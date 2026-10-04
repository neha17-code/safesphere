"""
Delivery channels behind small interfaces (stdlib only, no SDKs).
 - ConsoleNotifier : no SMS provider configured. Logs the text but reports NOT delivered,
                     so the app never claims an alert was sent when nothing left the server.
 - Fast2SmsNotifier: real SMS to Indian numbers through Fast2SMS (Quick SMS route).
 - TwilioNotifier  : real SMS through Twilio's REST API (works internationally).
 - BrevoEmail      : email over HTTPS (works where SMTP ports are blocked, e.g. Render free plan).
"""
import base64
import json
import logging
import urllib.error
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
                ok = 200 <= resp.status < 300 and data.get("return") is True
                if not ok:
                    log.error("Fast2SMS did not accept the message: %s", str(data.get("message"))[:300])
                return ok
        except urllib.error.HTTPError as exc:
            # Fast2SMS explains the refusal in the response body (bad key, wallet balance, number...).
            try:
                reason = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                reason = ""
            log.error("Fast2SMS rejected the request: HTTP %s %s", exc.code, reason)
            return False
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


class BrevoEmail:
    """Transactional email over HTTPS (port 443). Free plan: 300 emails/day, no card (Brevo's published terms)."""
    URL = "https://api.brevo.com/v3/smtp/email"

    def send_email(self, to: str, subject: str, body: str) -> bool:
        payload = json.dumps({
            "sender": {"name": settings.email_from_name, "email": settings.email_from},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": body,
        }).encode()
        req = urllib.request.Request(self.URL, data=payload, headers={
            "api-key": settings.brevo_api_key, "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            try:
                reason = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                reason = ""
            log.error("Brevo rejected the email: HTTP %s %s", exc.code, reason)
            return False
        except Exception as exc:  # never crash the scheduler, never log the key
            log.error("Brevo send failed: %s", type(exc).__name__)
            return False


def get_notifier():
    if settings.fast2sms_api_key:
        return Fast2SmsNotifier()
    if settings.twilio_sid and settings.twilio_token and settings.twilio_from:
        return TwilioNotifier()
    return ConsoleNotifier()


notifier = get_notifier()
emailer = BrevoEmail() if (settings.brevo_api_key and settings.email_from) else None
