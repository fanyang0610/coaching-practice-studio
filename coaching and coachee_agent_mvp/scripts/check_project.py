#!/usr/bin/env python3
"""Run repeatable local checks for Coaching Practice Studio."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_ICON_SOURCE = ROOT / "assets" / "icons" / "StudioIcon.icns"
LAUNCHER_ICON_TARGET = ROOT / "Coaching Practice Studio.app" / "Contents" / "Resources" / "applet.icns"
PYTHON_FILES = [
    "app.py",
    "cli_app.py",
    "mac_launcher.py",
    "coach_agent.py",
    "coach_data.py",
    "coachee_agent.py",
    "coachee_data.py",
    "coaching_core.py",
    "memory.py",
    "web_assets.py",
    "web_app.py",
    "tests.py",
    "manual_ui_probe.py",
    "scripts/deploy_hf_space.py",
    "scripts/check_project.py",
    "scripts/load_test.py",
    "scripts/manage.py",
    "scripts/dev_server.py",
    "db.py",
    "accounts.py",
    "account_pages.py",
    "quota.py",
    "safety.py",
    "mailer.py",
]


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print("$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def wait_for_url(url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def probe_login(database_url: str, secret: str) -> str:
    """Create a throwaway probe account and return a signed-in session cookie for it."""
    sys.path.insert(0, str(ROOT))
    import accounts
    import db

    store = db.Store(database_url)
    user_id = store.create_user("probe@example.com", "Probe", accounts.hash_password(secrets.token_urlsafe(16)), role="admin", consented=True)
    return f"{accounts.SESSION_COOKIE}={accounts.make_session_cookie(store.get_user(user_id), secret)}"


def run_browser_check(port: int) -> None:
    workdir = tempfile.mkdtemp(prefix="erickson-check-")
    env = os.environ.copy()
    # An empty key stops web_app from loading the real one from .env, so screenshots never call (or use up) the model.
    env["OPENAI_API_KEY"] = ""
    env["ERICKSON_INBROWSER"] = "0"
    env["GRADIO_SERVER_PORT"] = str(port)
    env["DATABASE_URL"] = f"sqlite:///{workdir}/check.db"
    env["ERICKSON_SECRET_KEY"] = secrets.token_hex(32)
    cookie = probe_login(env["DATABASE_URL"], env["ERICKSON_SECRET_KEY"])
    proc = subprocess.Popen(
        [sys.executable, "web_app.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        wait_for_url(url)
        run([sys.executable, "manual_ui_probe.py", "--url", url, "--out-dir", "/private/tmp/erickson-check", "--cookie", cookie])
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(workdir, ignore_errors=True)


def compile_launcher() -> None:
    run(["osacompile", "-o", "Coaching Practice Studio.app", "Coaching Practice Studio Launcher.applescript"])
    shutil.copyfile(LAUNCHER_ICON_SOURCE, LAUNCHER_ICON_TARGET)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Coaching Practice Studio project checks.")
    parser.add_argument("--browser", action="store_true", help="Run desktop and mobile browser screenshots.")
    parser.add_argument("--launcher", action="store_true", help="Recompile the local macOS launcher app.")
    parser.add_argument("--port", type=int, default=8787, help="Port for browser checks.")
    args = parser.parse_args(argv)

    run([sys.executable, "tests.py"])
    run([sys.executable, "-m", "py_compile", *PYTHON_FILES])
    run([sys.executable, "scripts/deploy_hf_space.py", "--dry-run"])

    if args.browser:
        run_browser_check(args.port)

    if args.launcher:
        compile_launcher()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
