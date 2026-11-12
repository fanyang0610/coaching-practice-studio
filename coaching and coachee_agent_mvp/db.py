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
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.pool import StaticPool

from studio_config import LEGACY_NAME, local_path


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "studio.db"

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

practice_navigation = sa.Table(
    "practice_navigation",
    metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("module", sa.String(16), nullable=False),
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

# What a finished session produced: an AI Coach action card, or a Coachee Lab score.
session_results = sa.Table(
    "session_results",
    metadata,
    sa.Column("session_id", sa.String(36), sa.ForeignKey("coaching_sessions.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("module", sa.String(16), nullable=False),
    sa.Column("score", sa.Integer),
    sa.Column("card", sa.Text),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Index("ix_results_user_module", "user_id", "module", "created_at"),
)

# How useful the person found a finished session, 1 (not useful) to 5 (very useful), asked once at its end.
session_ratings = sa.Table(
    "session_ratings",
    metadata,
    sa.Column("session_id", sa.String(36), sa.ForeignKey("coaching_sessions.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("module", sa.String(16), nullable=False),
    sa.Column("rating", sa.Integer, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Index("ix_ratings_created", "created_at"),
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


def _version_stamp() -> dt.datetime:
    """A session's updated_at, to the microsecond: it doubles as the version a page last saw (see save_session)."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def database_url(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    url = env.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url:
        return url
    return f"sqlite:///{local_path(DEFAULT_SQLITE_PATH, f'{LEGACY_NAME}.db')}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LastAdminError(ValueError):
    """A change would remove the last active administrator."""


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
        with self.engine.begin() as conn:
            return self._insert_user(conn, email, display_name, password_hash, role, trainer_id, consented)

    @staticmethod
    def _insert_user(conn, email, display_name, password_hash, role, trainer_id, consented):
        now = utcnow()
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
            if "role" in fields or "status" in fields:
                self._protect_last_admin(conn, user_id, fields)
            if "trainer_id" in fields:
                previous_trainer = conn.execute(sa.select(users.c.trainer_id).where(users.c.id == user_id)
                                                .with_for_update()).scalar_one_or_none()
            conn.execute(users.update().where(users.c.id == user_id).values(**fields))
            if "trainer_id" in fields and fields["trainer_id"] != previous_trainer:
                conn.execute(coaching_sessions.update().where(coaching_sessions.c.user_id == user_id,
                             coaching_sessions.c.shared_with_trainer.is_(True)).values(shared_with_trainer=False))

    def delete_user(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            self._protect_last_admin(conn, user_id)
            conn.execute(users.delete().where(users.c.id == user_id))

    def _protect_last_admin(self, conn, user_id: int, fields: dict | None = None) -> None:
        """Serialize role/status changes and deletions before reading the current user/count.

        None means deletion. The lock lasts through the caller's commit/rollback and is shared
        by every Store/process using this database; locking only the target row allows write skew.
        """
        if self.is_sqlite:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            # Database-local transaction advisory lock, reserved for active-admin membership.
            conn.execute(sa.text("SELECT pg_advisory_xact_lock(1129337683, 1)"))
        current = conn.execute(sa.select(users).where(users.c.id == user_id)).mappings().first()
        if not current or current["role"] != "admin" or current["status"] != "active":
            return
        if fields is not None and (fields.get("role", current["role"]) == "admin"
                                   and fields.get("status", current["status"]) == "active"):
            return
        count = conn.execute(sa.select(sa.func.count()).select_from(users).where(
            users.c.role == "admin", users.c.status == "active")).scalar_one()
        if count <= 1:
            raise LastAdminError()

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

    def register_from_invite(self, code: str, email: str, display_name: str, password_hash: str) -> int | None:
        """Use the invite only if creating the account succeeds."""
        email = email.strip().lower()
        stmt = invites.update().where(
            invites.c.code == code, invites.c.revoked.is_(False), invites.c.uses < invites.c.max_uses,
            invites.c.expires_at >= utcnow(), sa.or_(invites.c.email.is_(None), invites.c.email == email),
        ).values(uses=invites.c.uses + 1).returning(invites.c.role, invites.c.trainer_id)
        with self.engine.begin() as conn:
            invite = conn.execute(stmt).first()
            if not invite:
                return None
            return self._insert_user(conn, email, display_name, password_hash, invite.role, invite.trainer_id, True)

    def list_invites(self, created_by: int | None = None) -> list[dict]:
        stmt = sa.select(invites).order_by(invites.c.created_at.desc(), invites.c.code.desc())
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

    def reset_password(self, token: str, password_hash: str) -> int | None:
        """Change the password and mark the reset link used in one transaction."""
        now = utcnow()
        stmt = password_resets.update().where(
            password_resets.c.token_hash == _hash_token(token), password_resets.c.used_at.is_(None),
            password_resets.c.expires_at >= now,
        ).values(used_at=now).returning(password_resets.c.user_id)
        with self.engine.begin() as conn:
            user_id = conn.execute(stmt).scalar_one_or_none()
            if user_id is None:
                return None
            conn.execute(users.update().where(users.c.id == user_id).values(password_hash=password_hash))
            return user_id

    # Coaching sessions -----------------------------------------------------

    def create_session(self, user_id: int, module: str, language: str, mode: str, stage: str, state: dict) -> str:
        session_id = str(uuid.uuid4())
        self.insert_session(session_id, user_id, module, language, mode, stage, state)
        return session_id

    def insert_session(self, session_id: str, user_id: int, module: str, language: str, mode: str,
                       stage: str, state: dict, *, replace_current: bool = False,
                       expected: tuple[str, dt.datetime] | None = None) -> dt.datetime | None:
        """Insert an opening only if the mode's session still matches the snapshot used to start it."""
        c = coaching_sessions.c
        with self.engine.begin() as conn:
            if replace_current:
                # Serialize openings for this account, including when there is no session row to lock yet.
                # A first write also takes the SQLite write lock before reading the current slot.
                locked = conn.execute(users.update().where(users.c.id == user_id, users.c.status == "active")
                                      .values(display_name=users.c.display_name))
                if not locked.rowcount:
                    return None
                current = conn.execute(self._resumable_query(user_id, module).with_for_update()).mappings().first()
                if (current and (current["id"], current["updated_at"])) != expected:
                    return None
                if current and current["status"] == "active":
                    conn.execute(coaching_sessions.update()
                                 .where(c.user_id == user_id, c.module == module, c.status == "active")
                                 .values(status="abandoned", updated_at=_version_stamp()))
            version = _version_stamp()
            conn.execute(coaching_sessions.insert().values(
                id=session_id, user_id=user_id, module=module, language=language, mode=mode, status="active",
                stage=stage, shared_with_trainer=False, user_turns=0, state=json.dumps(state, ensure_ascii=False),
                created_at=version, updated_at=version,
            ))
            if replace_current:
                self._remember_module(conn, user_id, module)
        return version

    def last_module(self, user_id: int) -> str | None:
        row = self._one(sa.select(practice_navigation.c.module).where(practice_navigation.c.user_id == user_id))
        return row["module"] if row else None

    def remember_module(self, user_id: int, module: str) -> None:
        with self.engine.begin() as conn:
            self._remember_module(conn, user_id, module)

    def _remember_module(self, conn, user_id: int, module: str) -> None:
        insert = sqlite.insert if self.is_sqlite else postgresql.insert
        stmt = insert(practice_navigation).values(user_id=user_id, module=module)
        conn.execute(stmt.on_conflict_do_update(index_elements=[practice_navigation.c.user_id],
                                                set_={"module": module}))

    def save_session(self, session_id: str, *, state: dict, status: str, stage: str, user_turns: int,
                     language: str, mode: str, expected_version: dt.datetime | None = None,
                     practice_score: int | None = None) -> dt.datetime | None:
        """Store a conversation and return its new version (its updated_at).

        With expected_version, the save happens only if nobody has saved the session since that version, e.g. from
        another tab or device; otherwise nothing changes and None is returned, so an old page can't overwrite newer turns.
        """
        now = _version_stamp()
        values = dict(state=json.dumps(state, ensure_ascii=False), status=status, stage=stage, user_turns=user_turns,
                      language=language, mode=mode, updated_at=now)
        if status == "completed":
            values["completed_at"] = sa.func.coalesce(coaching_sessions.c.completed_at,
                                                     sa.literal(now.replace(microsecond=0), sa.DateTime()))
        stmt = coaching_sessions.update().where(coaching_sessions.c.id == session_id)
        if expected_version is not None:
            stmt = stmt.where(coaching_sessions.c.updated_at == expected_version)
        with self.engine.begin() as conn:
            if conn.execute(stmt.values(**values)).rowcount != 1:
                return None
            if practice_score is not None:
                self._insert_practice_score(conn, session_id, practice_score)
            return now

    def save_review_attempt(self, session_id: str, state: dict, expected_version: dt.datetime, *,
                            score: int | None = None) -> dt.datetime | None:
        """Claim or finish a retry without changing the practice's completion date or turn count."""
        c = coaching_sessions.c
        now = _version_stamp()
        stmt = coaching_sessions.update().where(c.id == session_id, c.module == "coachee",
                                               c.status == "completed", c.updated_at == expected_version)
        with self.engine.begin() as conn:
            if conn.execute(stmt.values(state=json.dumps(state, ensure_ascii=False), updated_at=now)).rowcount != 1:
                return None
            if score is not None:
                self._insert_practice_score(conn, session_id, score)
            return now

    def save_action_card_attempt(self, session_id: str, user_id: int, state: dict,
                                 expected_version: dt.datetime, *, card: dict | None = None) -> dt.datetime | None:
        """Claim/finish recovery atomically; never replace an existing result or original dialogue."""
        c = coaching_sessions.c
        now = _version_stamp()
        stmt = coaching_sessions.update().where(
            c.id == session_id, c.user_id == user_id, c.module == "coach", c.status == "completed",
            c.mode == "llm", c.updated_at == expected_version,
            ~sa.exists(sa.select(session_results.c.session_id).where(session_results.c.session_id == session_id)),
        )
        with self.engine.begin() as conn:
            if conn.execute(stmt.values(state=json.dumps(state, ensure_ascii=False), updated_at=now)).rowcount != 1:
                return None
            if card is not None:
                # A plain insert also rolls back the state if another writer inserted a card meanwhile.
                conn.execute(session_results.insert().from_select(
                    ["session_id", "user_id", "module", "card", "created_at"],
                    sa.select(c.id, c.user_id, c.module, sa.literal(json.dumps(card, ensure_ascii=False)),
                              sa.func.coalesce(c.completed_at, c.created_at)).where(c.id == session_id),
                ))
            return now

    def _insert_practice_score(self, conn, session_id: str, score: int) -> None:
        c = coaching_sessions.c
        insert = sqlite.insert if self.is_sqlite else postgresql.insert
        stmt = insert(session_results).from_select(
            ["session_id", "user_id", "module", "score", "created_at"],
            sa.select(c.id, c.user_id, c.module, sa.literal(score), sa.func.coalesce(c.completed_at, c.created_at))
            .where(c.id == session_id),
        )
        conn.execute(stmt.on_conflict_do_nothing(index_elements=[session_results.c.session_id]))

    def delete_session(self, session_id: str) -> None:
        """Remove a session and its dependent results and ratings."""
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.delete().where(coaching_sessions.c.id == session_id))

    def session_version(self, session_id: str) -> dict | None:
        """What a page needs to tell whether its copy of a session is still the latest: updated_at, status, module, language."""
        c = coaching_sessions.c
        return self._one(sa.select(c.updated_at, c.status, c.module, c.language).where(c.id == session_id))

    def set_session_status(self, session_id: str, status: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(coaching_sessions.update().where(coaching_sessions.c.id == session_id).values(
                status=status, updated_at=_version_stamp()))

    def abandon_session(self, session_id: str, expected_version: dt.datetime | None = None) -> None:
        """Set an unfinished session aside. A session finished meanwhile stays finished."""
        c = coaching_sessions.c
        stmt = coaching_sessions.update().where(c.id == session_id, c.status == "active")
        if expected_version is not None:
            stmt = stmt.where(c.updated_at == expected_version)
        with self.engine.begin() as conn:
            conn.execute(stmt.values(status="abandoned", updated_at=_version_stamp()))

    def set_session_shared(self, session_id: str, shared: bool, *, expected_trainer_id: int | None = None) -> bool:
        with self.engine.begin() as conn:
            if expected_trainer_id is not None:
                if self.is_sqlite:
                    conn.exec_driver_sql("BEGIN IMMEDIATE")
                owner = (sa.select(users.c.trainer_id).join(coaching_sessions, coaching_sessions.c.user_id == users.c.id)
                         .where(coaching_sessions.c.id == session_id).with_for_update(of=users))
                if conn.execute(owner).scalar_one_or_none() != expected_trainer_id:
                    return False
            return conn.execute(coaching_sessions.update().where(coaching_sessions.c.id == session_id).values(
                shared_with_trainer=shared)).rowcount == 1

    def get_session(self, session_id: str, *, with_owner: bool = False) -> dict | None:
        stmt = (sa.select(coaching_sessions, session_results.c.score, session_results.c.card)
                .outerjoin(session_results, session_results.c.session_id == coaching_sessions.c.id)
                .where(coaching_sessions.c.id == session_id))
        if with_owner:
            stmt = stmt.join(users, users.c.id == coaching_sessions.c.user_id).add_columns(
                users.c.trainer_id.label("owner_trainer_id"), users.c.display_name.label("owner_name"))
        row = self._one(stmt)
        return _with_card(row) if row else None

    def _resumable_query(self, user_id: int, module: str | None):
        c = coaching_sessions.c
        stmt = sa.select(coaching_sessions).where(c.user_id == user_id, c.status.in_(("active", "completed")))
        if module is not None:
            stmt = stmt.where(c.module == module)
        # A legacy account can have an unfinished session and older finished ones. Prefer the unfinished one.
        return stmt.order_by(sa.case((c.status == "active", 0), else_=1), c.created_at.desc(),
                             c.updated_at.desc(), c.id.desc()).limit(1)

    def resumable_session(self, user_id: int, module: str | None = None) -> dict | None:
        return self._one(self._resumable_query(user_id, module))

    def latest_active_session(self, user_id: int) -> dict | None:
        stmt = (sa.select(coaching_sessions)
                .where(coaching_sessions.c.user_id == user_id, coaching_sessions.c.status == "active")
                .order_by(coaching_sessions.c.updated_at.desc()).limit(1))
        return self._one(stmt)

    def _account_sessions_query(self, user_id: int):
        return (sa.select(*_session_summary_columns(), session_results.c.score, session_results.c.card)
                .select_from(coaching_sessions.outerjoin(session_results, session_results.c.session_id == coaching_sessions.c.id))
                .where(coaching_sessions.c.user_id == user_id))

    def count_sessions(self, user_id: int) -> int:
        with self.engine.connect() as conn:
            return conn.execute(self._account_sessions_query(user_id).with_only_columns(sa.func.count())).scalar_one()

    def list_sessions(self, user_id: int, limit: int = 100, *, offset: int = 0) -> list[dict]:
        """A person's sessions, newest first, each with its score or action card when it has one."""
        stmt = self._account_sessions_query(user_id).order_by(
            coaching_sessions.c.created_at.desc(), coaching_sessions.c.id.desc()).limit(limit).offset(offset)
        return [_with_card(row) for row in self._all(stmt)]

    def _trainer_sessions_query(self, trainer_id: int):
        return (sa.select(*_session_summary_columns(), users.c.display_name.label("owner_name"),
                          session_results.c.score, session_results.c.card)
                .select_from(coaching_sessions.join(users, users.c.id == coaching_sessions.c.user_id)
                             .outerjoin(session_results, session_results.c.session_id == coaching_sessions.c.id))
                .where(users.c.trainer_id == trainer_id,
                       sa.or_(coaching_sessions.c.module == "coachee", coaching_sessions.c.shared_with_trainer.is_(True))))

    def count_trainer_visible_sessions(self, trainer_id: int) -> int:
        with self.engine.connect() as conn:
            return conn.execute(self._trainer_sessions_query(trainer_id).with_only_columns(sa.func.count())).scalar_one()

    def trainer_visible_sessions(self, trainer_id: int, limit: int = 200, *, offset: int = 0) -> list[dict]:
        """Practice sessions of the trainer's trainees, plus coaching sessions they chose to share."""
        stmt = self._trainer_sessions_query(trainer_id).order_by(
            coaching_sessions.c.created_at.desc(), coaching_sessions.c.id.desc()).limit(limit).offset(offset)
        return [_with_card(row) for row in self._all(stmt)]

    # Session results -----------------------------------------------------------

    def save_session_result(self, session_id: str, user_id: int, module: str, *, score: int | None = None,
                            card: dict | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(session_results.delete().where(session_results.c.session_id == session_id))
            conn.execute(session_results.insert().values(
                session_id=session_id, user_id=user_id, module=module, score=score,
                card=json.dumps(card, ensure_ascii=False) if card else None, created_at=utcnow()))

    def session_results(self, user_id: int, module: str, limit: int = 10) -> list[dict]:
        """A person's recent results in one module, newest first."""
        stmt = (sa.select(session_results).where(session_results.c.user_id == user_id, session_results.c.module == module)
                .order_by(session_results.c.created_at.desc()).limit(limit))
        return [_with_card(row) for row in self._all(stmt)]

    def latest_card(self, user_id: int, since: dt.datetime, until: dt.datetime) -> dict | None:
        """The most recent action card made between two times, so the next session can follow up on it."""
        stmt = (sa.select(session_results.c.card)
                .where(session_results.c.user_id == user_id, session_results.c.module == "coach",
                       session_results.c.card.is_not(None), session_results.c.created_at >= since,
                       session_results.c.created_at <= until)
                .order_by(session_results.c.created_at.desc()).limit(1))
        row = self._one(stmt)
        return json.loads(row["card"]) if row else None

    def recent_sessions(self, limit: int = 200) -> list[dict]:
        stmt = (sa.select(*_session_summary_columns(), users.c.display_name.label("owner_name"), session_ratings.c.rating)
                .select_from(coaching_sessions.join(users, users.c.id == coaching_sessions.c.user_id)
                             .outerjoin(session_ratings, session_ratings.c.session_id == coaching_sessions.c.id))
                .order_by(coaching_sessions.c.created_at.desc()).limit(limit))
        return self._all(stmt)

    def ai_sessions_since(self, user_id: int, since: dt.datetime, module: str, *, completed: bool = False,
                          below_limit: int | None = None) -> tuple[int, dt.datetime | None]:
        """Count AI starts/finishes after `since`, and the earliest timestamp.

        With `below_limit`, return the timestamp whose expiry leaves the count below that limit instead.
        None means no expiry is needed, or a nonpositive limit cannot recover by waiting.
        """
        column = coaching_sessions.c.completed_at if completed else coaching_sessions.c.created_at
        scope = (
            coaching_sessions.c.user_id == user_id, coaching_sessions.c.mode == "llm", coaching_sessions.c.module == module,
            column > since)
        stmt = sa.select(sa.func.count(), sa.func.min(column)).where(*scope)
        with self.engine.connect() as conn:
            count, earliest = conn.execute(stmt).one()
            if below_limit is not None:
                earliest = (conn.execute(sa.select(column).where(*scope).order_by(column)
                                         .offset(count - below_limit).limit(1)).scalar_one()
                            if 0 < below_limit <= count else None)
            return count, earliest

    # Profiles ----------------------------------------------------------------

    def get_profile(self, user_id: int, module: str) -> dict | None:
        row = self._one(sa.select(profiles).where(profiles.c.user_id == user_id, profiles.c.module == module))
        return json.loads(row["data"]) if row else None

    def save_profile(self, user_id: int, module: str, data: dict, *, expected_version: str | None = None) -> bool:
        from memory import profile_version

        payload = json.dumps(data, ensure_ascii=False)
        with self.engine.begin() as conn:
            scope = (profiles.c.user_id == user_id, profiles.c.module == module)
            if expected_version is not None:
                row = conn.execute(sa.select(profiles.c.data).where(*scope)).first()
                if profile_version(json.loads(row.data) if row else None) != expected_version:
                    return False
                if row:
                    return conn.execute(profiles.update().where(*scope, profiles.c.data == row.data)
                                        .values(data=payload, updated_at=utcnow())).rowcount == 1
                insert = sqlite.insert if self.is_sqlite else postgresql.insert
                return conn.execute(insert(profiles).values(user_id=user_id, module=module, data=payload, updated_at=utcnow())
                                    .on_conflict_do_nothing(index_elements=[profiles.c.user_id, profiles.c.module])
                                    .returning(profiles.c.user_id)).scalar_one_or_none() is not None
            updated = conn.execute(profiles.update().where(profiles.c.user_id == user_id, profiles.c.module == module)
                                   .values(data=payload, updated_at=utcnow())).rowcount
            if not updated:
                conn.execute(profiles.insert().values(user_id=user_id, module=module, data=payload, updated_at=utcnow()))
            return True

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

    def token_usage_since(self, user_id: int, since: dt.datetime, *,
                          below_limit: int | None = None) -> tuple[int, dt.datetime | None]:
        """Tokens used after `since`, and the earliest usage time.

        With `below_limit`, return the usage timestamp whose expiry leaves the total below that limit.
        """
        amount = usage_events.c.prompt_tokens + usage_events.c.completion_tokens
        scope = (usage_events.c.user_id == user_id, usage_events.c.created_at > since)
        stmt = sa.select(sa.func.coalesce(sa.func.sum(amount), 0), sa.func.min(usage_events.c.created_at)).where(*scope)
        with self.engine.connect() as conn:
            total, earliest = conn.execute(stmt).one()
            if below_limit is not None:
                earliest = None
                if 0 < below_limit <= total:
                    remaining = int(total)
                    timeline = (sa.select(usage_events.c.created_at, sa.func.sum(amount)).where(*scope)
                                .group_by(usage_events.c.created_at).order_by(usage_events.c.created_at))
                    for timestamp, released in conn.execute(timeline):
                        remaining -= int(released)
                        if remaining < below_limit:
                            earliest = timestamp
                            break
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

    def rate_session(self, session_id: str, user_id: int, module: str, rating: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(session_ratings.delete().where(session_ratings.c.session_id == session_id))
            conn.execute(session_ratings.insert().values(session_id=session_id, user_id=user_id, module=module,
                                                         rating=rating, created_at=utcnow()))

    def session_rating(self, session_id: str) -> int | None:
        row = self._one(sa.select(session_ratings.c.rating).where(session_ratings.c.session_id == session_id))
        return row["rating"] if row else None

    def ratings_since(self, since: dt.datetime) -> dict[str, tuple[int, float]]:
        """{module: (number of ratings, average)} for sessions rated since a time."""
        stmt = (sa.select(session_ratings.c.module, sa.func.count(), sa.func.avg(session_ratings.c.rating))
                .where(session_ratings.c.created_at >= since).group_by(session_ratings.c.module))
        with self.engine.connect() as conn:
            return {row[0]: (row[1], float(row[2])) for row in conn.execute(stmt)}

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

    def audit_since(self, action: str, since: dt.datetime) -> list[dict]:
        """Entries of one kind since a time, newest first."""
        return self._all(sa.select(audit_log).where(audit_log.c.action == action, audit_log.c.created_at >= since)
                         .order_by(audit_log.c.id.desc()))

    # Export ------------------------------------------------------------------

    def export_user(self, user_id: int) -> dict:
        user = self.get_user(user_id) or {}
        sessions = self._all(sa.select(coaching_sessions).where(coaching_sessions.c.user_id == user_id)
                             .order_by(coaching_sessions.c.created_at))
        results = {row["session_id"]: row for row in map(_with_card, self._all(
            sa.select(session_results).where(session_results.c.user_id == user_id)))}
        return {
            "account": {key: user.get(key) for key in ("email", "display_name", "role", "created_at", "consented_at")},
            "sessions": [
                {**{key: row[key] for key in ("id", "module", "language", "mode", "status", "stage", "shared_with_trainer",
                                               "created_at", "completed_at")},
                 "transcript": json.loads(row["state"]).get("context", []),
                 "feedback": self.feedback_for_session(row["id"]),
                 "usefulness_rating": self.session_rating(row["id"]),
                 "score": results.get(row["id"], {}).get("score"),
                 "action_card": results.get(row["id"], {}).get("card")}
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


def _with_card(row: dict) -> dict:
    """Decode a stored action card in a result row."""
    if row.get("card"):
        row["card"] = json.loads(row["card"])
    return row


def _sqlite_pragmas(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()
