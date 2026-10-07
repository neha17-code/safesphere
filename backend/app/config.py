"""Central configuration, read once from environment variables."""
import os
from dataclasses import dataclass


def normalise_db_url(url: str) -> str:
    """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy 2 + psycopg 3
    need the postgresql+psycopg:// form."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = normalise_db_url(os.getenv("DATABASE_URL", "sqlite:///./safesphere.db"))
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-secret-change-me-0123456789abcdef")
    jwt_expire_minutes: int = _int("JWT_EXPIRE_MINUTES", 60 * 24 * 7)
    # Render sets RENDER_EXTERNAL_URL automatically, so links in invitations just work when deployed.
    public_base_url: str = (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
                            or "http://localhost:8000").rstrip("/")

    grace_minutes: int = _int("GRACE_MINUTES", 10)
    second_level_minutes: int = _int("SECOND_LEVEL_MINUTES", 15)
    scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    scheduler_interval_seconds: int = _int("SCHEDULER_INTERVAL_SECONDS", 30)
    location_retention_hours: int = _int("LOCATION_RETENTION_HOURS", 24)

    twilio_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from: str = os.getenv("TWILIO_FROM_NUMBER", "")

    fast2sms_api_key: str = os.getenv("FAST2SMS_API_KEY", "")

    # Email over HTTPS (Brevo). Render's free plan blocks SMTP ports, so plain SMTP is not an option there.
    brevo_api_key: str = os.getenv("BREVO_API_KEY", "")
    email_from: str = os.getenv("EMAIL_FROM", "")            # must be a sender you verified in Brevo
    email_from_name: str = os.getenv("EMAIL_FROM_NAME", "SafeSphere")

    # Web Push: notifications that pop up on a contact's phone with no app and nothing open.
    # Generate the keys once with:  python scripts/gen_vapid.py
    vapid_public_key: str = os.getenv("VAPID_PUBLIC_KEY", "")
    vapid_private_key: str = os.getenv("VAPID_PRIVATE_KEY", "")
    vapid_subject: str = os.getenv("VAPID_SUBJECT") or "mailto:" + (os.getenv("EMAIL_FROM") or "admin@example.com")
    progress_update_minutes: int = _int("PROGRESS_UPDATE_MINUTES", 15)   # 0 turns the regular updates off

    max_contacts: int = 10

    def validate(self) -> None:
        if self.environment == "production" and self.jwt_secret.startswith("dev-only"):
            raise RuntimeError("Set a strong JWT_SECRET before running in production.")


settings = Settings()
