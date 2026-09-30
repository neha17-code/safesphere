"""
Contact-facing web page. No app or account needed: the private link in the SMS is the credential.
Consent flow: PENDING -> (contact taps Accept) -> CONFIRMED. Alerts are only ever sent to CONFIRMED contacts.
"""
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts import log_event, maps_link
from ..database import get_db
from ..models import Consent, Contact, Event, JourneyStatus, LocationPoint, User, utcnow

router = APIRouter(prefix="/c", tags=["contact-view"], include_in_schema=False)

CSS = ("body{font-family:system-ui,sans-serif;max-width:480px;margin:24px auto;padding:0 16px;color:#1c1c1e}"
       ".card{border:1px solid #ddd;border-radius:14px;padding:16px;margin:12px 0}"
       ".bad{border-color:#d33;background:#fff0f0}.ok{border-color:#2a7;background:#effaf3}"
       "button{font-size:16px;padding:12px 18px;border-radius:10px;border:0;margin-right:8px}"
       ".yes{background:#1a7f4b;color:#fff}.no{background:#eee}")


def _page(body: str, refresh: bool = False) -> HTMLResponse:
    meta = '<meta http-equiv="refresh" content="30">' if refresh else ""
    return HTMLResponse(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        f'{meta}<title>SafeSphere</title><style>{CSS}</style>{body}',
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def _contact(db: Session, token: str) -> Contact:
    c = db.scalar(select(Contact).where(Contact.view_token == token))
    if not c:
        raise HTTPException(404, "This link is not valid")
    return c


@router.get("/{token}", response_class=HTMLResponse)
def view(token: str, db: Session = Depends(get_db)):
    c = _contact(db, token)
    owner = db.get(User, c.owner_id)
    who = escape(owner.name)

    if c.consent == Consent.PENDING.value:
        return _page(f'<h2>SafeSphere</h2><div class="card"><b>{who}</b> would like to add you as a trusted contact.'
                     f'<p>You will only receive a message if they may need help. You can stop at any time.</p>'
                     f'<form method="post" action="/c/{escape(token)}/confirm" style="display:inline">'
                     f'<button class="yes">Accept</button></form>'
                     f'<form method="post" action="/c/{escape(token)}/decline" style="display:inline">'
                     f'<button class="no">Decline</button></form></div>')
    if c.consent == Consent.DECLINED.value:
        return _page(f'<h2>SafeSphere</h2><p>You declined to be a contact for {who}. No alerts will be sent.</p>')

    now, parts = utcnow(), []
    for j in c.journeys:
        if j.status not in (JourneyStatus.ACTIVE.value, JourneyStatus.EMERGENCY.value):
            continue
        mins = int((j.expected_arrival_at - now).total_seconds() // 60)
        timing = f"arriving in ~{mins} min" if mins >= 0 else f"<b>{-mins} min overdue</b>"
        loc = ""
        if j.share_location:
            last = db.scalar(select(LocationPoint).where(LocationPoint.journey_id == j.id)
                             .order_by(LocationPoint.recorded_at.desc()))
            if last:
                ago = int((now - last.recorded_at).total_seconds() // 60)
                loc = f'<p><a href="{escape(maps_link(last.lat, last.lng))}">Last location</a> ({ago} min ago)</p>'
        bad = j.status == JourneyStatus.EMERGENCY.value or j.escalation_stage >= 2
        parts.append(f'<div class="card {"bad" if bad else "ok"}"><b>{who}</b> → {escape(j.destination)}<br>'
                     f'{timing}<br>Status: {escape(j.status)}{loc}</div>')

    alert = db.scalar(select(Event).where(Event.owner_id == owner.id, Event.contact_id == c.id,
                                          Event.type.in_(("EMERGENCY_ALERT", "UNSAFE_ALERT")))
                      .order_by(Event.created_at.desc()))
    if alert and (now - alert.created_at).total_seconds() < 6 * 3600:
        link = f' <a href="{escape(maps_link(alert.lat, alert.lng))}">Location</a>' if alert.lat is not None else ""
        parts.append(f'<div class="card bad"><b>Latest alert:</b> {escape(alert.type.replace("_", " ").title())}{link}</div>')

    body = "".join(parts) or f"<p>{who} has no active journey right now. You're all set.</p>"
    return _page(f"<h2>SafeSphere</h2>{body}<p style='color:#777;font-size:13px'>This page refreshes every 30 seconds.</p>", refresh=True)


def _set_consent(db: Session, token: str, value: Consent):
    c = _contact(db, token)
    c.consent = value.value
    log_event(db, c.owner_id, f"CONSENT_{value.value}", f"{c.name}", contact_id=c.id)
    db.commit()
    return RedirectResponse(f"/c/{token}", status_code=303)


@router.post("/{token}/confirm")
def confirm(token: str, db: Session = Depends(get_db)):
    return _set_consent(db, token, Consent.CONFIRMED)


@router.post("/{token}/decline")
def decline(token: str, db: Session = Depends(get_db)):
    return _set_consent(db, token, Consent.DECLINED)
