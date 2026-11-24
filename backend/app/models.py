from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# roles
CLUB_ROLES = ("club_secretary", "club_joint_secretary")
APPROVER_ROLES = ("approver", "dean_sw")
ALL_ROLES = CLUB_ROLES + APPROVER_ROLES + ("dsw_office", "admin")


class Club(Base):
    __tablename__ = "clubs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)  # club mailbox, must be on club domain
    cc_emails: Mapped[list] = mapped_column(JSON, default=list)  # extra people/authorities mailed on every update
    suggested_path: Mapped[list] = mapped_column(JSON, default=list)  # optional hint: approver user ids in usual order


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    designation: Mapped[str] = mapped_column(String(200), default="")
    club_id: Mapped[int | None] = mapped_column(ForeignKey("clubs.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    club: Mapped["Club | None"] = relationship()


class GreenSheet(Base):
    __tablename__ = "green_sheets"
    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    event_date: Mapped[str] = mapped_column(String(20))
    venue: Mapped[str] = mapped_column(String(200), default="")
    # blocked | pending | changes_requested | rejected | revoked | approved | ready | collected
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    current_approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ai_status: Mapped[str] = mapped_column(String(20), default="pass")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
    ai_flags: Mapped[list] = mapped_column(JSON, default=list)
    ai_engine: Mapped[str] = mapped_column(String(40), default="rules")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    club: Mapped["Club"] = relationship()
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    current_approver: Mapped["User | None"] = relationship(foreign_keys=[current_approver_id])
    versions: Mapped[list["SheetVersion"]] = relationship(order_by="SheetVersion.version")
    steps: Mapped[list["ApprovalStep"]] = relationship(order_by="ApprovalStep.id")
    events: Mapped[list["SheetEvent"]] = relationship(order_by="SheetEvent.id")

    @property
    def ref(self):
        return f"GS-{self.created_at.year}-{self.id:04d}"


class SheetVersion(Base):
    __tablename__ = "sheet_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("green_sheets.id"))
    version: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("green_sheets.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # pending | approved | changes_requested | rejected | skipped (revoked)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    comment: Mapped[str] = mapped_column(Text, default="")
    next_kind: Mapped[str] = mapped_column(String(10), default="")  # approver | final
    acted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    signature_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    approver: Mapped["User"] = relationship()


class SheetEvent(Base):
    __tablename__ = "sheet_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int] = mapped_column(ForeignKey("green_sheets.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    actor: Mapped["User | None"] = relationship()


class EmailLog(Base):
    __tablename__ = "email_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    sheet_id: Mapped[int | None] = mapped_column(ForeignKey("green_sheets.id"), nullable=True)
    to_addr: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
