from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import log_event, maps_link, send_to_contacts
from ..database import get_db
from ..deps import current_user
from ..escalation import Stage
from ..models import Consent, Contact, Journey, JourneyStatus, LocationPoint, User, utcnow
from ..schemas import (AlertIn, AlertOut, ArriveIn, ArriveOut, ExtendIn, JourneyIn,
                       JourneyOut, LocationIn, to_naive_utc)
from ..security import verify_secret

router = APIRouter(prefix="/journeys", tags=["journeys"])
LIVE = (JourneyStatus.ACTIVE.value, JourneyStatus.EMERGENCY.value)


def _owned(db: Session, user: User, journey_id: int) -> Journey:
    j = db.get(Journey, journey_id)
    if not j or j.owner_id != user.id:
        raise HTTPException(404, "Journey not found")
    return j


@router.post("", response_model=JourneyOut, status_code=201)
def start_journey(body: JourneyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    eta, now = to_naive_utc(body.expected_arrival_at), utcnow()
    if eta <= now:
        raise HTTPException(422, "Expected arrival must be in the future")
    if eta > now + timedelta(hours=48):
        raise HTTPException(422, "Journeys longer than 48 hours are not supported")

    already = db.scalar(select(Journey).where(
        Journey.owner_id == user.id, Journey.status.in_(LIVE), Journey.duress_triggered.is_(False)))
    if already:
        raise HTTPException(409, "You already have an active journey")

    ids = set(body.contact_ids)
    contacts = db.scalars(select(Contact).where(Contact.owner_id == user.id, Contact.id.in_(ids))).all()
    if len(contacts) != len(ids):
        raise HTTPException(422, "One or more contacts do not exist")
    if not any(c.consent == Consent.CONFIRMED.value for c in contacts):
        raise HTTPException(422, "None of the selected contacts has accepted your invitation yet")

    j = Journey(owner_id=user.id, destination=body.destination.strip(), expected_arrival_at=eta,
                share_location=body.share_location, contacts=list(contacts))
    db.add(j)
    db.flush()
    mins = int((eta - now).total_seconds() // 60)
    send_to_contacts(db, user, j.contacts,
                     f"{user.name} started a journey to {j.destination}, arriving in about {mins} min. "
                     f"You'll only be alerted if they don't check in.", "JOURNEY_STARTED", j)
    log_event(db, user.id, "JOURNEY_STARTED", j.destination, j.id)
    db.commit()
    return j


@router.get("/active", response_model=JourneyOut | None)
def active_journey(user: User = Depends(current_user), db: Session = Depends(get_db)):
    # duress-triggered journeys are hidden from the owner's app on purpose
    return db.scalar(select(Journey).where(
        Journey.owner_id == user.id, Journey.status.in_(LIVE), Journey.duress_triggered.is_(False)))


@router.get("/{journey_id}", response_model=JourneyOut)
def get_journey(journey_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _owned(db, user, journey_id)


@router.post("/{journey_id}/arrive", response_model=ArriveOut)
def arrive(journey_id: int, body: ArriveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, journey_id)
    if j.status not in LIVE:
        raise HTTPException(409, "Journey is not active")
    now = utcnow()

    duress = False
    if user.safe_pin_hash and user.duress_pin_hash:
        if not body.pin:
            raise HTTPException(400, "PIN required")
        # evaluate BOTH so response time doesn't reveal which PIN was entered
        is_duress = verify_secret(body.pin, user.duress_pin_hash)
        is_safe = verify_secret(body.pin, user.safe_pin_hash)
        if not (is_duress or is_safe):
            raise HTTPException(400, "Incorrect PIN")
        duress = is_duress

    if duress:
        # Response is identical to a normal arrival -- an onlooker sees "journey completed".
        j.status = JourneyStatus.EMERGENCY.value
        j.duress_triggered = True
        last = db.scalar(select(LocationPoint).where(LocationPoint.journey_id == j.id)
                         .order_by(LocationPoint.recorded_at.desc()))
        loc = maps_link(last.lat, last.lng) if last else ""
        send_to_contacts(db, user, j.contacts,
                         f"SILENT ALERT: {user.name} used their duress code on arrival at {j.destination}. "
                         f"They may be under pressure. Do NOT call them; consider contacting emergency services. {loc}",
                         "DURESS_ALERT", j, last.lat if last else None, last.lng if last else None)
        log_event(db, user.id, "DURESS", j.destination, j.id)
    else:
        j.status = JourneyStatus.COMPLETED.value
        j.completed_at = now
        for p in list(j.points):           # privacy: location history is deleted on safe arrival
            db.delete(p)
        send_to_contacts(db, user, j.contacts,
                         f"{user.name} arrived safely at {j.destination}.", "ARRIVED", j)
        log_event(db, user.id, "ARRIVED", j.destination, j.id)
    db.commit()
    return ArriveOut(status="COMPLETED", completed_at=now)


@router.post("/{journey_id}/extend", response_model=JourneyOut)
def extend(journey_id: int, body: ExtendIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, journey_id)
    if j.status != JourneyStatus.ACTIVE.value:
        raise HTTPException(409, "Journey is not active")
    j.expected_arrival_at += timedelta(minutes=body.minutes)
    if j.escalation_stage >= Stage.CONTACTS_ALERTED:
        send_to_contacts(db, user, j.contacts,
                         f"Update: {user.name} is OK but delayed. New arrival in about "
                         f"{max(int((j.expected_arrival_at - utcnow()).total_seconds() // 60), 0)} min.",
                         "DELAY_UPDATE", j)
    j.escalation_stage = int(Stage.NONE)
    log_event(db, user.id, "EXTENDED", f"+{body.minutes} min", j.id)
    db.commit()
    return j


@router.post("/{journey_id}/location", status_code=204)
def push_location(journey_id: int, body: LocationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, journey_id)
    if j.status not in LIVE or not j.share_location:
        raise HTTPException(409, "Location sharing is not enabled for this journey")
    db.add(LocationPoint(journey_id=j.id, lat=body.lat, lng=body.lng, accuracy=body.accuracy))
    db.commit()


@router.post("/{journey_id}/emergency", response_model=AlertOut)
def journey_emergency(journey_id: int, body: AlertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, journey_id)
    if j.status not in LIVE:
        raise HTTPException(409, "Journey is not active")
    j.status = JourneyStatus.EMERGENCY.value
    text = f"EMERGENCY: {user.name} needs help right now (journey to {j.destination}). {maps_link(body.lat, body.lng)}"
    delivered, skipped = send_to_contacts(db, user, j.contacts, text, "EMERGENCY_ALERT", j, body.lat, body.lng)
    log_event(db, user.id, "EMERGENCY_PRESSED", f"delivered={delivered}", j.id, body.lat, body.lng)
    db.commit()
    return AlertOut(delivered_to=delivered, skipped_unconfirmed=skipped)
