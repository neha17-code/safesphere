"""
Delivery channels behind small interfaces (stdlib only, no SDKs).
 - ConsoleNotifier : no SMS provider configured. Logs the text but reports NOT delivered,
                     so the app never claims an alert was sent when nothing left the server.
 - Fast2SmsNotifier: real SMS to Indian numbers through Fast2SMS (Quick SMS route).
 - TwilioNotifier  : real SMS through Twilio's REST API (works internationally).
 - TelegramClient  : free push-style messages to a contact who connected the SafeSphere bot.
"""
import base64
import json
import logging
import urllib.parse
import urllib.request

from .config import settings

log = logging.getLogger("safesphere.notifier")


class ConsoleNotifier:
    def send_sms(self, to: str, body: str) -> bool:
        log.warning("[SMS -> %s] %s   (NOT delivered: no SMS provider configured)", to, body)
        return False


def indian_mobile(phone: str) -> str | None:
    """'+919876543210' -> '9876543210'. Fast2SMS only reaches Indian 10-digit mobile numbers."""
    digits = phone.lstrip("+")
    if phone.startswith("+91") and len(digits) == 12 and digits.isdigit() and digits[2] in "6789":
        return digits[2:]
    return None


class Fast2SmsNotifier:
    """SMS to Indian numbers via Fast2SMS 'Quick SMS' (route q: free text, no own DLT template needed)."""
    URL = "https://www.fast2sms.com/dev/bulkV2"

    def send_sms(self, to: str, body: str) -> bool:
        number = indian_mobile(to)
        if number is None:
            log.warning("Fast2SMS reaches Indian mobiles only; skipped %s", to)
            return False
        payload = json.dumps({"route": "q", "message": body, "numbers": number}).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={
            "Authorization": settings.fast2sms_api_key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read() or b"{}")
                return 200 <= resp.status < 300 and data.get("return") is True
        except Exception as exc:  # provider errors must never crash the scheduler
            log.error("Fast2SMS send failed: %s", type(exc).__name__)
            return False


class TwilioNotifier:
    def send_sms(self, to: str, body: str) -> bool:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_sid}/Messages.json"
        data = urllib.parse.urlencode({"To": to, "From": settings.twilio_from, "Body": body}).encode()
        req = urllib.request.Request(url, data=data)
        auth = base64.b64encode(f"{settings.twilio_sid}:{settings.twilio_token}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception as exc:  # provider errors must never crash the scheduler
            log.error("Twilio send failed: %s", type(exc).__name__)
            return False


class TelegramClient:
    def __init__(self, token: str, username: str = ""):
        self.token = token
        self.username = username

    def _call(self, method: str, payload: dict) -> dict | None:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # never log the URL: it contains the bot token
            log.error("Telegram %s failed: %s", method, type(exc).__name__)
            return None

    def send_message(self, chat_id: str, text: str) -> bool:
        res = self._call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})
        return bool(res and res.get("ok"))

    def set_webhook(self, url: str, secret: str) -> bool:
        res = self._call("setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"]})
        return bool(res and res.get("ok"))

    def load_username(self) -> None:
        res = self._call("getMe", {})
        if res and res.get("ok"):
            self.username = res["result"].get("username", "")


def get_notifier():
    if settings.fast2sms_api_key:
        return Fast2SmsNotifier()
    if settings.twilio_sid and settings.twilio_token and settings.twilio_from:
        return TwilioNotifier()
    return ConsoleNotifier()


notifier = get_notifier()
telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_bot_username) \
    if settings.telegram_bot_token else None
