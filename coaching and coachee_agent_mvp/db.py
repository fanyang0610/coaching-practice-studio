"""Storage for accounts, invites, coaching sessions, profiles and the audit log.

Uses a local SQLite file by default. In production set DATABASE_URL to a managed Postgres
database, e.g. postgresql+psycopg://user:password@host:5432/coaching. Timestamps are naive UTC.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import uuid

import sqlalchemy as sa
from sqlalchemy.pool import StaticPool


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "erickson.db"

metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("email", sa.String(320), nullable=False, unique=True),
    sa.Column("display_name", sa.String(120), nullable=False),
    sa.Column("password_hash", sa.String(255), nullable=False),
    sa.Column("role", sa.String(16), nullable=False),
    sa.Column("trainer_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("daily_session_limit", sa.Integer),
    sa.Column("daily_token_limit", sa.Integer),
    sa.Column("consented_at", sa.DateTime),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

invites = sa.Table(
    "invites",
    metadata,
    sa.Column("code", sa.String(64), primary_key=True),
    sa.Column("email", sa.String(320)),
    sa.Column("role", sa.String(16), nullable=False),
    sa.Column("trainer_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("expires_at", sa.DateTime, nullable=False),
    sa.Column("max_uses", sa.Integer, nullable=False),
    sa.Column("uses", sa.Integer, nullable=False),
    sa.Column("revoked", sa.Boolean, nullable=False),
)

password_resets = sa.Table(
    "password_resets",
    metadata,
    sa.Column("token_hash", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("expires_at", sa.DateTime, nullable=False),
    sa.Column("used_at", sa.DateTime),
)

coaching_sessions = sa.Table(
    "coaching_sessions",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("module", sa.String(16), nullable=False),
    sa.Column("language", sa.String(8), nullable=False),
    sa.Column("mode", sa.String(16), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("stage", sa.String(16), nullable=False),
    sa.Column("shared_with_trainer", sa.Boolean, nullable=False),
    sa.Column("user_turns", sa.Integer, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
    sa.Column("completed_at", sa.DateTime),
    sa.Index("ix_sessions_user_status", "user_id", "status"),
    sa.Index("ix_sessions_user_created", "user_id", "created_at"),
)

profiles = sa.Table(
    "profiles",
    metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("module", sa.String(16), primary_key=True),
    sa.Column("data", sa.Text, nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
)

usage_events = sa.Table(
    "usage_events",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("session_id", sa.String(36)),
    sa.Column("model", sa.String(120), nullable=False),
    sa.Column("prompt_tokens", sa.Integer, nullable=False),
    sa.Column("completion_tokens", sa.Integer, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Index("ix_usage_user_created", "user_id", "created_at"),
)

feedback = sa.Table(
    "feedback",
    metadata,
    sa.Column("session_id", sa.String(36), sa.ForeignKey("coaching_sessions.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("message_index", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("value", sa.String(16), nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

settings = sa.Table(
    "settings",
    metadata,
    sa.Column("key", sa.String(64), primary_key=True),
    sa.Column("value", sa.Text, nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
)

# No foreign keys here on purpose: the audit trail outlives deleted accounts and sessions.
audit_log = sa.Table(
    "audit_log",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("actor_id", sa.Integer),
    sa.Column("action", sa.String(40), nullable=False),
    sa.Column("target_user_id", sa.Integer),
    sa.Column("target_session_id", sa.String(36)),
    sa.Column("detail", sa.String(255), nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Index("ix_audit_created", "created_at"),
)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)


def database_url(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    url = env.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, url: str):
        self.url = url
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
            if url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
        self.engine = sa.create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            sa.event.listen(self.engine, "connect", _sqlite_pragmas)
        metadata.create_all(self.engine)

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")

    # Users -----------------------------------------------------------------

    def create_user(self, email: str, display_name: str, password_hash: str, role: str = "user",
                    trainer_id: int | None = None, consented: bool = False) -> int:
        now = utcnow()
        with self.engine.begin() as conn:
            result = conn.execute(users.insert().values(
                email=email.strip().lower(), display_name=display_name.strip(), password_hash=password_hash,
                role=role, trainer_id=trainer_id, status="active", consented_at=now if consented else None,
                created_at=now,
            ))
            return result.inserted_primary_key[0]

    def get_user(self, user_id: int) -> dict | None:
        return self._one(sa.select(users).where(users.c.id == user_id))

    def get_user_by_email(self, email: str) -> dict | None:
        return self._one(sa.select(users).where(users.c.email == email.strip().lower()))

    def list_users(self) -> list[dict]:
        return self._all(sa.select(users).order_by(users.c.created_at))

    def trainees(self, trainer_id: int) -> list[dict]:
        return self._all(sa.select(users).where(users.c.trainer_id == trainer_id).order_by(users.c.display_name))

    def update_user(self, user_id: int, **fields) -> None:
        with self.engine.begin() as conn:
            conn.execute(users.update().where(users.c.id == user_id).values(**fields))

    def delete_user(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(users.delete().where(users.c.id == user_id))

    def count_admins(self) -> int:
        stmt = sa.select(sa.func.count()).select_from(users).where(users.c.role == "admin", users.c.status == "active")
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar_one()

    def has_users(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(sa.select(sa.func.count()).select_from(users)).scalar_one() > 0

    # Invites and password resets -------------------------------------------

    def create_invite(self, created_by: int | None, role: str = "user", trainer_id: int | None = None,
                      email: str | None = None, days_valid: int = 14, max_uses: int = 1) -> str:
        code = secrets.token_urlsafe(18)
        now = utcnow()
        with self.engine.begin() as conn:
            conn.execute(invites.insert().values(
                code=code, email=(email or "").strip().lower() or None, role=role, trainer_id=trainer_id,
                created_by=created_by, created_at=now, expires_at=now + dt.timedelta(days=days_valid),
                max_uses=max_uses, uses=0, revoked=False,
            ))
        return code

    def get_invite(self, code: str) -> dict | None:
        return self._one(sa.select(invites).where(invites.c.code == code))

    def usable_invite(self, code: str) -> dict | None:
        invite = self.get_invite(code)
        if not invite or invite["revoked"] or invite["uses"] >= invite["max_uses"] or invite["expires_at"] < utcnow():
            return None
        return invite

    def consume_invite(self, code: str) -> bool:
        """Count one use of an invite, atomically. False if it was used up or revoked meanwhile."""
        stmt = invites.update().where(
            invites.c.code == code, invites.c.revoked.is_(False), invites.c.uses < invites.c.max_uses,
            invites.c.expires_at >= utcnow(),
        ).values(uses=invites.c.uses + 1)
        with self.engine.begin() as conn:
            return conn.execute(stmt).rowcount == 1

    def list_invites(self, created_by: int | None = None) -> list[dict]:
        stmt = sa.select(invites).order_by(invites.c.created_at.desc())
        if created_by is not None:
            stmt = stmt.where(invites.c.created_by == created_by)
        return self._all(stmt)

    def revoke_invite(self, code: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(invites.update().where(invites.c.code == code).values(revoked=True))

    def create_password_reset(self, user_id: int, hours_valid: int = 48) -> str:
        token = secrets.token_urlsafe(24)
        with self.engine.begin() as conn:
            conn.execute(password_resets.insert().values(
                token_hash=_hash_token(token), user_id=user_id, expires_at=utcnow() + dt.timedelta(hours=hours_valid),
            ))
        return token

    def reset_user_id(self, token: str) -> int | None:
        row = self._one(sa.select(password_resets).where(password_resets.c.token_hash == _hash_token(token)))
        if not row or row["used_at"] or row["expires_at"] < utcnow():
            return None
        return row["user_id"]

    def consume_password_reset(self, token: str) -> int | None:
        user_id = self.reset_user_id(token)
        if user_id is None:
            return None
        stmt = password_resets.update().where(
            password_resets.c.token_hash == _hash_token(token), password_resets.c.used_at.is_(None),
        ).values(used_at=utcnow())
        with self.engine.begin() as conn:
            return user_id if conn.execute(stmt).rowcount == 1 else None

    # Coaching sessions -----------------------------------------------------

    def create_session(self, user_id: int, module: str, language: str, mode: str, stage: str, state: dict) -> str:
        session_id = str(uuid.uuid4())
        now = utcnow()
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.insert().values(
                id=session_id, user_id=user_id, module=module, language=language, mode=mode, status="active",
                stage=stage, shared_with_trainer=False, user_turns=0, state=json.dumps(state, ensure_ascii=False),
                created_at=now, updated_at=now,
            ))
        return session_id

    def save_session(self, session_id: str, *, state: dict, status: str, stage: str, user_turns: int,
                     language: str, mode: str) -> None:
        now = utcnow()
        values = dict(state=json.dumps(state, ensure_ascii=False), status=status, stage=stage, user_turns=user_turns,
                      language=language, mode=mode, updated_at=now)
        stmt = coaching_sessions.update().where(coaching_sessions.c.id == session_id)
        with self.engine.begin() as conn:
            if status == "completed":
                conn.execute(stmt.where(coaching_sessions.c.completed_at.is_(None)).values(completed_at=now))
            conn.execute(stmt.values(**values))

    def set_session_status(self, session_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.update().where(coaching_sessions.c.id == session_id).values(
                status=status, updated_at=utcnow()))

    def set_session_shared(self, session_id: str, shared: bool) -> None:
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.update().where(coaching_sessions.c.id == session_id).values(
                shared_with_trainer=shared))

    def unshare_sessions(self, user_id: int) -> None:
        """Make all of a person's shared sessions private again, e.g. when their mentor changes."""
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.update().where(coaching_sessions.c.user_id == user_id).values(
                shared_with_trainer=False))

    def get_session(self, session_id: str) -> dict | None:
        return self._one(sa.select(coaching_sessions).where(coaching_sessions.c.id == session_id))

    def latest_active_session(self, user_id: int) -> dict | None:
        stmt = (sa.select(coaching_sessions)
                .where(coaching_sessions.c.user_id == user_id, coaching_sessions.c.status == "active")
                .order_by(coaching_sessions.c.updated_at.desc()).limit(1))
        return self._one(stmt)

    def list_sessions(self, user_id: int, limit: int = 100) -> list[dict]:
        stmt = (sa.select(*_session_summary_columns()).where(coaching_sessions.c.user_id == user_id)
                .order_by(coaching_sessions.c.created_at.desc()).limit(limit))
        return self._all(stmt)

    def trainer_visible_sessions(self, trainer_id: int, limit: int = 200) -> list[dict]:
        """Practice sessions of the trainer's trainees, plus coaching sessions they chose to share."""
        stmt = (sa.select(*_session_summary_columns(), users.c.display_name.label("owner_name"))
                .join(users, users.c.id == coaching_sessions.c.user_id)
                .where(users.c.trainer_id == trainer_id,
                       sa.or_(coaching_sessions.c.module == "coachee", coaching_sessions.c.shared_with_trainer.is_(True)))
                .order_by(coaching_sessions.c.created_at.desc()).limit(limit))
        return self._all(stmt)

    def recent_sessions(self, limit: int = 200) -> list[dict]:
        stmt = (sa.select(*_session_summary_columns(), users.c.display_name.label("owner_name"))
                .join(users, users.c.id == coaching_sessions.c.user_id)
                .order_by(coaching_sessions.c.created_at.desc()).limit(limit))
        return self._all(stmt)

    def ai_sessions_since(self, user_id: int, since: dt.datetime, module: str, *, completed: bool = False) -> tuple[int, dt.datetime | None]:
        """(count, earliest timestamp) of AI sessions in a module started, or finished, since a time."""
        column = coaching_sessions.c.completed_at if completed else coaching_sessions.c.created_at
        stmt = sa.select(sa.func.count(), sa.func.min(column)).where(
            coaching_sessions.c.user_id == user_id, coaching_sessions.c.mode == "llm", coaching_sessions.c.module == module,
            column >= since)
        with self.engine.connect() as conn:
            count, earliest = conn.execute(stmt).one()
            return count, earliest

    # Profiles ----------------------------------------------------------------

    def get_profile(self, user_id: int, module: str) -> dict | None:
        row = self._one(sa.select(profiles).where(profiles.c.user_id == user_id, profiles.c.module == module))
        return json.loads(row["data"]) if row else None

    def save_profile(self, user_id: int, module: str, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        with self.engine.begin() as conn:
            updated = conn.execute(profiles.update().where(profiles.c.user_id == user_id, profiles.c.module == module)
                                   .values(data=payload, updated_at=utcnow())).rowcount
            if not updated:
                conn.execute(profiles.insert().values(user_id=user_id, module=module, data=payload, updated_at=utcnow()))

    def delete_profiles(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(profiles.delete().where(profiles.c.user_id == user_id))

    # Usage and feedback ------------------------------------------------------

    def record_usage(self, user_id: int, session_id: str | None, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(usage_events.insert().values(
                user_id=user_id, session_id=session_id, model=model or "", prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens), created_at=utcnow()))

    def tokens_since(self, user_id: int, since: dt.datetime) -> int:
        return self.token_usage_since(user_id, since)[0]

    def token_usage_since(self, user_id: int, since: dt.datetime) -> tuple[int, dt.datetime | None]:
        """(tokens used, earliest usage time) since a time."""
        stmt = sa.select(sa.func.coalesce(sa.func.sum(usage_events.c.prompt_tokens + usage_events.c.completion_tokens), 0),
                         sa.func.min(usage_events.c.created_at)).where(
            usage_events.c.user_id == user_id, usage_events.c.created_at >= since)
        with self.engine.connect() as conn:
            total, earliest = conn.execute(stmt).one()
            return int(total), earliest

    def usage_by_user_since(self, since: dt.datetime) -> dict[int, int]:
        stmt = (sa.select(usage_events.c.user_id, sa.func.sum(usage_events.c.prompt_tokens + usage_events.c.completion_tokens))
                .where(usage_events.c.created_at >= since).group_by(usage_events.c.user_id))
        with self.engine.connect() as conn:
            return {row[0]: int(row[1]) for row in conn.execute(stmt)}

    def set_feedback(self, user_id: int, session_id: str, message_index: int, value: str | None) -> None:
        key = (feedback.c.session_id == session_id) & (feedback.c.message_index == message_index)
        with self.engine.begin() as conn:
            conn.execute(feedback.delete().where(key))
            if value:
                conn.execute(feedback.insert().values(session_id=session_id, message_index=message_index, user_id=user_id,
                                                      value=value, created_at=utcnow()))

    def feedback_for_session(self, session_id: str) -> dict[int, str]:
        rows = self._all(sa.select(feedback).where(feedback.c.session_id == session_id))
        return {row["message_index"]: row["value"] for row in rows}

    def feedback_totals_since(self, since: dt.datetime) -> dict[str, int]:
        stmt = sa.select(feedback.c.value, sa.func.count()).where(feedback.c.created_at >= since).group_by(feedback.c.value)
        with self.engine.connect() as conn:
            return {row[0]: row[1] for row in conn.execute(stmt)}

    # Settings ----------------------------------------------------------------

    def get_setting(self, key: str) -> dict | None:
        row = self._one(sa.select(settings).where(settings.c.key == key))
        return json.loads(row["value"]) if row else None

    def set_setting(self, key: str, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with self.engine.begin() as conn:
            if not conn.execute(settings.update().where(settings.c.key == key).values(value=payload, updated_at=utcnow())).rowcount:
                conn.execute(settings.insert().values(key=key, value=payload, updated_at=utcnow()))

    # Audit -------------------------------------------------------------------

    def log(self, actor_id: int | None, action: str, *, target_user_id: int | None = None,
            target_session_id: str | None = None, detail: str = "") -> None:
        with self.engine.begin() as conn:
            conn.execute(audit_log.insert().values(
                actor_id=actor_id, action=action, target_user_id=target_user_id, target_session_id=target_session_id,
                detail=detail[:255], created_at=utcnow()))

    def audit_entries(self, limit: int = 100) -> list[dict]:
        return self._all(sa.select(audit_log).order_by(audit_log.c.id.desc()).limit(limit))

    # Export ------------------------------------------------------------------

    def export_user(self, user_id: int) -> dict:
        user = self.get_user(user_id) or {}
        sessions = self._all(sa.select(coaching_sessions).where(coaching_sessions.c.user_id == user_id)
                             .order_by(coaching_sessions.c.created_at))
        return {
            "account": {key: user.get(key) for key in ("email", "display_name", "role", "created_at", "consented_at")},
            "sessions": [
                {**{key: row[key] for key in ("id", "module", "language", "mode", "status", "stage", "shared_with_trainer",
                                               "created_at", "completed_at")},
                 "transcript": json.loads(row["state"]).get("context", []),
                 "feedback": self.feedback_for_session(row["id"])}
                for row in sessions
            ],
            "profiles": {module: self.get_profile(user_id, module) for module in ("coach", "coachee")},
            "tokens_used_last_30_days": self.tokens_since(user_id, utcnow() - dt.timedelta(days=30)),
        }

    # Helpers -----------------------------------------------------------------

    def _one(self, stmt) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
            return dict(row) if row else None

    def _all(self, stmt) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(stmt).mappings()]


def _session_summary_columns():
    c = coaching_sessions.c
    return (c.id, c.user_id, c.module, c.language, c.mode, c.status, c.stage, c.shared_with_trainer, c.user_turns,
            c.created_at, c.updated_at, c.completed_at)


def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()
