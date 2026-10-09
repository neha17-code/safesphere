"""Which alert channels are really set up on this server, and a self-test, so progress is never a guess."""
from fastapi import APIRouter, Depends, HTTPException

from .. import alerts as alerts_mod
from ..deps import current_user
from ..models import User
from ..notifier import ConsoleNotifier
from ..security import RateLimiter

router = APIRouter(prefix="/status", tags=["status"])
_limiter = RateLimiter(limit=5, window_seconds=60)


@router.get("/channels")
def channels(_: User = Depends(current_user)):
    return {"email": alerts_mod.emailer is not None,
            "sms": not isinstance(alerts_mod.notifier, ConsoleNotifier),
            "push": alerts_mod.pusher is not None}


def _hint(error: str) -> str:
    low = error.lower()
    if "http 401" in low or "unrecognised ip" in low or "unrecognized ip" in low:
        return ("Brevo did not accept the API key or this server's IP address. Check BREVO_API_KEY in Render, and in "
                "Brevo turn off blocking of unknown IP addresses (Security > Authorized IPs).")
    if "http 400" in low and "sender" in low:
        return "Brevo does not recognise the sender. EMAIL_FROM must exactly match a sender you verified in Brevo."
    if "http 403" in low or "activat" in low:
        return "Your Brevo account may still need activation or review. Check for notices in Brevo."
    if "could not reach" in low:
        return "The server could not connect to Brevo. Try again in a minute."
    return ""


@router.post("/test-email")
def test_email(user: User = Depends(current_user)):
    """Send a test email to the logged-in user's own address and report exactly what happened."""
    if not _limiter.allow(f"test-email:{user.id}"):
        raise HTTPException(429, "Too many tests. Wait a minute and try again.")
    mailer = alerts_mod.emailer
    if mailer is None:
        return {"ok": False, "to": user.email, "hint": "",
                "detail": "Email is not set up on the server (BREVO_API_KEY and EMAIL_FROM are missing)."}
    ok = mailer.send_email(user.email, "SafeSphere test email",
                           "If you can read this, SafeSphere email alerts work. Check Spam if it was not in your inbox.")
    error = "" if ok else (getattr(mailer, "last_error", "") or "The email provider refused the message.")
    return {"ok": ok, "to": user.email, "hint": "" if ok else _hint(error),
            "detail": "Sent. Check your inbox and your Spam folder." if ok else error}
