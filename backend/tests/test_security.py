import unittest

from app.security import (PHONE_RE, PIN_RE, RateLimiter, create_access_token,
                          decode_access_token, hash_secret, verify_secret)


class Hashing(unittest.TestCase):
    def test_roundtrip(self):
        h = hash_secret("correct horse")
        self.assertTrue(verify_secret("correct horse", h))
        self.assertFalse(verify_secret("wrong", h))

    def test_salted(self):
        self.assertNotEqual(hash_secret("same"), hash_secret("same"))

    def test_garbage_hash_is_rejected_not_crashed(self):
        self.assertFalse(verify_secret("x", "not-a-hash"))
        self.assertFalse(verify_secret("x", None))


class Tokens(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(decode_access_token(create_access_token(42)), 42)

    def test_tampered_token_rejected(self):
        self.assertIsNone(decode_access_token(create_access_token(42) + "x"))


class Validation(unittest.TestCase):
    def test_phone(self):
        self.assertTrue(PHONE_RE.match("+919876543210"))
        self.assertFalse(PHONE_RE.match("9876543210"))

    def test_pin(self):
        self.assertTrue(PIN_RE.match("1234"))
        self.assertFalse(PIN_RE.match("12"))
        self.assertFalse(PIN_RE.match("12ab"))


class Limiter(unittest.TestCase):
    def test_blocks_after_limit(self):
        rl = RateLimiter(3, 60)
        self.assertEqual([rl.allow("k") for _ in range(4)], [True, True, True, False])
        self.assertTrue(rl.allow("other"))


if __name__ == "__main__":
    unittest.main()
