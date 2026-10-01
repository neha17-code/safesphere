# Deploying SafeSphere so it works for every contact, on any network

A laptop can't be reached from other networks. Deploy the backend once to a public server and you get a
permanent `https://` address. Then:

* invitation links open on **any** phone, on Wi-Fi or mobile data;
* the app no longer needs your PC, USB or `adb reverse`;
* the escalation worker keeps running when your PC is off.

## 1. Put the project on GitHub
```powershell
cd C:\Users\nehaa\safesphere
git init
git add .
git commit -m "SafeSphere"
# create an EMPTY repo on github.com (e.g. safesphere), then:
git branch -M main
git remote add origin https://github.com/<your-username>/safesphere.git
git push -u origin main
```
`.gitignore` already excludes `.env`, `.venv` and `*.db`. Never commit secrets.

## 2. Deploy on Render (Blueprint)
1. Sign up at render.com with GitHub.
2. **New +  ->  Blueprint**, pick the `safesphere` repo. Render reads `render.yaml` and creates
   the API and a PostgreSQL database, wiring `DATABASE_URL` and a random `JWT_SECRET` for you.
3. Wait for the first deploy (a few minutes). Your address is shown on the service page:
   `https://safesphere-api.onrender.com` (yours may differ).
4. Open `<your-address>/health`. You should see `{"status":"ok"}`. Also try `<your-address>/docs`.

The address is also used automatically inside invitation links (`RENDER_EXTERNAL_URL`), so nothing else to configure.

## 3. Point the app at it
```powershell
cd C:\Users\nehaa\safety_app
flutter run --dart-define=API_BASE_URL=https://safesphere-api.onrender.com
```
No `adb reverse`, no same-Wi-Fi requirement. To install on a phone without a cable:
```powershell
flutter build apk --release --dart-define=API_BASE_URL=https://safesphere-api.onrender.com
```
The APK is in `build\app\outputs\flutter-apk\app-release.apk`. Send it to your phone and install it.
Contacts never need the app: they only open the link.

## 4. Real caveats (read before demoing or calling it "production")
Facts below were checked against Render's published information in Sept 2026; plans change, so re-check.

| Free-tier behaviour | Effect on SafeSphere |
|---|---|
| Free web services **sleep after ~15 min without traffic** and take ~30-60 s to wake | **The escalation worker sleeps too.** If your phone is dead and nobody hits the server, overdue alerts will NOT fire. The first request after sleep is also slow (the app allows 30 s). |
| Free PostgreSQL **expires after ~30 days** | Data is lost unless you upgrade or export/re-create it. |

What to do:
* **Demo / viva:** open the app and `/health` a minute before you present. While a journey screen is open the app
  contacts the server every minute, which keeps it awake. An external pinger (for example cron-job.org calling
  `/health` every 10 minutes) also works, but it is a workaround Render doesn't officially support.
* **Real use:** the whole promise ("we alert even if your phone is dead") requires an always-on server.
  Upgrade the web service to a paid instance (`plan: starter` in `render.yaml`, roughly US$7/month at the time of
  writing) and use a paid or independently hosted database (for example Neon or Supabase, or Render's paid Postgres).
  Any host that runs the Dockerfile works the same way (Railway, Fly.io, a VPS).

## 5. SMS to every contact (the universal channel)
Every phone receives SMS with no app and no account, so SMS is the primary alert channel.

**India: Fast2SMS** (confirmed against their API docs, Oct 2026)
1. Sign up at fast2sms.com. They advertise free starter credit; check current terms. Open **Dev API** and copy your key.
2. Render -> `safesphere-api` -> **Environment** -> add `FAST2SMS_API_KEY` = your key -> Save (never commit it).
3. After the redeploy, add a contact with a real `+91...` number, accept their invitation, and start a journey: an SMS arrives.

Things to know:
* SafeSphere uses Fast2SMS **Quick SMS** (free-text, no DLT template of your own). Fast2SMS describes it as suited to
  testing and internal alerts, and says business SMS to Indian numbers needs **DLT registration** (one-time TRAI rule,
  free help from Fast2SMS). Register on DLT before a public launch. Supporting the DLT route needs template support
  that SafeSphere does not implement yet.
* You pay per SMS from a wallet. Messages over 160 characters count as more than one SMS.
* Fast2SMS reaches **Indian mobiles only**. For other countries set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_FROM_NUMBER` instead (trial accounts only text verified numbers).
* **Honest reporting:** with no provider configured, messages are only logged and the app says "No one could be
  alerted" rather than pretending.

**Provider-free backup built into the app:** the Emergency screen has **SMS FROM MY PHONE**. It opens the phone's own
SMS app addressed to all saved contacts with your location link. It uses your SIM, works with no internet and no
provider, and needs one tap on Send. Contacts are saved on the phone after each successful load for this reason.

## 6. Security checklist before real users
HTTPS only (Render provides it), strong `JWT_SECRET` (auto-generated), database not public, rate limiting on
(uses real client IPs behind the proxy), Alembic migrations instead of auto-created tables, backups, and a privacy
policy that explains contacts, location and the audit log.

## 7. Optional extra: Telegram alerts (off unless you set a bot token)
1. In Telegram, open **@BotFather**, send `/newbot`, choose a name and a username ending in `bot`.
   BotFather replies with a **token**. Treat it like a password.
2. In Render: `safesphere-api` -> **Environment** -> add `TELEGRAM_BOT_TOKEN` = that token -> Save.
   Render redeploys. Never put the token in GitHub.
3. On startup the server finds the bot's username and registers its webhook automatically
   (look for `Telegram webhook registered: True` in the Logs tab).
4. A contact accepts your invitation, then taps **Connect Telegram** on their page. Telegram opens, they press
   **Start**, and the bot replies "Connected". From then on every journey update and alert reaches them as a
   Telegram notification. Telegram retries webhooks for a while, so linking still works if the free server was asleep.

Telegram is only an *extra*: not everyone has it, so SMS stays the main channel. Without `TELEGRAM_BOT_TOKEN` the
Telegram button never appears. Delivery order per contact: Telegram (only if that contact connected it), then SMS.
