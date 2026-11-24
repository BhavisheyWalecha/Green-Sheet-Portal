from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from . import config, ai_check, esign, mailer
from .database import Base, engine, get_db, SessionLocal
from .models import (User, Club, GreenSheet, SheetVersion, ApprovalStep, SheetEvent, EmailLog, now,
                     CLUB_ROLES, APPROVER_ROLES, ALL_ROLES)
from .security import verify_password, make_token, current_user, require_roles, hash_password


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    from .seed import seed
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Green Sheet Portal", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=True)


# ---------------------------------------------------------------- helpers
def iso(d):
    return d.isoformat() + "Z" if d else None


def user_out(u: User | None):
    if not u:
        return None
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "designation": u.designation,
            "club_id": u.club_id, "club_name": u.club.name if u.club else None, "active": u.active}


def step_out(s: ApprovalStep):
    return {"id": s.id, "version": s.version, "status": s.status, "comment": s.comment, "next_kind": s.next_kind,
            "approver": user_out(s.approver), "acted_at": iso(s.acted_at), "created_at": iso(s.created_at),
            "signature": s.signature_hash[:16] if s.signature_hash else None}


def sheet_out(s: GreenSheet):
    return {"id": s.id, "ref": s.ref, "title": s.title, "club": {"id": s.club.id, "name": s.club.name},
            "created_by": user_out(s.creator), "event_date": s.event_date, "venue": s.venue, "status": s.status,
            "version": s.version, "current_approver": user_out(s.current_approver), "ai_status": s.ai_status,
            "created_at": iso(s.created_at), "updated_at": iso(s.updated_at)}


def can_view(u: User, s: GreenSheet) -> bool:
    if u.role == "admin":
        return True
    if u.role in CLUB_ROLES:
        return u.club_id == s.club_id
    if u.role == "dsw_office":
        return s.status in ("approved", "ready", "collected")
    if u.role == "dean_sw":
        return s.status != "blocked"
    return any(st.approver_id == u.id for st in s.steps)


def get_sheet(db: Session, sheet_id: int, user: User) -> GreenSheet:
    s = db.get(GreenSheet, sheet_id)
    if not s or not can_view(user, s):
        raise HTTPException(404, "Green sheet not found")
    return s


def event(db, sheet, actor, action, detail=""):
    db.add(SheetEvent(sheet_id=sheet.id, actor_id=actor.id if actor else None, action=action, detail=detail))


def signers(sheet) -> list[User]:
    seen, out = set(), []
    for st in sheet.steps:
        if st.status == "approved" and st.approver_id not in seen:
            seen.add(st.approver_id)
            out.append(st.approver)
    return out


def is_club_user(u: User) -> bool:
    return u.role in CLUB_ROLES and u.email.lower().endswith("@" + config.CLUB_EMAIL_DOMAIN)


def sheet_file(sheet: GreenSheet, version: int | None = None) -> tuple[Path, SheetVersion]:
    v = next((x for x in sheet.versions if x.version == (version or sheet.version)), None)
    if not v:
        raise HTTPException(404, "File missing")
    return Path(v.file_path), v


def save_version(db, sheet, data: bytes):
    d = config.STORAGE_DIR / f"sheet_{sheet.id}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"v{sheet.version}.pdf"
    p.write_bytes(data)
    db.add(SheetVersion(sheet_id=sheet.id, version=sheet.version, file_path=str(p), sha256=esign.file_sha256(data)))


def pick_approver(db, approver_id: int, exclude: User | None = None) -> User:
    a = db.get(User, approver_id)
    if not a or not a.active or a.role not in APPROVER_ROLES:
        raise HTTPException(400, "Selected person is not an active approving authority")
    if exclude and a.id == exclude.id:
        raise HTTPException(400, "You cannot route the sheet to yourself")
    return a


def route_to(db, sheet, approver: User):
    sheet.status, sheet.current_approver_id = "pending", approver.id
    db.add(ApprovalStep(sheet_id=sheet.id, version=sheet.version, approver_id=approver.id))


async def read_pdf(file: UploadFile) -> bytes:
    data = await file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(400, "Please attach the green sheet PDF")
    return data


def apply_ai(sheet, res):
    sheet.ai_status, sheet.ai_summary, sheet.ai_flags, sheet.ai_engine = res["status"], res["summary"], res["flags"], res["engine"]


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(u), "user": user_out(u)}


@app.get("/api/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@app.get("/api/approvers")
def approvers(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.scalars(select(User).where(User.role.in_(APPROVER_ROLES), User.active == True).order_by(User.name)).all()  # noqa
    return [user_out(r) for r in rows if r.id != u.id]


@app.get("/api/clubs")
def clubs(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return [{"id": c.id, "name": c.name, "email": c.email, "cc_emails": c.cc_emails, "suggested_path": c.suggested_path}
            for c in db.scalars(select(Club).order_by(Club.name))]


# ---------------------------------------------------------------- sheets: read
@app.get("/api/sheets")
def list_sheets(db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = select(GreenSheet).order_by(GreenSheet.updated_at.desc())
    if u.role in CLUB_ROLES:
        q = q.where(GreenSheet.club_id == u.club_id)
    elif u.role == "dsw_office":
        q = q.where(GreenSheet.status.in_(("approved", "ready", "collected")))
    elif u.role == "dean_sw":
        q = q.where(GreenSheet.status != "blocked")
    elif u.role == "approver":
        q = q.where(GreenSheet.id.in_(select(ApprovalStep.sheet_id).where(ApprovalStep.approver_id == u.id)))
    return [sheet_out(s) for s in db.scalars(q)]


@app.get("/api/sheets/{sheet_id}")
def sheet_detail(sheet_id: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = get_sheet(db, sheet_id, u)
    hashes = {v.version: v.sha256 for v in s.versions}
    mine_club = u.role in CLUB_ROLES and u.club_id == s.club_id and is_club_user(u)
    out = sheet_out(s)
    approved = [st for st in s.steps if st.status == "approved"]
    out.update({
        "description": s.description, "ai": {"status": s.ai_status, "summary": s.ai_summary, "flags": s.ai_flags, "engine": s.ai_engine},
        "steps": [step_out(st) for st in s.steps],
        "events": [{"action": e.action, "detail": e.detail, "at": iso(e.created_at), "actor": user_out(e.actor)} for e in s.events],
        "versions": [{"version": v.version, "uploaded_at": iso(v.uploaded_at), "sha256": v.sha256} for v in s.versions],
        "integrity_ok": esign.verify_chain(s.steps, hashes),
        "suggested_path": [user_out(db.get(User, i)) for i in (s.club.suggested_path or []) if db.get(User, i)],
        "can": {
            "act": s.status == "pending" and s.current_approver_id == u.id,
            "finalize": u.role == config.FINALIZER_ROLE,
            "revoke": mine_club and s.status in ("pending", "changes_requested"),
            "resubmit": mine_club and s.status in ("changes_requested", "blocked"),
            "stamp": u.role == "dsw_office" and s.status == "approved",
            "collect": u.role == "dsw_office" and s.status == "ready",
        },
        "needs_first_approver": s.status == "blocked" or not any(st.status == "changes_requested" for st in s.steps),
        "signatures": len(approved),
    })
    return out


@app.get("/api/sheets/{sheet_id}/file")
def download(sheet_id: int, plain: bool = False, db: Session = Depends(get_db), u: User = Depends(current_user)):
    s = get_sheet(db, sheet_id, u)
    path, _ = sheet_file(s)
    data = path.read_bytes()
    if not plain:
        approved = [st for st in s.steps if st.status == "approved"]
        data = esign.build_signed_pdf(data, s, approved, final=s.status in ("approved", "ready", "collected"),
                                      stamped=s.status in ("ready", "collected"))
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{s.ref}.pdf"'})


# ---------------------------------------------------------------- sheets: club actions
@app.post("/api/sheets", status_code=201)
async def create_sheet(title: str = Form(...), description: str = Form(...), event_date: str = Form(...), venue: str = Form(""),
                       first_approver_id: int = Form(...), file: UploadFile = File(...),
                       db: Session = Depends(get_db), u: User = Depends(require_roles(*CLUB_ROLES))):
    if not is_club_user(u):
        raise HTTPException(403, f"Only official club mailboxes (@{config.CLUB_EMAIL_DOMAIN}) can submit green sheets")
    data = await read_pdf(file)
    first = pick_approver(db, first_approver_id)
    s = GreenSheet(club_id=u.club_id, created_by=u.id, title=title.strip(), description=description.strip(),
                   event_date=event_date, venue=venue.strip())
    db.add(s)
    db.flush()
    save_version(db, s, data)
    res = ai_check.check_sheet(data, s.title, s.description, event_date, venue)
    apply_ai(s, res)
    event(db, s, u, "submitted", f"Submitted v1 (AI check: {res['status']})")
    if res["status"] == "blocked":
        s.status = "blocked"
        event(db, s, None, "ai_blocked", "; ".join(f["msg"] for f in res["flags"] if f["level"] == "block"))
        mailer.notify(db, s, "Green sheet blocked by AI check", "Your green sheet was NOT sent to any authority because the AI check found a problem. Open it to see what to fix, then resubmit.", [u], include_club=False)
    else:
        route_to(db, s, first)
        mailer.notify(db, s, "New green sheet awaiting your approval", f"{u.name} ({s.club.name}) submitted a green sheet for your approval.\n\nAI summary: {s.ai_summary}", [first])
    db.commit()
    return sheet_out(s)


@app.post("/api/sheets/{sheet_id}/resubmit")
async def resubmit(sheet_id: int, description: str = Form(""), first_approver_id: Optional[int] = Form(None),
                   file: UploadFile | None = File(None), db: Session = Depends(get_db),
                   u: User = Depends(require_roles(*CLUB_ROLES))):
    s = get_sheet(db, sheet_id, u)
    if not is_club_user(u) or s.status not in ("changes_requested", "blocked"):
        raise HTTPException(400, "This sheet cannot be resubmitted right now")
    back_to = None
    requested = [st for st in s.steps if st.status == "changes_requested"]
    if s.status == "changes_requested" and requested:
        back_to = requested[-1].approver
    else:
        if not first_approver_id:
            raise HTTPException(400, "Choose the first approver")
        back_to = pick_approver(db, first_approver_id)
    if file and file.filename:
        data = await read_pdf(file)
    else:
        if s.status == "blocked":
            raise HTTPException(400, "Upload a corrected PDF - the blocked one cannot be reused")
        data = sheet_file(s)[0].read_bytes()
    if description.strip():
        s.description = description.strip()
    s.version += 1
    save_version(db, s, data)
    res = ai_check.check_sheet(data, s.title, s.description, s.event_date, s.venue)
    apply_ai(s, res)
    event(db, s, u, "resubmitted", f"Resubmitted as v{s.version} (AI check: {res['status']})")
    if res["status"] == "blocked":
        s.status, s.current_approver_id = "blocked", None
        mailer.notify(db, s, "Green sheet blocked by AI check", "The corrected sheet was blocked by the AI check and was not sent on.", [u], include_club=False)
    else:
        route_to(db, s, back_to)
        mailer.notify(db, s, "Updated green sheet awaiting your approval", f"{u.name} resubmitted the sheet (v{s.version}) after the requested changes.", [back_to])
    db.commit()
    return sheet_out(s)


@app.post("/api/sheets/{sheet_id}/revoke")
def revoke(sheet_id: int, db: Session = Depends(get_db), u: User = Depends(require_roles(*CLUB_ROLES))):
    s = get_sheet(db, sheet_id, u)
    if not is_club_user(u) or s.status not in ("pending", "changes_requested"):
        raise HTTPException(400, "A sheet can only be revoked before final approval")
    pending_user = s.current_approver
    for st in s.steps:
        if st.status == "pending":
            st.status = "skipped"
    s.status, s.current_approver_id = "revoked", None
    event(db, s, u, "revoked", "Revoked by the club")
    mailer.notify(db, s, "Green sheet revoked", f"{u.name} revoked this green sheet. No further action is needed.", ([pending_user] if pending_user else []) + signers(s))
    db.commit()
    return sheet_out(s)


# ---------------------------------------------------------------- sheets: approver action
class ActionIn(BaseModel):
    decision: Literal["approve", "changes", "reject"]
    comment: str = ""
    next_kind: Optional[Literal["approver", "final"]] = None
    next_approver_id: Optional[int] = None


@app.post("/api/sheets/{sheet_id}/action")
def act(sheet_id: int, body: ActionIn, db: Session = Depends(get_db), u: User = Depends(require_roles(*APPROVER_ROLES))):
    s = get_sheet(db, sheet_id, u)
    step = next((x for x in reversed(s.steps) if x.status == "pending" and x.approver_id == u.id), None)
    if s.status != "pending" or s.current_approver_id != u.id or not step:
        raise HTTPException(400, "This sheet is not waiting for you")
    comment = body.comment.strip()
    if body.decision in ("changes", "reject") and not comment:
        raise HTTPException(400, "Please say what needs to change / why it is rejected")
    step.acted_at, step.comment = now(), comment

    if body.decision == "changes":
        step.status = "changes_requested"
        s.status, s.current_approver_id = "changes_requested", None
        event(db, s, u, "changes_requested", comment)
        mailer.notify(db, s, "Changes requested on your green sheet", f"{u.name} ({u.designation}) asked for a change:\n\n\"{comment}\"\n\nUpdate and resubmit; it will come back to the same approver.", signers(s))
    elif body.decision == "reject":
        step.status = "rejected"
        s.status, s.current_approver_id = "rejected", None
        event(db, s, u, "rejected", comment)
        mailer.notify(db, s, "Green sheet rejected", f"{u.name} ({u.designation}) rejected the sheet:\n\n\"{comment}\"", signers(s))
    else:
        if body.next_kind == "final":
            if u.role != config.FINALIZER_ROLE:
                raise HTTPException(400, "Only the Dean of Student Welfare can give the final approval. Choose the next approver instead.")
            nxt = None
        elif body.next_kind == "approver" and body.next_approver_id:
            nxt = pick_approver(db, body.next_approver_id, exclude=u)
        else:
            raise HTTPException(400, "After approving, choose the next approver or mark it final")
        # e-sign: hash chained to previous signature + file hash
        prev = next((x.signature_hash for x in reversed(s.steps) if x.status == "approved"), "")
        fh = next(v.sha256 for v in s.versions if v.version == step.version)
        step.status, step.next_kind, step.prev_hash = "approved", body.next_kind, prev
        step.signature_hash = esign.sign_hash(prev, fh, u.id, step.acted_at, "approved", comment)
        if nxt:
            route_to(db, s, nxt)
            event(db, s, u, "approved", f"Signed and forwarded to {nxt.name}. {comment}".strip())
            mailer.notify(db, s, "Green sheet awaiting your approval", f"{u.name} ({u.designation}) approved and forwarded this sheet to you.\nApproved by so far: {', '.join(x.name for x in signers(s))}", [nxt])
            mailer.notify(db, s, "Green sheet progress", f"{u.name} approved. Now with {nxt.name} ({nxt.designation}).", [], include_club=True)
        else:
            s.status, s.current_approver_id = "approved", None
            event(db, s, u, "final_approved", f"Final approval by {u.name}. Sent to DSW office for printing and stamping. {comment}".strip())
            office = db.scalars(select(User).where(User.role == "dsw_office", User.active == True)).all()  # noqa
            mailer.notify(db, s, "Final approval - ready to print and stamp", "The Dean of Student Welfare gave final approval. Please print, stamp and keep it ready for collection.", office, include_club=False)
            mailer.notify(db, s, "Green sheet fully approved", "Your green sheet is fully approved. The DSW office will print and stamp it; you will get another mail when it is ready to collect.", signers(s))
    db.commit()
    return sheet_out(s)


# ---------------------------------------------------------------- DSW office
@app.post("/api/sheets/{sheet_id}/dsw/stamp")
def dsw_stamp(sheet_id: int, db: Session = Depends(get_db), u: User = Depends(require_roles("dsw_office"))):
    s = get_sheet(db, sheet_id, u)
    if s.status != "approved":
        raise HTTPException(400, "Sheet is not waiting for printing")
    s.status = "ready"
    event(db, s, u, "stamped", "Printed and stamped by DSW office. Ready for collection.")
    mailer.notify(db, s, "Your green sheet is ready - collect from DSW office", "Your signed and stamped green sheet is ready. Please collect it from the DSW office.", signers(s))
    db.commit()
    return sheet_out(s)


@app.post("/api/sheets/{sheet_id}/dsw/collected")
def dsw_collected(sheet_id: int, db: Session = Depends(get_db), u: User = Depends(require_roles("dsw_office"))):
    s = get_sheet(db, sheet_id, u)
    if s.status != "ready":
        raise HTTPException(400, "Sheet is not ready for collection")
    s.status = "collected"
    event(db, s, u, "collected", "Collected by the club")
    mailer.notify(db, s, "Green sheet collected", "The club collected the stamped green sheet.", [])
    db.commit()
    return sheet_out(s)


# ---------------------------------------------------------------- email outbox (demo / audit)
@app.get("/api/emails")
def emails(db: Session = Depends(get_db), u: User = Depends(current_user)):
    q = select(EmailLog).order_by(EmailLog.id.desc()).limit(100)
    if u.role != "admin":
        mine = [u.email.lower()] + ([db.get(Club, u.club_id).email.lower()] if u.club_id else [])
        q = q.where(EmailLog.to_addr.in_(mine))
    return [{"id": e.id, "to": e.to_addr, "subject": e.subject, "body": e.body, "delivered": e.delivered, "at": iso(e.created_at),
             "sheet_id": e.sheet_id} for e in db.scalars(q)]


# ---------------------------------------------------------------- admin
class UserIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["club_secretary", "club_joint_secretary", "approver", "dean_sw", "dsw_office", "admin"]
    designation: str = ""
    club_id: Optional[int] = None


@app.get("/api/admin/users")
def admin_users(db: Session = Depends(get_db), u: User = Depends(require_roles("admin"))):
    return [user_out(x) for x in db.scalars(select(User).order_by(User.role, User.name))]


@app.post("/api/admin/users", status_code=201)
def admin_create_user(body: UserIn, db: Session = Depends(get_db), u: User = Depends(require_roles("admin"))):
    email = body.email.lower()
    if body.role in CLUB_ROLES:
        if not email.endswith("@" + config.CLUB_EMAIL_DOMAIN):
            raise HTTPException(400, f"Club accounts must use an @{config.CLUB_EMAIL_DOMAIN} address")
        if not body.club_id or not db.get(Club, body.club_id):
            raise HTTPException(400, "Choose a club for this account")
    elif not email.endswith("@" + config.AUTHORITY_EMAIL_DOMAIN):
        raise HTTPException(400, f"Authority/staff accounts must use an @{config.AUTHORITY_EMAIL_DOMAIN} address")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "Email already registered")
    nu = User(name=body.name, email=email, password_hash=hash_password(body.password), role=body.role,
              designation=body.designation, club_id=body.club_id if body.role in CLUB_ROLES else None)
    db.add(nu)
    db.commit()
    return user_out(nu)


class UserPatch(BaseModel):
    active: Optional[bool] = None
    designation: Optional[str] = None
    password: Optional[str] = None


@app.patch("/api/admin/users/{uid}")
def admin_patch_user(uid: int, body: UserPatch, db: Session = Depends(get_db), u: User = Depends(require_roles("admin"))):
    t = db.get(User, uid)
    if not t:
        raise HTTPException(404, "No such user")
    if body.active is not None:
        if t.id == u.id and not body.active:
            raise HTTPException(400, "You cannot disable yourself")
        t.active = body.active
    if body.designation is not None:
        t.designation = body.designation
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        t.password_hash = hash_password(body.password)
    db.commit()
    return user_out(t)


class ClubIn(BaseModel):
    name: str
    email: EmailStr
    cc_emails: list[EmailStr] = []
    suggested_path: list[int] = []


@app.post("/api/admin/clubs", status_code=201)
def admin_create_club(body: ClubIn, db: Session = Depends(get_db), u: User = Depends(require_roles("admin"))):
    if not body.email.lower().endswith("@" + config.CLUB_EMAIL_DOMAIN):
        raise HTTPException(400, f"Club mailbox must be on @{config.CLUB_EMAIL_DOMAIN}")
    c = Club(name=body.name, email=body.email.lower(), cc_emails=[e.lower() for e in body.cc_emails], suggested_path=body.suggested_path)
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name}


@app.patch("/api/admin/clubs/{cid}")
def admin_patch_club(cid: int, body: ClubIn, db: Session = Depends(get_db), u: User = Depends(require_roles("admin"))):
    c = db.get(Club, cid)
    if not c:
        raise HTTPException(404, "No such club")
    c.name, c.cc_emails, c.suggested_path = body.name, [e.lower() for e in body.cc_emails], body.suggested_path
    db.commit()
    return {"id": c.id}
