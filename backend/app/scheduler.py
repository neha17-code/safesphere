"""
Background escalation worker. Every N seconds it looks at active journeys and executes
any escalation stage that is due. Stage is stored on the journey, so a restart never
re-sends an alert and never skips one (see escalation.pending_transitions).
"""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, select

from . import alerts as alerts_mod
from .alerts import log_event, send_to_contacts
from .config import settings
from .database import SessionLocal
from .escalation import Policy, Stage, pending_transitions, target_stage
from .progress import progress_due, progress_text
from .models import Journey, JourneyStatus, LocationPoint, User, utcnow
from .notifier import notifier

log = logging.getLogger("safesphere.scheduler")


def policy() -> Policy:
    return Policy(timedelta(minutes=settings.grace_minutes), timedelta(minutes=settings.second_level_minutes))


def _apply(db, j: Journey, owner: User, stage: Stage) -> None:
    if stage == Stage.NUDGED:
        if owner.phone:
            notifier.send_sms(owner.phone, f"SafeSphere: you were due at {j.destination}. Open the app and confirm you're safe.")
        log_event(db, owner.id, "NUDGED", j.destination, j.id)
    elif stage == Stage.CONTACTS_ALERTED:
        first = [c for c in j.contacts if c.priority == 1] or list(j.contacts)
        send_to_contacts(db, owner, first,
                         f"{owner.name} has not confirmed arrival at {j.destination} and is overdue. Please try to reach them.",
                         "CONTACTS_ALERTED", j)
    elif stage == Stage.ESCALATED:
        send_to_contacts(db, owner, list(j.contacts),
                         f"URGENT: {owner.name} is still unreachable and overdue for {j.destination}. "
                         f"If you cannot reach them, consider calling emergency services (112).",
                         "ESCALATED", j)


def tick() -> None:
    now, pol = utcnow(), policy()
    with SessionLocal() as db:
        due = db.scalars(select(Journey).where(Journey.status == JourneyStatus.ACTIVE.value,
                                               Journey.expected_arrival_at <= now)
                         .with_for_update(skip_locked=True)).all()   # safe with several workers on PostgreSQL
        for j in due:
            owner = db.get(User, j.owner_id)
            for stage in pending_transitions(Stage(j.escalation_stage), target_stage(j.expected_arrival_at, now, pol)):
                _apply(db, j, owner, stage)
                j.escalation_stage = int(stage)
                db.commit()                                          # commit per stage: never double-send
        if settings.progress_update_minutes > 0 and alerts_mod.pusher is not None:
            interval = timedelta(minutes=settings.progress_update_minutes)
            for j in db.scalars(select(Journey).where(Journey.status == JourneyStatus.ACTIVE.value)).all():
                if progress_due(j.last_progress_at or j.created_at, now, interval):
                    owner = db.get(User, j.owner_id)
                    mins = int((j.expected_arrival_at - now).total_seconds() // 60)
                    alerts_mod.push_progress(db, owner, j, progress_text(owner.name, j.destination, mins))
                    j.last_progress_at = now
                    db.commit()
        cutoff = now - timedelta(hours=settings.location_retention_hours)
        db.execute(delete(LocationPoint).where(LocationPoint.recorded_at < cutoff))
        db.commit()


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(settings.scheduler_interval_seconds)
