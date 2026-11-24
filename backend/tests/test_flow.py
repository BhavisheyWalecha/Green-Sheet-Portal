import io, os, tempfile
_tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/t.db", STORAGE_DIR=f"{_tmp}/st", EMAIL_ENABLED="0", ANTHROPIC_API_KEY="")

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from app.main import app

GOOD_TEXT = ["Event: RoboWars 2026 inter-college robotics competition", "Date: 20/12/2026   Venue: Main Auditorium",
             "Budget: Rs. 45,000 expenditure approved by treasurer", "Expected participants: 120 attendees",
             "Faculty coordinator: Dr. Arun Kumar", "Organised by the Robotics Club for students of all branches."]


def pdf(lines=GOOD_TEXT, evil=False):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    y = 800
    for l in lines:
        c.drawString(50, y, l); y -= 20
    c.save()
    d = b.getvalue()
    return d.replace(b"%%EOF", b"/JavaScript (app.alert(1))\n%%EOF") if evil else d


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def ids(client, h):
    return {a["email"]: a["id"] for a in client.get("/api/approvers", headers=h).json()}


def submit(client, h, first, data=None):
    return client.post("/api/sheets", headers=h, data={"title": "RoboWars 2026", "description": "Annual inter-college robotics competition with workshops and a final arena battle.",
                       "event_date": "2026-12-20", "venue": "Main Auditorium", "first_approver_id": first},
                       files={"file": ("gs.pdf", data or pdf(), "application/pdf")})


def test_full_happy_path_with_changes_and_stamp(client):
    club = login(client, "riya.secretary@clubs.college.edu")
    ap = ids(client, club)
    r = submit(client, club, ap["arun.kumar@college.edu"]); assert r.status_code == 201, r.text
    sid = r.json()["id"]; assert r.json()["status"] == "pending"

    coord = login(client, "arun.kumar@college.edu"); hod = login(client, "hod.cse@college.edu"); dean = login(client, "dean.sw@college.edu")
    # unrelated approver cannot see it
    assert client.get(f"/api/sheets/{sid}", headers=hod).status_code == 404
    # coordinator asks for change
    assert client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "changes"}).status_code == 400  # comment required
    r = client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "changes", "comment": "Add sponsor details"}); assert r.status_code == 200
    assert client.get(f"/api/sheets/{sid}", headers=club).json()["status"] == "changes_requested"
    # joint secretary of same club resubmits -> returns to same approver
    joint = login(client, "karan.joint@clubs.college.edu")
    r = client.post(f"/api/sheets/{sid}/resubmit", headers=joint, files={"file": ("v2.pdf", pdf(GOOD_TEXT + ["Sponsors: none"]), "application/pdf")}); assert r.status_code == 200, r.text
    d = client.get(f"/api/sheets/{sid}", headers=club).json()
    assert d["version"] == 2 and d["current_approver"]["email"] == "arun.kumar@college.edu"
    # coordinator approves -> HOD
    hod_id = ids(client, coord)["hod.cse@college.edu"]
    assert client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "approve", "next_kind": "final"}).status_code == 400  # only dean finalizes
    assert client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "approve"}).status_code == 400  # must choose next
    assert client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "approve", "next_kind": "approver", "next_approver_id": hod_id}).status_code == 200
    # wrong person cannot act
    assert client.post(f"/api/sheets/{sid}/action", headers=dean, json={"decision": "approve", "next_kind": "final"}).status_code in (400, 404)
    dean_id = ids(client, hod)["dean.sw@college.edu"]
    assert client.post(f"/api/sheets/{sid}/action", headers=hod, json={"decision": "approve", "comment": "ok", "next_kind": "approver", "next_approver_id": dean_id}).status_code == 200
    assert client.post(f"/api/sheets/{sid}/action", headers=dean, json={"decision": "approve", "next_kind": "final"}).status_code == 200
    d = client.get(f"/api/sheets/{sid}", headers=club).json()
    assert d["status"] == "approved" and d["integrity_ok"] and d["signatures"] == 3
    assert not d["can"]["revoke"]
    # signed pdf downloads
    f = client.get(f"/api/sheets/{sid}/file", headers=club); assert f.status_code == 200 and f.content.startswith(b"%PDF")
    # DSW office
    dsw = login(client, "dsw.office@college.edu")
    assert client.post(f"/api/sheets/{sid}/dsw/stamp", headers=club).status_code == 403
    assert client.post(f"/api/sheets/{sid}/dsw/stamp", headers=dsw).status_code == 200
    assert client.post(f"/api/sheets/{sid}/dsw/collected", headers=dsw).status_code == 200
    assert client.get(f"/api/sheets/{sid}", headers=club).json()["status"] == "collected"
    # emails were logged for the club, cc list and approvers
    mails = client.get("/api/emails", headers=login(client, "admin@college.edu")).json()
    tos = {m["to"] for m in mails}
    assert {"robotics@clubs.college.edu", "student.council@college.edu", "hod.cse@college.edu", "dsw.office@college.edu"} <= tos


def test_malicious_pdf_is_blocked_and_not_routed(client):
    club = login(client, "riya.secretary@clubs.college.edu")
    ap = ids(client, club)
    r = submit(client, club, ap["arun.kumar@college.edu"], pdf(evil=True)); assert r.status_code == 201
    j = r.json(); assert j["status"] == "blocked" and j["current_approver"] is None
    coord = login(client, "arun.kumar@college.edu")
    assert client.get(f"/api/sheets/{j['id']}", headers=coord).status_code == 404
    d = client.get(f"/api/sheets/{j['id']}", headers=club).json()
    assert any(f["level"] == "block" for f in d["ai"]["flags"])
    # fixed re-upload gets routed
    r = client.post(f"/api/sheets/{j['id']}/resubmit", headers=club, data={"first_approver_id": ap["arun.kumar@college.edu"]}, files={"file": ("ok.pdf", pdf(), "application/pdf")})
    assert r.status_code == 200 and r.json()["status"] == "pending"


def test_revoke_and_isolation(client):
    club = login(client, "riya.secretary@clubs.college.edu"); other = login(client, "ananya.secretary@clubs.college.edu")
    ap = ids(client, club)
    sid = submit(client, club, ap["arun.kumar@college.edu"]).json()["id"]
    assert client.get(f"/api/sheets/{sid}", headers=other).status_code == 404       # other club cannot see
    assert client.post(f"/api/sheets/{sid}/revoke", headers=other).status_code == 404
    assert client.post(f"/api/sheets/{sid}/revoke", headers=club).status_code == 200
    coord = login(client, "arun.kumar@college.edu")
    assert client.post(f"/api/sheets/{sid}/action", headers=coord, json={"decision": "reject", "comment": "x"}).status_code == 400


def test_auth_and_roles(client):
    assert client.get("/api/sheets").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@college.edu", "password": "bad"}).status_code == 401
    approver = login(client, "arun.kumar@college.edu")
    assert client.post("/api/admin/users", headers=approver, json={}).status_code in (403, 422)
    admin = login(client, "admin@college.edu")
    bad = {"name": "X", "email": "x@gmail.com", "password": "password123", "role": "club_secretary", "club_id": 1}
    assert client.post("/api/admin/users", headers=admin, json=bad).status_code == 400    # club mailbox must be on club domain
    ok = dict(bad, email="x@clubs.college.edu")
    assert client.post("/api/admin/users", headers=admin, json=ok).status_code == 201
