#!/usr/bin/env python3
"""Run the storage, account and quota tests against a real (embedded, throwaway) Postgres.

Needs uv (https://docs.astral.sh/uv/). It downloads Python 3.12 and pgserver into a temporary environment:

    uv run --python 3.12 --no-project --with pgserver --with "sqlalchemy>=2,<3" \\
        --with "psycopg[binary]>=3.2,<4" --with "openai>=2.24,<3" --with python-dotenv python scripts/pg_test.py
"""

import itertools
from pathlib import Path
import sys
import tempfile
import unittest

import pgserver
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import db  # noqa: E402

# Unix socket paths are capped at 103 bytes, so the data folder must have a short path.
server = pgserver.get_server(tempfile.mkdtemp(prefix="pg", dir="/tmp"), cleanup_mode="delete")
admin_url = server.get_uri().replace("postgresql://", "postgresql+psycopg://")
admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
counter = itertools.count()
original_init = db.Store.__init__


def postgres_store(self, url):
    """Every Store the tests create gets its own fresh Postgres database."""
    name = f"t{next(counter)}"
    with admin.connect() as conn:
        conn.execute(sa.text(f"CREATE DATABASE {name}"))
    original_init(self, sa.engine.make_url(admin_url).set(database=name).render_as_string(hide_password=False))


db.Store.__init__ = postgres_store
import tests  # noqa: E402

suite = unittest.TestSuite()
for case in (tests.TestStore, tests.TestAccounts, tests.TestQuota):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
