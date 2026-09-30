"""Turns 'something happened' into SMS messages + audit events."""
from sqlalchemy.orm import Session

from .config import settings
from .models import Consent, Contact, Event, Journey, User
from .notifier import notifier


def link_for(contact: Contact) -> str:
    return f"{settings.public_base_url}/c/{contact.view_token}"


def log_event(db: Session, owner_id: int, type_: str, detail: str = "",
              journey_id: int | None = None, lat: float | None = None, lng: float | None = None,
              contact_id: int | None = None):
    db.add(Event(owner_id=owner_id, journey_id=journey_id, type=type_, detail=detail,
                 lat=lat, lng=lng, contact_id=contact_id))


def maps_link(lat: float | None, lng: float | None) -> str:
    return f"https://maps.google.com/?q={lat},{lng}" if lat is not None and lng is not None else ""


def send_to_contacts(db: Session, owner: User, contacts: list[Contact], text: str,
                     event_type: str, journey: Journey | None = None,
                     lat: float | None = None, lng: float | None = None) -> tuple[int, int]:
    """Send `text` (+ each contact's private link) to CONFIRMED contacts only.
    Returns (delivered, skipped_because_not_confirmed)."""
    delivered = skipped = 0
    for c in contacts:
        if c.consent != Consent.CONFIRMED.value:
            skipped += 1
            continue
        ok = notifier.send_sms(c.phone, f"{text}\nLive view: {link_for(c)}")
        delivered += 1 if ok else 0
        log_event(db, owner.id, event_type if ok else event_type + "_FAILED",
                  f"to {c.name}", journey.id if journey else None, lat, lng, contact_id=c.id)
    return delivered, skipped


def send_consent_request(db: Session, owner: User, contact: Contact) -> None:
    notifier.send_sms(
        contact.phone,
        f"{owner.name} added you as a trusted contact on SafeSphere. "
        f"You'll only be alerted if they may need help. Review & accept: {link_for(contact)}",
    )
    log_event(db, owner.id, "CONSENT_REQUESTED", f"to {contact.name}")
