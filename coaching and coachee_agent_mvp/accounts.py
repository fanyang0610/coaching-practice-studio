"""Passwords, login cookies, CSRF tokens, login throttling and transcript visibility rules."""

from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import secrets
import threading
import time


ROLES = ("user", "trainer", "admin")
MIN_PASSWORD_LENGTH = 10
SESSION_COOKIE = "erickson_session"
SESSION_DAYS = 14

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def password_problem(password: str, confirm: str | None = None) -> str | None:
    """Return a message key when the password isn't acceptable, else None."""
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return "password_too_short"
    if confirm is not None and password != confirm:
        return "password_mismatch"
    return None


def _sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def make_session_cookie(user: dict, secret: str, now: float | None = None) -> str:
    """user_id.expiry.signature. The signature covers part of the password hash, so a password change logs out old sessions."""
    expires = int((now or time.time()) + SESSION_DAYS * 86400)
    payload = f"{user['id']}.{expires}"
    return f"{payload}.{_sign(secret, payload + '.' + user['password_hash'][-24:])}"


def read_session_cookie(value: str | None, secret: str, get_user, now: float | None = None) -> dict | None:
    """Return the active user a cookie belongs to, or None."""
    try:
        user_id, expires, signature = (value or "").split(".")
        if int(expires) < (now or time.time()):
            return None
        user = get_user(int(user_id))
    except (ValueError, TypeError):
        return None
    if not user or user["status"] != "active":
        return None
    expected = _sign(secret, f"{user_id}.{expires}.{user['password_hash'][-24:]}")
    return user if hmac.compare_digest(expected, signature) else None


def csrf_token(session_cookie: str, secret: str) -> str:
    return _sign(secret, "csrf:" + session_cookie)[:32]


def csrf_ok(session_cookie: str | None, secret: str, token: str | None) -> bool:
    return bool(session_cookie and token) and hmac.compare_digest(csrf_token(session_cookie, secret), token)


class LoginThrottle:
    """Refuse further attempts for an email/IP pair after repeated failures."""

    def __init__(self, max_failures: int = 8, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str, now: float | None = None) -> bool:
        now = now or time.time()
        with self._lock:
            attempts = self._failures.get(key)
            while attempts and attempts[0] < now - self.window:
                attempts.popleft()
            return bool(attempts) and len(attempts) >= self.max_failures

    def failed(self, key: str, now: float | None = None) -> None:
        with self._lock:
            self._failures.setdefault(key, collections.deque()).append(now or time.time())

    def succeeded(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def can_view_session(viewer: dict, session: dict, owner: dict | None) -> bool:
    """Owners and admins see everything; a trainer sees their trainees' practice sessions and shared coaching sessions."""
    if viewer["id"] == session["user_id"] or viewer["role"] == "admin":
        return True
    if viewer["role"] == "trainer" and owner and owner.get("trainer_id") == viewer["id"]:
        return session["module"] == "coachee" or bool(session["shared_with_trainer"])
    return False
