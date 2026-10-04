"""
End-to-end API tests (need: pip install -r requirements.txt, then `pytest`).
They walk the full safety story: register -> contact consent -> journey -> overdue escalation
-> duress PIN -> authorization checks.
"""
import os
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_safesphere.db"
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Contact, Journey, utcnow
from app import scheduler
from app.routers import auth as auth_router
from app.notifier import ConsoleNotifier
import app.alerts as alerts_mod
import app.scheduler as scheduler_mod


class Outbox(ConsoleNotifier):
    def __init__(self): self.sent = []
    def send_sms(self, to, body): self.sent.append((to, body)); return True


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    box = Outbox()
    alerts_mod.notifier = box; scheduler_mod.notifier = box
    alerts_mod.emailer = None
    auth_router._limiter.reset()      # each test starts with a fresh login/register allowance
    with TestClient(app) as c:
        c.outbox = box
        yield c


def register(c, email="neha@example.com"):
    r = c.post("/auth/register", json={"name": "Neha", "email": email, "password": "supersecret1", "phone": "+919876543210"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def confirmed_contact(c, h, phone="+919000000001", email=None):
    payload = {"name": "Mom", "phone": phone}
    if email:
        payload["email"] = email
    cid = c.post("/contacts", json=payload, headers=h).json()["id"]
    with SessionLocal() as db:
        token = db.get(Contact, cid).view_token
    assert c.post(f"/c/{token}/confirm", follow_redirects=False).status_code == 303
    return cid, token


def eta(minutes):
    return (utcnow() + timedelta(minutes=minutes)).isoformat() + "Z"


def start(c, h, cid, minutes=30):
    r = c.post("/journeys", headers=h, json={"destination": "Airport", "expected_arrival_at": eta(minutes), "contact_ids": [cid]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_requires_auth(client):
    assert client.get("/contacts").status_code == 401


def test_unconfirmed_contact_cannot_be_used(client):
    h = register(client)
    cid = client.post("/contacts", json={"name": "Mom", "phone": "+919000000001"}, headers=h).json()["id"]
    r = client.post("/journeys", headers=h, json={"destination": "X", "expected_arrival_at": eta(30), "contact_ids": [cid]})
    assert r.status_code == 422


def test_arrive_safely_notifies_contact(client):
    h = register(client); cid, _ = confirmed_contact(client, h)
    jid = start(client, h, cid)
    assert client.post(f"/journeys/{jid}/arrive", headers=h, json={}).json()["status"] == "COMPLETED"
    assert any("arrived safely" in body for _, body in client.outbox.sent)
    assert client.get("/journeys/active", headers=h).json() is None


def test_overdue_journey_escalates_in_order(client):
    h = register(client); cid, _ = confirmed_contact(client, h)
    jid = start(client, h, cid, minutes=5)
    with SessionLocal() as db:
        db.get(Journey, jid).expected_arrival_at = utcnow() - timedelta(minutes=12)   # 12 min overdue
        db.commit()
    client.outbox.sent.clear()
    scheduler.tick()
    assert any("not confirmed arrival" in b for _, b in client.outbox.sent)
    scheduler.tick()   # idempotent: nothing is re-sent
    assert sum("not confirmed arrival" in b for _, b in client.outbox.sent) == 1


def test_duress_pin_looks_like_arrival_but_alerts(client):
    h = register(client); cid, _ = confirmed_contact(client, h)
    assert client.put("/auth/pins", headers=h, json={"safe_pin": "1234", "duress_pin": "4321"}).status_code == 204
    jid = start(client, h, cid)
    assert client.post(f"/journeys/{jid}/arrive", headers=h, json={"pin": "0000"}).status_code == 400
    r = client.post(f"/journeys/{jid}/arrive", headers=h, json={"pin": "4321"})
    assert r.json()["status"] == "COMPLETED"                       # looks normal to an onlooker
    assert any("SILENT ALERT" in b for _, b in client.outbox.sent)  # but contacts were warned
    assert client.get("/journeys/active", headers=h).json() is None


def test_other_users_cannot_read_my_journey(client):
    a = register(client); cid, _ = confirmed_contact(client, a); jid = start(client, a, cid)
    b = register(client, "eve@example.com")
    assert client.get(f"/journeys/{jid}", headers=b).status_code == 404
    assert client.post(f"/journeys/{jid}/arrive", headers=b, json={}).status_code == 404


def test_contact_page_shows_journey(client):
    h = register(client); cid, token = confirmed_contact(client, h); start(client, h, cid)
    page = client.get(f"/c/{token}").text
    assert "Airport" in page and "Neha" in page
    assert client.get("/c/not-a-real-token").status_code == 404


def test_emergency_without_confirmed_contacts_is_honest(client):
    h = register(client)
    r = client.post("/alerts/emergency", headers=h, json={})
    assert r.json()["delivered_to"] == 0


def test_whatsapp_invite_link(client):
    h = register(client)
    cid = client.post("/contacts", json={"name": "Mom", "phone": "+919000000001"}, headers=h).json()["id"]
    r = client.get(f"/contacts/{cid}/invite", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["whatsapp_url"].startswith("https://wa.me/919000000001?text=")
    assert "/c/" in body["link"]
    # another user must not be able to fetch this contact's private link
    other = register(client, "eve@example.com")
    assert client.get(f"/contacts/{cid}/invite", headers=other).status_code == 404
    # once confirmed there is nothing left to invite
    token = body["link"].rsplit("/", 1)[1]
    client.post(f"/c/{token}/confirm", follow_redirects=False)
    assert client.get(f"/contacts/{cid}/invite", headers=h).status_code == 409


def test_running_late_is_flexible_but_bounded(client):
    h = register(client); cid, _ = confirmed_contact(client, h); jid = start(client, h, cid, minutes=30)
    url = f"/journeys/{jid}/extend"
    assert client.post(url, headers=h, json={"minutes": 180}).status_code == 200   # any custom amount
    assert client.post(url, headers=h, json={"minutes": 4}).status_code == 422     # too small
    assert client.post(url, headers=h, json={"minutes": 721}).status_code == 422   # over 12 h at once
    for _ in range(3):                                                             # 210 -> 2370 min
        assert client.post(url, headers=h, json={"minutes": 720}).status_code == 200
    assert client.post(url, headers=h, json={"minutes": 720}).status_code == 422   # would pass 48 h


def test_no_provider_means_not_reported_as_delivered(client):
    h = register(client); confirmed_contact(client, h)
    alerts_mod.notifier = ConsoleNotifier()      # the real console notifier: logs only
    assert client.post("/alerts/emergency", headers=h, json={}).json()["delivered_to"] == 0


def test_arrived_safely_is_shown_to_the_contact(client):
    h = register(client); cid, token = confirmed_contact(client, h); jid = start(client, h, cid)
    client.post(f"/journeys/{jid}/arrive", headers=h, json={})
    assert "arrived safely" in client.get(f"/c/{token}").text


class FakeEmail:
    def __init__(self):
        self.sent = []

    def send_email(self, to, subject, body):
        self.sent.append((to, subject, body))
        return True


def test_invitation_is_emailed_when_contact_has_an_email(client):
    mail = FakeEmail(); alerts_mod.emailer = mail
    h = register(client)
    client.post("/contacts", json={"name": "Mom", "phone": "+919000000001", "email": "mom@example.com"}, headers=h)
    assert mail.sent and mail.sent[0][0] == "mom@example.com"
    assert "/c/" in mail.sent[0][2]


def test_email_is_the_fallback_when_sms_cannot_be_delivered(client):
    mail = FakeEmail(); alerts_mod.emailer = mail
    h = register(client); confirmed_contact(client, h, email="mom@example.com")
    alerts_mod.notifier = ConsoleNotifier()          # no SMS provider / refused
    mail.sent.clear()
    assert client.post("/alerts/emergency", headers=h, json={}).json()["delivered_to"] == 1
    assert mail.sent[0][0] == "mom@example.com"
    assert mail.sent[0][1].startswith("SafeSphere: EMERGENCY")


def test_sms_is_preferred_over_email_when_it_works(client):
    mail = FakeEmail(); alerts_mod.emailer = mail
    h = register(client); cid, _ = confirmed_contact(client, h, email="mom@example.com")
    mail.sent.clear(); client.outbox.sent.clear()
    start(client, h, cid)
    assert any("started a journey" in b for _, b in client.outbox.sent)
    assert not any("started a journey" in b for _, _, b in mail.sent)


def test_email_can_be_added_later_with_authorization(client):
    mail = FakeEmail(); alerts_mod.emailer = mail
    h = register(client)
    cid = client.post("/contacts", json={"name": "Mom", "phone": "+919000000001"}, headers=h).json()["id"]
    assert client.put(f"/contacts/{cid}/email", json={"email": "Mom@Example.com"}, headers=h).status_code == 204
    assert client.get("/contacts", headers=h).json()[0]["email"] == "mom@example.com"
    assert any(to == "mom@example.com" for to, _, _ in mail.sent)        # pending contact gets the invitation
    other = register(client, "eve@example.com")
    assert client.put(f"/contacts/{cid}/email", json={"email": "x@example.com"}, headers=other).status_code == 404
    assert client.put(f"/contacts/{cid}/email", json={"email": "not-an-email"}, headers=h).status_code == 422
