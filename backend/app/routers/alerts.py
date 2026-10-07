"""Stand-alone alerts (not tied to a journey) + the user's own audit trail."""
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import log_event, maps_link, notify_contacts
from ..database import get_db
from ..deps import current_user
from ..models import Contact, Event, Journey, JourneyStatus, User
from ..schemas import AlertIn, AlertOut, EventOut, OutcomeOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _targets(db: Session, user: User, ids: list[int] | None) -> list[Contact]:
    q = select(Contact).where(Contact.owner_id == user.id)
    if ids:
        q = q.where(Contact.id.in_(ids))
    return list(db.scalars(q.order_by(Contact.priority)).all())


def _alert_out(outcomes) -> AlertOut:
    return AlertOut(delivered_to=sum(o.ok for o in outcomes),
                    skipped_unconfirmed=sum(o.reason == "NOT_ACCEPTED" for o in outcomes),
                    results=[OutcomeOut(**asdict(o)) for o in outcomes])


@router.post("/unsafe", response_model=AlertOut)
def unsafe(body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    text = (f"{user.name} feels unsafe and wanted you to know. This is NOT an emergency yet. "
            f"{body.message or ''} {maps_link(body.lat, body.lng)}").strip()
    outcomes = notify_contacts(db, user, _targets(db, user, body.contact_ids), text,
                               "UNSAFE_ALERT", None, body.lat, body.lng)
    db.commit()
    return _alert_out(outcomes)


@router.post("/emergency", response_model=AlertOut)
def emergency(body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    text = f"EMERGENCY: {user.name} needs help right now. {body.message or ''} {maps_link(body.lat, body.lng)}".strip()
    outcomes = notify_contacts(db, user, _targets(db, user, body.contact_ids), text,
                               "EMERGENCY_ALERT", None, body.lat, body.lng)
    delivered = sum(o.ok for o in outcomes)
    for j in db.scalars(select(Journey).where(Journey.owner_id == user.id,
                                              Journey.status == JourneyStatus.ACTIVE.value)):
        j.status = JourneyStatus.EMERGENCY.value
    log_event(db, user.id, "EMERGENCY_PRESSED", f"delivered={delivered}", None, body.lat, body.lng)
    db.commit()
    return _alert_out(outcomes)


@router.get("/events", response_model=list[EventOut])
def events(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Event).where(Event.owner_id == user.id, ~Event.type.like("DURESS%"))
                      .order_by(Event.created_at.desc()).limit(50)).all()
