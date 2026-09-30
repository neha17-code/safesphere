# Viva / interview Q&A: SafeSphere

## Concept
**Q: What problem does it solve?** Existing panic buttons need you to act while in danger. SafeSphere assumes you
may be unable to act: you declare a journey beforehand and *silence* triggers help.

**Q: What is unique?** Server-side escalation ladder, duress PIN, consent-first contacts, no-app contact view,
privacy-limited location, and an honest UI that reports real delivery.

## Architecture
**Q: Why a backend at all? The prototype worked locally.** Local notifications only ever reach the same phone.
A safety app must reach *another person* even if the phone is dead, so the decision to escalate lives on a server.

**Q: Why FastAPI?** Type-hint-driven validation (pydantic), automatic OpenAPI docs at /docs, async support, small code.

**Q: Why PostgreSQL / SQLAlchemy?** Relational data with ownership and many-to-many links (journeys to contacts),
transactions for alert bookkeeping. SQLAlchemy lets SQLite be used in dev and PostgreSQL in prod with no code change.

**Q: How does the scheduler work?** A background asyncio task calls `tick()` every 30 s in a thread. It selects ACTIVE
journeys whose ETA has passed, computes the target stage with the pure `target_stage()`, executes each pending stage
in order, and commits after every stage. Stage lives in the DB, so a restart never re-sends or skips an alert.

**Q: What if two server instances run?** `SELECT ... FOR UPDATE SKIP LOCKED` (PostgreSQL) lets each worker take
different rows, and the per-stage commit prevents duplicates.

**Q: What if the server was down for an hour?** `pending_transitions()` returns every missed stage in order, so alerts
still go out (never silently skipped).

## Security
**Q: How are passwords stored?** scrypt (memory-hard KDF, stdlib), random 16-byte salt per password, constant-time compare.
**Q: Authentication?** JWT (HS256) with expiry; the app keeps it in Android Keystore via flutter_secure_storage.
**Q: Authorization?** Every query filters by `owner_id`; foreign IDs return 404 (not 403) so IDs can't be enumerated.
**Q: How can a contact see data without an account?** A 32-byte random URL-safe token (`secrets.token_urlsafe`) in their
private link, unguessable, per contact, only valid once they've accepted. Page is `no-store`, `no-referrer`.
**Q: Brute force / enumeration?** Rate limiter on register/login; identical error for wrong email vs wrong password.
**Q: Injection / XSS?** SQLAlchemy parameterises queries; the HTML page escapes every user-supplied value with `html.escape`.
**Q: Weakness of PINs?** Small search space; see limitations. Mitigated by rate limits and DB access control.

## Duress PIN
**Q: How does it work?** After a journey, arrival asks for a PIN. Safe PIN completes it. Duress PIN returns the same
JSON (`COMPLETED`), the app shows the same screen, the journey is hidden from the owner's app (`duress_triggered`),
and contacts get "SILENT ALERT, do not call them". Both hashes are always verified so timing doesn't reveal which matched.
**Q: Downside?** An attacker who knows the feature may demand the PIN and check; it reduces but doesn't eliminate risk.

## Privacy & ethics
**Q: Could it be used for stalking?** Contacts must accept an SMS invitation, can decline, location is opt-in per journey
and deleted on safe arrival and after 24 h, and every alert is written to an audit log the user can view.
**Q: Why not call the police automatically?** Reliable automatic dispatch requires agreements with emergency services and
risks false alarms; the app says clearly it does not, and provides a one-tap 112 call instead.

## Code-level
**Q: Why pure `escalation.py`?** Deterministic, no clock or DB, so all timing rules are unit-tested (9 tests).
**Q: Why store times as UTC?** Avoids time-zone bugs; the prototype's hard-coded Asia/Kolkata broke elsewhere. The client
converts to local for display; local reminders are scheduled as absolute instants.
**Q: What bugs did you fix from the prototype?** Fake "will notify" alerts; ID collision (unsafe alert vs check-in, both 103);
defaults reappearing when the last contact was deleted; back-button losing the active journey; forgotten check-in state;
public lock-screen notifications; risky `USE_EXACT_ALARM` permission; stale journeys with no date.
**Q: How do you handle offline?** ApiClient maps timeouts/network errors to a clear message and never pretends success;
arrival and alerts are only marked done when the server confirms.
**Q: What would you do next?** Foreground-service location, FCM, Alembic, Redis rate limiting, iOS.

## Testing
**Q: How do you test?** Unit tests for escalation/security; API tests walk the story (consent, overdue escalation
idempotency, duress, cross-user access, honest zero-delivery emergency); Flutter model test.
