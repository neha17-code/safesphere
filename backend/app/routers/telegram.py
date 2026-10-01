"""Telegram bot webhook. A contact taps 'Connect Telegram' on their page -> Telegram opens our bot with
/start <their-private-token> -> we store their chat id. Only CONFIRMED contacts can connect."""
import hmac
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts as alerts_mod
from ..config import settings
from ..database import get_db
from ..models import Consent, Contact, User

router = APIRouter(tags=["telegram"], include_in_schema=False)


@router.post("/telegram/webhook")
def webhook(payload: dict[str, Any] = Body(default_factory=dict),
            x_telegram_bot_api_secret_token: str | None = Header(default=None),
            db: Session = Depends(get_db)):
    tg = alerts_mod.telegram
    if tg is None:
        raise HTTPException(404, "Not found")
    secret = settings.telegram_webhook_secret
    if not secret or not hmac.compare_digest(x_telegram_bot_api_secret_token or "", secret):
        raise HTTPException(403, "Forbidden")

    msg = payload.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if chat_id is None or not text.startswith("/start"):
        return {"ok": True}

    parts = text.split(maxsplit=1)
    contact = db.scalar(select(Contact).where(Contact.view_token == parts[1])) if len(parts) == 2 else None

    if contact is None:
        tg.send_message(str(chat_id), "Hi! Open the SafeSphere link you were sent and tap 'Connect Telegram'.")
    elif contact.consent != Consent.CONFIRMED.value:
        tg.send_message(str(chat_id), "Please open your SafeSphere link and tap Accept first, then connect Telegram.")
    else:
        owner = db.get(User, contact.owner_id)
        contact.telegram_chat_id = str(chat_id)
        alerts_mod.log_event(db, contact.owner_id, "TELEGRAM_CONNECTED", contact.name, contact_id=contact.id)
        db.commit()
        tg.send_message(str(chat_id), f"Connected. You'll be alerted here if {owner.name} may need help.")
    return {"ok": True}
