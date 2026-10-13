"""Daily AI allowances per person, over a rolling 24 hours, plus a per-minute message limit.

A session that is already running is never cut off: allowances are checked when an AI session starts.
Over the limit, new sessions open in template mode instead.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass
import datetime as dt
import threading
import time

import db


# "sessions" counts finished AI sessions; "starts" also counts ones abandoned midway (each opening costs model calls).
ROLE_DEFAULTS = {
    "user": {"sessions": 3, "starts": 6, "tokens": 250_000},
    "trainer": {"sessions": 15, "starts": 30, "tokens": 1_000_000},
    "admin": {"sessions": None, "starts": None, "tokens": None},
}
MESSAGES_PER_MINUTE = 10
WINDOW = dt.timedelta(hours=24)


@dataclass
class Allowance:
    session_limit: int | None
    sessions_used: int
    start_limit: int | None
    starts_used: int
    token_limit: int | None
    tokens_used: int

    @property
    def sessions_left(self) -> int | None:
        return None if self.session_limit is None else max(0, self.session_limit - self.sessions_used)

    @property
    def blocked_reason(self) -> str | None:
        """Why a new AI session can't start right now: "sessions", "starts", "tokens", or None."""
        if self.session_limit is not None and self.sessions_used >= self.session_limit:
            return "sessions"
        if self.start_limit is not None and self.starts_used >= self.start_limit:
            return "starts"
        if self.token_limit is not None and self.tokens_used >= self.token_limit:
            return "tokens"
        return None


def allowance(store: db.Store, user: dict, now: dt.datetime | None = None) -> Allowance:
    defaults = ROLE_DEFAULTS.get(user["role"], ROLE_DEFAULTS["user"])
    session_limit = user["daily_session_limit"] if user["daily_session_limit"] is not None else defaults["sessions"]
    token_limit = user["daily_token_limit"] if user["daily_token_limit"] is not None else defaults["tokens"]
    if user["daily_session_limit"] is not None:
        start_limit = session_limit * 2
    else:
        start_limit = defaults["starts"]
    since = (now or db.utcnow()) - WINDOW
    return Allowance(
        session_limit=session_limit,
        sessions_used=store.count_sessions_since(user["id"], since, completed=True) if session_limit is not None else 0,
        start_limit=start_limit,
        starts_used=store.count_sessions_since(user["id"], since) if start_limit is not None else 0,
        token_limit=token_limit,
        tokens_used=store.tokens_since(user["id"], since) if token_limit is not None else 0,
    )


class MessageRateLimiter:
    """At most `limit` messages per person in any 60 seconds (in memory; one app process)."""

    def __init__(self, limit: int = MESSAGES_PER_MINUTE):
        self.limit = limit
        self._sent: dict[int, collections.deque] = {}
        self._lock = threading.Lock()

    def allow(self, user_id: int, now: float | None = None) -> bool:
        now = now or time.time()
        with self._lock:
            sent = self._sent.setdefault(user_id, collections.deque())
            while sent and sent[0] < now - 60:
                sent.popleft()
            if len(sent) >= self.limit:
                return False
            sent.append(now)
            return True
