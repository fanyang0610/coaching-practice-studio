import os
import re
import signal
import subprocess
import sys
from pathlib import Path


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_PROFILE = "/private/tmp/erickson-coach-chrome-profile"
LOCAL_URL_RE = re.compile(r"Running on local URL:\s+(https?://\S+)")


def chrome_command(url: str) -> list[str]:
    return [
        str(CHROME),
        f"--user-data-dir={CHROME_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]


def open_browser(url: str) -> None:
    if CHROME.exists():
        subprocess.Popen(chrome_command(url), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    subprocess.Popen(["/usr/bin/open", "-a", "Safari", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch() -> int:
    env = os.environ.copy()
    env["ERICKSON_INBROWSER"] = "0"

    proc = subprocess.Popen(
        [sys.executable, "-u", "app.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    opened = False

    def stop_server(signum, frame):
        if proc.poll() is None:
            proc.terminate()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            match = LOCAL_URL_RE.search(line)
            if match and not opened:
                open_browser(match.group(1))
                opened = True
        return proc.wait()
    except KeyboardInterrupt:
        print("Stopping Erickson Coach...", flush=True)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(launch())
