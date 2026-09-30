"""
SMS delivery behind a small interface.
 - ConsoleNotifier: prints the message (default; lets you demo with no account)
 - TwilioNotifier: real SMS through Twilio's REST API (stdlib only, no SDK)
"""
import base64
import logging
import urllib.parse
import urllib.request

from .config import settings

log = logging.getLogger("safesphere.notifier")


class ConsoleNotifier:
    def send_sms(self, to: str, body: str) -> bool:
        log.warning("[SMS -> %s] %s", to, body)
        return True


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
        except Exception as exc:  # network/provider errors must never crash the scheduler
            log.error("Twilio send failed: %s", exc)
            return False


def get_notifier():
    if settings.twilio_sid and settings.twilio_token and settings.twilio_from:
        return TwilioNotifier()
    return ConsoleNotifier()


notifier = get_notifier()
