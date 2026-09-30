import secrets
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import link_for, send_consent_request
from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Consent, Contact, User
from ..schemas import ContactIn, ContactOut, InviteOut

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _owned(db: Session, user: User, contact_id: int) -> Contact:
    c = db.get(Contact, contact_id)
    if not c or c.owner_id != user.id:      # 404 (not 403) so IDs can't be probed
        raise HTTPException(404, "Contact not found")
    return c


@router.get("", response_model=list[ContactOut])
def list_contacts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Contact).where(Contact.owner_id == user.id).order_by(Contact.priority, Contact.name)).all()


@router.post("", response_model=ContactOut, status_code=201)
def add_contact(body: ContactIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.scalars(select(Contact).where(Contact.owner_id == user.id)).all()
    if len(existing) >= settings.max_contacts:
        raise HTTPException(422, f"Maximum {settings.max_contacts} contacts")
    if any(c.phone == body.phone for c in existing):
        raise HTTPException(409, "This phone number is already a contact")
    contact = Contact(owner_id=user.id, name=body.name.strip(), phone=body.phone,
                      relationship_label=body.relationship_label, priority=body.priority,
                      view_token=secrets.token_urlsafe(24))
    db.add(contact)
    db.flush()
    send_consent_request(db, user, contact)
    db.commit()
    return contact


@router.get("/{contact_id}/invite", response_model=InviteOut)
def invite(contact_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Ready-to-send invitation text + a wa.me link, so the owner can share it on WhatsApp
    (or any app) without needing an SMS provider."""
    contact = _owned(db, user, contact_id)
    if contact.consent == Consent.CONFIRMED.value:
        raise HTTPException(409, "Already confirmed")
    link = link_for(contact)
    message = (f"Hi {contact.name}, {user.name} added you as a trusted contact on SafeSphere. "
               f"You will only get a message if they may need help. "
               f"Please tap to review and accept: {link}")
    digits = contact.phone.lstrip("+")
    return InviteOut(message=message, link=link,
                     whatsapp_url=f"https://wa.me/{digits}?text={urllib.parse.quote(message)}")


@router.post("/{contact_id}/resend", status_code=204)
def resend(contact_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    contact = _owned(db, user, contact_id)
    if contact.consent == Consent.CONFIRMED.value:
        raise HTTPException(409, "Already confirmed")
    send_consent_request(db, user, contact)
    db.commit()


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, contact_id))
    db.commit()
