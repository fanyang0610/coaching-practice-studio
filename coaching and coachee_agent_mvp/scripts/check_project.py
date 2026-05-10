#!/usr/bin/env python3
"""Run repeatable local checks for Erickson Coach."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_ICON_SOURCE = ROOT / "assets" / "icons" / "EricksonCoach.icns"
LAUNCHER_ICON_TARGET = ROOT / "Erickson Coach.app" / "Contents" / "Resources" / "applet.icns"
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


def run_browser_check(port: int) -> None:
    env = os.environ.copy()
    env["ERICKSON_INBROWSER"] = "0"
    env["GRADIO_SERVER_PORT"] = str(port)
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
        run([sys.executable, "manual_ui_probe.py", "--url", url, "--out-dir", "/private/tmp/erickson-check"])
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def compile_launcher() -> None:
    run(["osacompile", "-o", "Erickson Coach.app", "Erickson Coach Launcher.applescript"])
    shutil.copyfile(LAUNCHER_ICON_SOURCE, LAUNCHER_ICON_TARGET)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Erickson Coach project checks.")
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
