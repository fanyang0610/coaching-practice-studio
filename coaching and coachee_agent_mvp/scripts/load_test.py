#!/usr/bin/env python3
"""Simulate many users chatting at once against a local Coaching Practice Studio, with a fake LLM.

The fake model answers every call after a fixed delay and streams its reply, so the
numbers measure the app's own queueing rather than a real provider. Nothing is billed.
Each simulated person gets their own account in a throwaway database and signs in first.

    python3 scripts/load_test.py --users 50 --messages 3
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socketserver
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import httpx


ROOT = Path(__file__).resolve().parents[1]
FAKE_REPLY = "[[STAY]] That sounds important to you. What would make the biggest difference this week?"
# Chinese sessions drop replies with no Chinese in them, so a Chinese request gets a Chinese reply.
FAKE_REPLY_ZH = "[[STAY]] 嗯，这对我挺重要的。 我也不太确定该从哪里开始。"


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # The stock server_bind does a reverse-DNS lookup that can hang; loopback needs no name.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def fake_case(body: dict) -> str | None:
    """A practice case as JSON when the app asks for one, built around the coach's topic if there is one."""
    system = (body.get("messages") or [{}])[0].get("content", "")
    if "coachee case" not in system:
        return None
    topic = re.search(r"<<(.+?)>>", system, re.DOTALL)
    chinese = "Simplified Chinese" in system
    if topic:
        intro = (f"我想聊聊这件事：{topic.group(1)}" if chinese else f"I'd like to talk about this: {topic.group(1)}")
    else:
        intro = "我最近总觉得工作和生活都很乱。" if chinese else "Lately everything at work feels a bit much."
    line = ["这对我很重要。", "我还不确定。"] if chinese else ["It matters to me.", "I'm not sure yet."]
    sections = {"contract": ("goal", "importance", "success"),
                "experience": ("reality", "obstacle", "strength", "past_success", "scale"),
                "action": ("possibility", "stretch", "support"),
                "value": ("commitment", "timeline", "risk", "accountability"), "closing": ("reflection",)}
    case = {"intro": intro, **{name: {key: line for key in keys} for name, keys in sections.items()}}
    return json.dumps(case, ensure_ascii=False)


def start_fake_llm(latency: float) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            time.sleep(latency)
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                chinese = "Simplified Chinese" in ((body.get("messages") or [{}])[0].get("content") or "")
                words = (FAKE_REPLY_ZH if chinese else FAKE_REPLY).split(" ")
                for i, word in enumerate(words):
                    chunk = {
                        "id": "fake",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": "fake",
                        "choices": [{"index": 0, "delta": {"content": word + (" " if i < len(words) - 1 else "")}, "finish_reason": None}],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(0.03)
                if (body.get("stream_options") or {}).get("include_usage"):
                    usage = {"id": "fake", "object": "chat.completion.chunk", "created": 0, "model": "fake", "choices": [],
                             "usage": {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940}}
                    self.wfile.write(f"data: {json.dumps(usage)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                return
            # Practice mode's stage labelling: a question about the situation, so the tracker visibly moves on.
            labelling = "You label one message" in ((body.get("messages") or [{}])[0].get("content") or "")
            content = "[[REALITY]]" if labelling else fake_case(body) or FAKE_REPLY
            payload = json.dumps({
                "id": "fake",
                "object": "chat.completion",
                "created": 0,
                "model": "fake",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = LocalHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


PASSWORD = "load-test-password"


def create_accounts(app_dir: Path, database_url: str, count: int) -> list[str]:
    sys.path.insert(0, str(app_dir))
    import accounts
    import db

    store = db.Store(database_url)
    password_hash = accounts.hash_password(PASSWORD)
    emails = [f"load{i}@example.com" for i in range(count)]
    for email in emails:
        store.create_user(email, email.split("@")[0], password_hash, consented=True)
    return emails


def start_app(app_dir: Path, port: int, llm_port: int, database_url: str) -> subprocess.Popen:
    env = {key: value for key, value in os.environ.items() if key not in ("SPACE_ID", "GRADIO_SERVER_NAME")}
    env.update({
        "OPENAI_API_KEY": "load-test",
        "OPENAI_BASE_URL": f"http://127.0.0.1:{llm_port}/v1",
        "OPENAI_MODEL": "fake",
        "GRADIO_SERVER_PORT": str(port),
        "ERICKSON_INBROWSER": "0",
        "DATABASE_URL": database_url,
        "ERICKSON_SECRET_KEY": secrets.token_hex(32),
    })
    proc = subprocess.Popen([sys.executable, "web_app.py"], cwd=app_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=2).status_code == 200:
                return proc
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("App did not start within 60 seconds.")


def find_fn_index(config: dict, name: str) -> int:
    for dep in config["dependencies"]:
        if dep.get("api_name") == name:
            return dep["id"]
    raise LookupError(f"No event named {name!r} in the app config.")


def run_event(client: httpx.Client, base: str, fn_index: int, data: list, session_hash: str) -> tuple[float, float]:
    """Return (seconds until the reply's first words, seconds until done) for one queued event.

    A streaming reply first echoes the user's message, so its first words arrive with the second update.
    A non-streaming reply shows everything at completion.
    """
    start = time.monotonic()
    joined = client.post(f"{base}/gradio_api/queue/join", json={"data": data, "fn_index": fn_index, "session_hash": session_hash})
    joined.raise_for_status()
    event_id = joined.json()["event_id"]
    first = None
    updates = 0
    with client.stream("GET", f"{base}/gradio_api/queue/data", params={"session_hash": session_hash}) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            message = json.loads(line[5:])
            if message.get("event_id") != event_id:
                continue
            if message["msg"] == "process_generating":
                updates += 1
                if updates == 2 and first is None:
                    first = time.monotonic() - start
            if message["msg"] == "process_completed" and first is None:
                first = time.monotonic() - start
            if message["msg"] == "process_completed":
                if not message.get("success", True):
                    raise RuntimeError(f"Event failed: {message.get('output')}")
                return first, time.monotonic() - start
    raise RuntimeError("Stream closed before the event completed.")


def sign_in(client: httpx.Client, base: str, email: str) -> None:
    response = client.post(f"{base}/login", data={"email": email, "password": PASSWORD})
    if response.status_code != 303:
        raise RuntimeError(f"Sign-in failed for {email}: {response.status_code}")


def simulate_user(base: str, email: str, load_fn: int, respond_fn: int, messages: int) -> list[tuple[float, float]]:
    session_hash = uuid.uuid4().hex[:11]
    timings = []
    with httpx.Client(timeout=600) as client:
        sign_in(client, base, email)
        run_event(client, base, load_fn, [None, "coach", "AI", "English"], session_hash)
        for turn in range(messages):
            timings.append(run_event(client, base, respond_fn, [f"Message {turn + 1}: I want to focus better.", [], None, "coach", "AI", "English"], session_hash))
    return timings


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-dir", type=Path, default=ROOT)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--messages", type=int, default=3, help="Messages each simulated user sends.")
    parser.add_argument("--latency", type=float, default=1.5, help="Seconds the fake model waits before answering.")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args(argv)

    workdir = tempfile.mkdtemp(prefix="erickson-load-")
    database_url = f"sqlite:///{workdir}/load.db"
    emails = create_accounts(args.app_dir.resolve(), database_url, args.users)
    llm = start_fake_llm(args.latency)
    app = start_app(args.app_dir.resolve(), args.port, llm.server_address[1], database_url)
    base = f"http://127.0.0.1:{args.port}"
    try:
        with httpx.Client(timeout=30) as client:
            sign_in(client, base, emails[0])
            config = client.get(f"{base}/config").json()
        load_fn, respond_fn = find_fn_index(config, "initial_load"), find_fn_index(config, "respond")
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.users) as pool:
            results = list(pool.map(lambda email: simulate_user(base, email, load_fn, respond_fn, args.messages), emails))
        wall = time.monotonic() - started
        import db

        store = db.Store(database_url)
        tokens = sum(store.usage_by_user_since(db.utcnow() - db.dt.timedelta(hours=1)).values())
        saved_turns = sum(row["user_turns"] for email in emails for row in store.list_sessions(store.get_user_by_email(email)["id"]))
    finally:
        app.terminate()
        app.wait(timeout=10)
        llm.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)

    first = [t[0] for user in results for t in user]
    done = [t[1] for user in results for t in user]
    print(f"{args.users} users x {args.messages} messages against {args.app_dir.resolve().name} (fake model latency {args.latency}s)")
    print(f"  first words of reply:  median {statistics.median(first):.1f}s, p95 {percentile(first, 95):.1f}s, worst {max(first):.1f}s")
    print(f"  full reply:           median {statistics.median(done):.1f}s, p95 {percentile(done, 95):.1f}s, worst {max(done):.1f}s")
    print(f"  wall time {wall:.1f}s for {len(done)} replies")
    print(f"  saved {saved_turns} user turns and metered {tokens} tokens in the database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
