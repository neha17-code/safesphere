import io
import json
import sys
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from app.notifier import BrevoEmail, Fast2SmsNotifier, WebPusher, indian_mobile

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


class BrevoLastError(unittest.TestCase):
    def test_last_error_keeps_status_and_reason_but_not_the_key(self):
        cfg = SimpleNamespace(brevo_api_key="SECRETKEY", email_from="me@x.com", email_from_name="SafeSphere")
        err = urllib.error.HTTPError("https://x", 401, "no", {}, io.BytesIO(b'{"message":"unrecognised IP address"}'))
        mailer = BrevoEmail()
        with mock.patch("app.notifier.settings", cfg), mock.patch("urllib.request.urlopen", side_effect=err):
            self.assertFalse(mailer.send_email("a@b.com", "S", "B"))
        self.assertIn("401", mailer.last_error)
        self.assertIn("unrecognised IP address", mailer.last_error)
        self.assertNotIn("SECRETKEY", mailer.last_error)
        with mock.patch("app.notifier.settings", cfg), mock.patch("urllib.request.urlopen", return_value=FakeResp()):
            self.assertTrue(mailer.send_email("a@b.com", "S", "B"))
        self.assertEqual(mailer.last_error, "")


class WebPush(unittest.TestCase):
    CFG = SimpleNamespace(vapid_private_key="PRIV", vapid_subject="mailto:a@b.c")
    SUB = {"endpoint": "https://push.example/x", "keys": {"p256dh": "p", "auth": "a"}}

    @staticmethod
    def _module(side_effect=None):
        class WebPushException(Exception):
            def __init__(self, status):
                super().__init__("push failed")
                self.status_code = status
        return SimpleNamespace(webpush=mock.Mock(side_effect=side_effect), WebPushException=WebPushException)

    def _send(self, module):
        with mock.patch("app.notifier.settings", self.CFG), mock.patch.dict(sys.modules, {"pywebpush": module}):
            return WebPusher().send(self.SUB, {"title": "T", "body": "B", "url": "https://x/c/t"}, ttl=600)

    def test_success_sends_the_payload_signed_with_our_key(self):
        module = self._module()
        self.assertEqual(self._send(module), "ok")
        kwargs = module.webpush.call_args.kwargs
        self.assertEqual(kwargs["subscription_info"], self.SUB)
        self.assertEqual(kwargs["vapid_private_key"], "PRIV")
        self.assertEqual(kwargs["vapid_claims"], {"sub": "mailto:a@b.c"})
        self.assertEqual(kwargs["ttl"], 600)
        self.assertEqual(json.loads(kwargs["data"])["title"], "T")

    def test_expired_subscription_is_reported_as_gone(self):
        module = self._module()
        module.webpush.side_effect = module.WebPushException(410)
        self.assertEqual(self._send(module), "gone")

    def test_other_push_service_errors_are_a_failure_not_a_removal(self):
        module = self._module()
        module.webpush.side_effect = module.WebPushException(500)
        self.assertEqual(self._send(module), "fail")

    def test_unexpected_error_never_raises(self):
        self.assertEqual(self._send(self._module(side_effect=OSError("down"))), "fail")

    def test_missing_library_disables_push_instead_of_crashing(self):
        with mock.patch("app.notifier.settings", self.CFG), mock.patch.dict(sys.modules, {"pywebpush": None}):
            self.assertEqual(WebPusher().send(self.SUB, {}), "fail")


if __name__ == "__main__":
    unittest.main()
