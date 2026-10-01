import json
import unittest
from types import SimpleNamespace
from unittest import mock

from app.notifier import Fast2SmsNotifier, indian_mobile

CFG = SimpleNamespace(fast2sms_api_key="KEY")


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

    def test_foreign_number_is_skipped_without_a_request(self):
        with mock.patch("app.notifier.settings", CFG), mock.patch("urllib.request.urlopen") as opened:
            self.assertFalse(Fast2SmsNotifier().send_sms("+14155550123", "x"))
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
