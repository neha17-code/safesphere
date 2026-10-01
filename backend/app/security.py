"""Password/PIN hashing (scrypt, stdlib), JWT tokens and a tiny rate limiter."""
import hashlib
import hmac
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(secret.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_secret(secret: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now,
               "exp": now + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")   # E.164, e.g. +919876543210
PIN_RE = re.compile(r"^\d{4,6}$")


class RateLimiter:
    """Sliding window, in-memory. Fine for one instance; use Redis when scaling out."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def reset(self) -> None:
        """Forget all hits (used by the test suite so tests don't throttle each other)."""
        self._hits.clear()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True
