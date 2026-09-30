# SafeSphere: journey-based personal safety with automatic escalation

SafeSphere lets you start a journey, name the people who follow it, and go. If you do not confirm
arrival, **the server** (not your possibly-dead phone) escalates through a timed ladder and alerts your
contacts by SMS with a private live link.

| Part | Tech |
|---|---|
| Mobile app | Flutter (Android) |
| API | FastAPI, SQLAlchemy 2, JWT (PyJWT) |
| Database | PostgreSQL (SQLite for local dev) |
| Worker | asyncio background scheduler inside the API process |
| SMS | Twilio REST (or console logger for demos) |
| Contact view | Server-rendered web page, opened from an SMS link. No app or account needed |

## What makes it different

1. **Server-side escalation ladder.** Overdue journeys are handled by a backend worker, so alerts fire even if
   the phone is off, offline or destroyed. Stages: nudge user at ETA, alert priority-1 contacts after a grace
   period, escalate to everyone with urgent wording. Pure logic in `backend/app/escalation.py`, unit-tested.
2. **Duress PIN.** Confirming arrival asks for a PIN. The *safe* PIN completes the journey. The *duress* PIN shows the
   exact same "Journey Completed" screen but silently texts contacts. Server responses are identical, and both
   PINs are always checked so response time leaks nothing.
3. **Consent-first contacts.** A contact receives an SMS invitation and must accept before they can be alerted.
   Nobody can be added as a surveillance target without agreeing.
4. **Contacts need no app.** Their private link shows journey status, ETA and last location, and refreshes itself.
5. **Privacy by design.** Location is shared only if you enable it per journey, and is deleted on safe arrival
   and after 24h regardless. Lock-screen notifications hide the destination.
6. **Honest UI.** Emergency reports how many people were *actually* reached. If zero, it says so and offers a
   one-tap call to 112, rather than pretending an alert was sent.

## Architecture

```
Flutter app ──HTTPS/JSON + JWT──► FastAPI ──► PostgreSQL
                                     │  ▲
                 scheduler (30 s) ───┘  │
                                     │
                                     └──► SMS provider ──► Contact's phone ──► /c/<private-token> web page
```

```
backend/app/
  main.py         app + lifespan (creates tables, starts scheduler)
  config.py       environment settings
  database.py     engine / session
  models.py       User, Contact, Journey, LocationPoint, Event (+ journey_contacts link table)
  schemas.py      request/response validation (pydantic)
  security.py     scrypt hashing, JWT, rate limiter, regexes
  escalation.py   PURE escalation rules (no I/O)  <-- the core
  alerts.py       builds & sends SMS to CONFIRMED contacts, writes audit events
  notifier.py     Console / Twilio SMS adapters
  scheduler.py    background worker applying escalation stages
  deps.py         current_user dependency
  routers/        auth, contacts, journeys, alerts, public (contact web page)
mobile/lib/
  core/           config, ApiClient (JWT, timeouts, error parsing)
  models/         Contact, Journey
  services/       auth, contact, journey, location, notification
  screens/        auth, home, journey (setup + active), contacts, emergency, unsafe, settings
```

## Run it

### Backend (local)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
# API docs: http://localhost:8000/docs      SMS text appears in the terminal (console notifier)
```

### Deploy publicly (works for every contact, any network)
See `docs/DEPLOY.md` (Render blueprint in `render.yaml`).

### Backend (Docker + PostgreSQL)
```bash
cp backend/.env.example backend/.env && docker compose up --build
```

### Mobile
1. Copy `mobile/lib/**` over your existing `safety_app/lib/` (same file names are replaced; all old
   SharedPreferences-based services are superseded). Copy `mobile/test/models_test.dart` too
   and delete the old `test/widget_test.dart`, which expects the old home screen.
2. Apply `mobile/config_snippets/pubspec_dependencies.yaml` and `AndroidManifest_additions.xml`.
3. `flutter pub get`
4. Emulator: `flutter run` (default API `http://10.0.2.2:8000`).
   Real phone on the same Wi-Fi: `flutter run --dart-define=API_BASE_URL=http://<your-pc-ip>:8000`.

### Tests
```bash
cd backend
python -m unittest tests.test_escalation tests.test_security   # 17 tests, only PyJWT needed
pytest                                   # full API tests (after pip install -r requirements.txt)
cd ../mobile && flutter test
```

### 3-minute demo script
1. Register one user in the app. Add contact "Mom" (`+91...`). Copy the invite link from the server log.
2. Open the link in a browser, tap **Accept**. The app now shows Mom as green.
3. Settings, set safe PIN `1234` and duress PIN `4321`.
4. Start a journey due in 2 minutes and set `GRACE_MINUTES=1` in `.env`. Wait: watch the server log show the nudge, then the contact alert. Open Mom's link to see "overdue".
5. Second run: arrive with `1234` (contacts told "arrived safely"), then with `4321` (screen identical, log shows SILENT ALERT).

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | /auth/register, /auth/login | account + JWT |
| GET | /auth/me | profile (`has_pins`) |
| PUT | /auth/pins | set safe + duress PIN |
| GET/POST | /contacts | list / add (sends consent SMS) |
| POST | /contacts/{id}/resend | resend invitation |
| DELETE | /contacts/{id} | remove |
| POST | /journeys | start (confirmed contacts only) |
| GET | /journeys/active | resume after restart |
| POST | /journeys/{id}/arrive | confirm arrival (optional PIN) |
| POST | /journeys/{id}/extend | "running late" |
| POST | /journeys/{id}/location | push location (if enabled) |
| POST | /journeys/{id}/emergency | emergency during a journey |
| POST | /alerts/unsafe, /alerts/emergency | stand-alone alerts |
| GET | /alerts/events | audit trail |
| GET | /c/{token} | contact's web page (+ POST /confirm, /decline) |

## Limitations (be upfront about these)

- The API layer (`routers/`, `scheduler.py`) and the Flutter code were written carefully but **not executed** in
  the environment they were authored in (no network to install FastAPI/Flutter). The pure logic (escalation,
  hashing, JWT, validation, rate limiter) is unit-tested and passes. Run `pytest` and `flutter analyze` first
  and expect small fixes.
- Live location is sent only while the app is open (no Android foreground service yet).
- SMS is not push; delivery depends on the provider. Emergency services are **not** contacted automatically.
- A 4-6 digit PIN has a small search space: if the database leaked, PINs could be brute-forced offline.
  Mitigation: rate-limit, keep DB private; a production version could keep PIN verification on-device secure storage.
- The rate limiter is in-memory (single instance). Use Redis when scaling out.
- Tables are auto-created; a production deployment should use Alembic migrations, HTTPS via a reverse proxy,
  and secrets from a vault.

## Roadmap
Foreground-service tracking, FCM push for the user's own nudge, Alembic migrations, missed-check-in via
"shake to alert", iOS build, admin dashboard.
