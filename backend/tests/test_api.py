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
    with TestClient(app) as c:
        c.outbox = box
        yield c


def register(c, email="neha@example.com"):
    r = c.post("/auth/register", json={"name": "Neha", "email": email, "password": "supersecret1", "phone": "+919876543210"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def confirmed_contact(c, h, phone="+919000000001"):
    cid = c.post("/contacts", json={"name": "Mom", "phone": phone}, headers=h).json()["id"]
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
