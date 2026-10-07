"""
Contact-facing web page. No app or account needed: the private link in the SMS is the credential.
Consent flow: PENDING -> (contact taps Accept) -> CONFIRMED. Alerts are only ever sent to CONFIRMED contacts.
"""
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts as alerts_mod
from ..alerts import log_event, maps_link
from ..config import settings
from ..database import get_db
from ..models import Consent, Contact, Event, JourneyStatus, LocationPoint, PushSubscription, User, utcnow

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


SW_JS = """self.addEventListener('push', function (e) {
  var d = {title: 'SafeSphere', body: '', url: '/'};
  try { d = Object.assign(d, e.data.json()); } catch (err) {}
  e.waitUntil(self.registration.showNotification(d.title, {
    body: d.body,
    data: {url: d.url},
    requireInteraction: /EMERGENCY|SILENT|URGENT/.test(d.title)
  }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url));
});
"""

PUSH_CARD = """<div class="card" id="pushcard"><b>Get alerts on this phone</b>
<p id="pushmsg">Turn on notifications to be alerted instantly, even when this page is closed.</p>
<button class="yes" type="button" id="pushbtn">Turn on notifications</button></div>
<script>
var KEY='__KEY__', TOKEN='__TOKEN__';
function b64(s){var p='='.repeat((4-s.length%4)%4),r=(s+p).replace(/-/g,'+').replace(/_/g,'/'),raw=atob(r),o=new Uint8Array(raw.length);for(var i=0;i<raw.length;i++)o[i]=raw.charCodeAt(i);return o;}
var msg=document.getElementById('pushmsg'), btn=document.getElementById('pushbtn');
async function state(){
  if(!('serviceWorker' in navigator)||!('PushManager' in window)){
    msg.textContent='This browser cannot receive notifications. On iPhone, add this page to the Home Screen first (Share, then Add to Home Screen) and open it from there.';
    btn.style.display='none'; return;}
  var reg=await navigator.serviceWorker.getRegistration('/c/');
  var sub=reg&&await reg.pushManager.getSubscription();
  if(sub&&Notification.permission==='granted'){msg.textContent='Notifications are ON for this device.';btn.style.display='none';}
}
btn.onclick=async function(){
  try{
    var perm=await Notification.requestPermission();
    if(perm!=='granted'){msg.textContent='Notifications are blocked. Allow them in your browser settings, then try again.';return;}
    var reg=await navigator.serviceWorker.register('/c/sw.js',{scope:'/c/'});
    await navigator.serviceWorker.ready;
    var sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64(KEY)});
    var r=await fetch('/c/'+TOKEN+'/push',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sub.toJSON())});
    if(r.ok){msg.textContent='Done! Notifications are ON for this device.';btn.style.display='none';}
    else{msg.textContent='Could not turn on notifications (error '+r.status+').';}
  }catch(e){msg.textContent='Could not turn on notifications: '+e.message;}
};
state();
</script>"""


class PushIn(BaseModel):
    endpoint: str = Field(max_length=600)
    keys: dict[str, str]


@router.get("/sw.js")
def service_worker():
    """Must be defined BEFORE /{token}, otherwise 'sw.js' would be read as a contact token."""
    return Response(SW_JS, media_type="application/javascript",
                    headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/c/"})


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

    # recently completed journeys: reassure the contact instead of silently showing "nothing"
    for j in c.journeys:
        if j.status == JourneyStatus.COMPLETED.value and j.completed_at and (now - j.completed_at).total_seconds() < 3 * 3600:
            ago = int((now - j.completed_at).total_seconds() // 60)
            parts.append(f'<div class="card ok"><b>{who}</b> arrived safely at {escape(j.destination)} ({ago} min ago)</div>')

    body = "".join(parts) or f"<p>{who} has no active journey right now. You're all set.</p>"
    if settings.vapid_public_key:
        body += PUSH_CARD.replace("__KEY__", escape(settings.vapid_public_key)).replace("__TOKEN__", escape(token))
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


@router.post("/{token}/push", status_code=204)
def subscribe(token: str, sub: PushIn, db: Session = Depends(get_db)):
    """The contact tapped 'Turn on notifications': remember this device so alerts can pop up on it."""
    c = _contact(db, token)
    if c.consent != Consent.CONFIRMED.value:
        raise HTTPException(403, "Accept the invitation first")
    p256dh, auth = sub.keys.get("p256dh"), sub.keys.get("auth")
    if not p256dh or not auth or not sub.endpoint.startswith("https://"):
        raise HTTPException(422, "Invalid subscription")
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint))
    if existing:
        existing.contact_id, existing.p256dh, existing.auth = c.id, p256dh, auth
    else:
        db.add(PushSubscription(contact_id=c.id, endpoint=sub.endpoint, p256dh=p256dh, auth=auth))
    log_event(db, c.owner_id, "PUSH_ENABLED", c.name, contact_id=c.id)
    db.commit()
    db.refresh(c)
    owner = db.get(User, c.owner_id)
    # a visible test message, so the contact (and the owner) can see that it really works
    alerts_mod.push_to_contact(db, c, "SafeSphere", f"Notifications are on. You'll be alerted here if {owner.name} may need help.", ttl=300)
    db.commit()
