"""Daily AI allowances per person and module, over a rolling 24 hours, plus a per-minute message limit.

A session that is already running is never cut off: allowances are checked when an AI session starts.
Over the limit, no new session starts in that module; the page says when one can.

AI Coach (personal coaching) and Coachee Lab (practice) have separate session allowances, because
practice drills shouldn't use up someone's own coaching. Tokens are one shared daily backstop.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass
import datetime as dt
import threading
import time

import db


MODULES = ("coach", "coachee")
LIMITS_SETTING = "role_limits"
# Finished AI sessions per module, and tokens across both. None means no limit.
ROLE_DEFAULTS = {
    "user": {"coach": 3, "coachee": 5, "tokens": 400_000},
    "trainer": {"coach": 10, "coachee": 20, "tokens": 1_500_000},
    "admin": {"coach": None, "coachee": None, "tokens": None},
}
MESSAGES_PER_MINUTE = 10
# A backstop against a runaway conversation, well above a full practice: Xiaofang's careful practice reached stage 3
# of 5 after 40 messages (the old cap, a guess made before anyone used the app). The last few are counted down, and
# the last one ends the conversation with its review or action card instead of locking it.
MESSAGES_PER_CONVERSATION = 100
MESSAGES_LEFT_WARNING = 5
WINDOW = dt.timedelta(hours=24)


def role_limits(store: db.Store) -> dict[str, dict[str, int | None]]:
    """Code defaults, overridden by whatever the admin saved on the Admin page."""
    saved = store.get_setting(LIMITS_SETTING) or {}
    return {role: {**defaults, **saved.get(role, {})} for role, defaults in ROLE_DEFAULTS.items()}


def save_role_limits(store: db.Store, role: str, coach: int | None, coachee: int | None, tokens: int | None) -> None:
    saved = store.get_setting(LIMITS_SETTING) or {}
    saved[role] = {"coach": coach, "coachee": coachee, "tokens": tokens}
    store.set_setting(LIMITS_SETTING, saved)


@dataclass
class Allowance:
    module: str
    session_limit: int | None
    sessions_used: int
    start_limit: int | None
    starts_used: int
    token_limit: int | None
    tokens_used: int
    # When the oldest counted item drops out of the 24-hour window, per limit.
    sessions_free_at: dt.datetime | None = None
    starts_free_at: dt.datetime | None = None
    tokens_free_at: dt.datetime | None = None

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

    def hours_until_available(self, now: dt.datetime | None = None) -> int:
        free_at = {"sessions": self.sessions_free_at, "starts": self.starts_free_at, "tokens": self.tokens_free_at}.get(self.blocked_reason)
        if free_at is None:
            return 24
        seconds = (free_at - (now or db.utcnow())).total_seconds()
        return max(1, -(-int(seconds) // 3600))


def allowance(store: db.Store, user: dict, module: str = "coach", now: dt.datetime | None = None) -> Allowance:
    limits = role_limits(store).get(user["role"], ROLE_DEFAULTS["user"])
    session_limit = user["daily_session_limit"] if user["daily_session_limit"] is not None else limits[module]
    token_limit = user["daily_token_limit"] if user["daily_token_limit"] is not None else limits["tokens"]
    # Abandoned sessions still cost an opening call, so starts are capped too, at twice the finished allowance.
    start_limit = None if session_limit is None else session_limit * 2
    since = (now or db.utcnow()) - WINDOW

    sessions_used = starts_used = tokens_used = 0
    sessions_free_at = starts_free_at = tokens_free_at = None
    if session_limit is not None:
        sessions_used, earliest = store.ai_sessions_since(user["id"], since, module, completed=True)
        sessions_free_at = earliest + WINDOW if earliest else None
        starts_used, earliest = store.ai_sessions_since(user["id"], since, module)
        starts_free_at = earliest + WINDOW if earliest else None
    if token_limit is not None:
        tokens_used, earliest = store.token_usage_since(user["id"], since)
        tokens_free_at = earliest + WINDOW if earliest else None
    return Allowance(module, session_limit, sessions_used, start_limit, starts_used, token_limit, tokens_used,
                     sessions_free_at, starts_free_at, tokens_free_at)


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
