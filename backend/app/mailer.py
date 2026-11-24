"""Email notifications. Every mail is stored in email_log (so the demo works even with no
SMTP server) and sent via SMTP when reachable (Mailpit: smtp localhost:1025)."""
import smtplib
import logging
from email.message import EmailMessage
from sqlalchemy.orm import Session
from . import config
from .models import EmailLog, GreenSheet, Club, User

log = logging.getLogger("mailer")


def _send_smtp(to: str, subject: str, body: str) -> bool:
    if not config.EMAIL_ENABLED:
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.MAIL_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=3) as s:
            if config.SMTP_TLS:
                s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:  # SMTP down must never break the workflow
        log.warning("SMTP send failed: %s", e)
        return False


def notify(db: Session, sheet: GreenSheet, subject: str, message: str, to_users: list[User] = (), extra: list[str] = (),
           include_club: bool = True):
    """Mail the given users + club mailbox + club cc list. De-duplicated."""
    addrs: list[str] = [u.email for u in to_users if u and u.active]
    club: Club = sheet.club
    if include_club:
        addrs += [club.email] + list(club.cc_emails or [])
    addrs += list(extra)
    seen = set()
    link = f"{config.APP_URL}/sheets/{sheet.id}"
    body = f"{message}\n\nGreen sheet: {sheet.ref} - {sheet.title}\nClub: {club.name}\nStatus: {sheet.status}\nOpen: {link}\n\n- Green Sheet Portal"
    for a in addrs:
        a = a.strip().lower()
        if not a or a in seen:
            continue
        seen.add(a)
        ok = _send_smtp(a, f"[{sheet.ref}] {subject}", body)
        db.add(EmailLog(sheet_id=sheet.id, to_addr=a, subject=f"[{sheet.ref}] {subject}", body=body, delivered=ok))
