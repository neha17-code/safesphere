"""Turns 'something happened' into messages + audit events, and reports what really happened."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .config import settings
from .models import Consent, Contact, Event, Journey, User, utcnow
from .notifier import emailer, notifier, pusher   # module globals: tests swap them for fakes


@dataclass
class Outcome:
    """What happened for ONE contact. Shown to the owner so progress is never a guess."""
    name: str
    ok: bool
    channel: str          # email | sms | sms+email | none | skipped
    reason: str = ""      # "" | NOT_ACCEPTED | NO_CONTACT_EMAIL | EMAIL_NOT_CONFIGURED | PROVIDER_REJECTED


def link_for(contact: Contact) -> str:
    return f"{settings.public_base_url}/c/{contact.view_token}"


def log_event(db: Session, owner_id: int, type_: str, detail: str = "",
              journey_id: int | None = None, lat: float | None = None, lng: float | None = None,
              contact_id: int | None = None):
    db.add(Event(owner_id=owner_id, journey_id=journey_id, type=type_, detail=detail,
                 lat=lat, lng=lng, contact_id=contact_id))


def maps_link(lat: float | None, lng: float | None) -> str:
    return f"https://maps.google.com/?q={lat},{lng}" if lat is not None and lng is not None else ""


FOOTER = "\n\nYou received this because someone added you as a trusted contact on SafeSphere."


def _subject(text: str) -> str:
    lines = text.strip().splitlines()
    first = lines[0] if lines else "Alert"
    return "SafeSphere: " + (first if len(first) <= 85 else first[:85] + "...")


def _why_failed(contact: Contact) -> str:
    if emailer is None:
        return "EMAIL_NOT_CONFIGURED"
    if not contact.email:
        return "NO_CONTACT_EMAIL"
    return "PROVIDER_REJECTED"


TITLES = {"JOURNEY_STARTED": "Journey started", "ARRIVED": "Arrived safely", "EMERGENCY_ALERT": "EMERGENCY",
          "UNSAFE_ALERT": "Feels unsafe", "DURESS_ALERT": "SILENT ALERT", "CONTACTS_ALERTED": "Not checked in",
          "ESCALATED": "URGENT", "DELAY_UPDATE": "Running late"}


def push_to_contact(db: Session, contact: Contact, title: str, body: str, ttl: int = 86400) -> bool:
    """Notify every device the contact enabled. Expired subscriptions are removed. True if any device got it."""
    if pusher is None or not contact.push_subscriptions:
        return False
    payload = {"title": title, "body": body[:300], "url": link_for(contact)}
    delivered = False
    for sub in list(contact.push_subscriptions):
        result = pusher.send({"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}, payload, ttl)
        if result == "ok":
            delivered = True
        elif result == "gone":
            db.delete(sub)
    return delivered


def push_progress(db: Session, owner: User, journey: Journey, body: str) -> int:
    """Regular 'on the way' update, by push only (no SMS/email, so it never costs money or spams inboxes)."""
    return sum(push_to_contact(db, c, f"{owner.name} is on the way", body, ttl=900)
               for c in journey.contacts if c.consent == Consent.CONFIRMED.value)


def _deliver(db: Session, contact: Contact, text: str, event_type: str) -> tuple[bool, str]:
    """Every available channel is tried: push (instant, free), then SMS, falling back to email.
    True only if at least one channel actually accepted the message."""
    channels = []
    if push_to_contact(db, contact, TITLES.get(event_type, "SafeSphere"), text):
        channels.append("push")
    full = f"{text}\nLive view: {link_for(contact)}"
    if notifier.send_sms(contact.phone, full):
        channels.append("sms")
    elif emailer and contact.email and emailer.send_email(contact.email, _subject(text), full + FOOTER):
        channels.append("email")
    return bool(channels), "+".join(channels) or "none"


def notify_contacts(db: Session, owner: User, contacts: list[Contact], text: str,
                    event_type: str, journey: Journey | None = None,
                    lat: float | None = None, lng: float | None = None) -> list[Outcome]:
    """Send `text` (+ each contact's private link) to CONFIRMED contacts only, one Outcome per contact."""
    outcomes: list[Outcome] = []
    for c in contacts:
        if c.consent != Consent.CONFIRMED.value:
            outcomes.append(Outcome(c.name, False, "skipped", "NOT_ACCEPTED"))
            continue
        ok, channel = _deliver(db, c, text, event_type)
        log_event(db, owner.id, event_type if ok else event_type + "_FAILED",
                  f"to {c.name} via {channel}", journey.id if journey else None, lat, lng, contact_id=c.id)
        outcomes.append(Outcome(c.name, ok, channel, "" if ok else _why_failed(c)))
    return outcomes


def send_to_contacts(db: Session, owner: User, contacts: list[Contact], text: str,
                     event_type: str, journey: Journey | None = None,
                     lat: float | None = None, lng: float | None = None) -> tuple[int, int]:
    """Same as notify_contacts but returns (delivered, skipped_because_not_accepted)."""
    outs = notify_contacts(db, owner, contacts, text, event_type, journey, lat, lng)
    return sum(o.ok for o in outs), sum(o.reason == "NOT_ACCEPTED" for o in outs)


def send_consent_request(db: Session, owner: User, contact: Contact) -> Outcome:
    """Send the invitation (SMS and/or email), record how it went on the contact, and return the outcome."""
    text = (f"{owner.name} added you as a trusted contact on SafeSphere. "
            f"You'll only be alerted if they may need help. Review & accept: {link_for(contact)}")
    channels = []
    if notifier.send_sms(contact.phone, text):
        channels.append("sms")
    if emailer and contact.email and emailer.send_email(
            contact.email, f"SafeSphere: {owner.name} added you as a trusted contact", text):
        channels.append("email")
    ok = bool(channels)
    contact.invite_channel = "+".join(channels) if ok else "none"
    if ok:
        contact.invite_sent_at = utcnow()
    log_event(db, owner.id, "CONSENT_REQUESTED" if ok else "CONSENT_REQUEST_FAILED",
              f"to {contact.name} via {contact.invite_channel}", contact_id=contact.id)
    return Outcome(contact.name, ok, contact.invite_channel, "" if ok else _why_failed(contact))
