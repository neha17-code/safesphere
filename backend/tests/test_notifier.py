import io
import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from app.notifier import BrevoEmail, Fast2SmsNotifier, indian_mobile

CFG = SimpleNamespace(fast2sms_api_key="KEY")
MAIL_CFG = SimpleNamespace(brevo_api_key="BKEY", email_from="alerts@example.com", email_from_name="SafeSphere")


class FakeResp:
    def __init__(self, status=200, body=b'{"return": true, "message": ["ok"]}'):
        self.status, self._body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class IndianMobile(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(indian_mobile("+919876543210"), "9876543210")

    def test_rejects_non_indian_or_malformed(self):
        for bad in ("+14155550123", "9876543210", "+911234567890", "+91987654321", "+91987654321x"):
            self.assertIsNone(indian_mobile(bad), bad)


class Fast2Sms(unittest.TestCase):
    def test_request_shape(self):
        with mock.patch("app.notifier.settings", CFG), \
             mock.patch("urllib.request.urlopen", return_value=FakeResp()) as opened:
            self.assertTrue(Fast2SmsNotifier().send_sms("+919876543210", "hello"))
        req = opened.call_args[0][0]
        self.assertEqual(req.full_url, "https://www.fast2sms.com/dev/bulkV2")
        self.assertEqual(req.get_header("Authorization"), "KEY")
        self.assertEqual(json.loads(req.data), {"route": "q", "message": "hello", "numbers": "9876543210"})

    def test_provider_says_failure(self):
        with mock.patch("app.notifier.settings", CFG), \
             mock.patch("urllib.request.urlopen", return_value=FakeResp(body=b'{"return": false}')):
            self.assertFalse(Fast2SmsNotifier().send_sms("+919876543210", "x"))

    def test_network_error_is_not_delivery_and_does_not_raise(self):
        with mock.patch("app.notifier.settings", CFG), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(Fast2SmsNotifier().send_sms("+919876543210", "x"))

    def test_http_error_logs_status_and_providers_reason_but_never_the_key(self):
        err = urllib.error.HTTPError("https://x", 412, "bad", {}, io.BytesIO(b'{"message":"Invalid Authentication"}'))
        with mock.patch("app.notifier.settings", CFG), mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertLogs("safesphere.notifier", level="ERROR") as logs:
                self.assertFalse(Fast2SmsNotifier().send_sms("+919876543210", "x"))
        text = "\n".join(logs.output)
        self.assertIn("412", text)
        self.assertIn("Invalid Authentication", text)
        self.assertNotIn("KEY", text)

    def test_foreign_number_is_skipped_without_a_request(self):
        with mock.patch("app.notifier.settings", CFG), mock.patch("urllib.request.urlopen") as opened:
            self.assertFalse(Fast2SmsNotifier().send_sms("+14155550123", "x"))
        opened.assert_not_called()


class Brevo(unittest.TestCase):
    def test_request_shape(self):
        with mock.patch("app.notifier.settings", MAIL_CFG), \
             mock.patch("urllib.request.urlopen", return_value=FakeResp(201, b'{"messageId": "x"}')) as opened:
            self.assertTrue(BrevoEmail().send_email("mom@example.com", "Subj", "Body"))
        req = opened.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(req.get_header("Api-key"), "BKEY")
        self.assertEqual(json.loads(req.data), {
            "sender": {"name": "SafeSphere", "email": "alerts@example.com"},
            "to": [{"email": "mom@example.com"}],
            "subject": "Subj",
            "textContent": "Body",
        })

    def test_http_error_logs_reason_but_never_the_key(self):
        err = urllib.error.HTTPError("https://x", 401, "no", {}, io.BytesIO(b'{"message":"Key not found"}'))
        with mock.patch("app.notifier.settings", MAIL_CFG), mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertLogs("safesphere.notifier", level="ERROR") as logs:
                self.assertFalse(BrevoEmail().send_email("mom@example.com", "S", "B"))
        text = "\n".join(logs.output)
        self.assertIn("401", text)
        self.assertIn("Key not found", text)
        self.assertNotIn("BKEY", text)

    def test_network_error_is_not_delivery_and_does_not_raise(self):
        with mock.patch("app.notifier.settings", MAIL_CFG), mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(BrevoEmail().send_email("mom@example.com", "S", "B"))


if __name__ == "__main__":
    unittest.main()
