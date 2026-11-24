import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'greensheet.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-32+-chars")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "8"))

# Only mailboxes under this domain may act as a club (create / revoke / resubmit sheets).
CLUB_EMAIL_DOMAIN = os.getenv("CLUB_EMAIL_DOMAIN", "clubs.college.edu").lower()
AUTHORITY_EMAIL_DOMAIN = os.getenv("AUTHORITY_EMAIL_DOMAIN", "college.edu").lower()

# Email (Mailpit default: smtp on 1025, web UI on 8025)
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "1") == "1"
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = os.getenv("SMTP_TLS", "0") == "1"
MAIL_FROM = os.getenv("MAIL_FROM", "greensheet@college.edu")
APP_URL = os.getenv("APP_URL", "http://localhost:5173")

# AI checker: rules always run; Claude is used on top when a key is set.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
# Only the Dean of Student Welfare may mark the approval chain as final.
FINALIZER_ROLE = "dean_sw"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
