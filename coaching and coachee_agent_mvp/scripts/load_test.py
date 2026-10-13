#!/usr/bin/env python3
"""Simulate many users chatting at once against a local Erickson Coach, with a fake LLM.

The fake model answers every call after a fixed delay and streams its reply, so the
numbers measure the app's own queueing rather than a real provider. Nothing is billed.

    python3 scripts/load_test.py --users 50 --messages 3
    python3 scripts/load_test.py --app-dir "../some other copy" --users 20   # compare versions
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socketserver
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import uuid

import httpx


ROOT = Path(__file__).resolve().parents[1]
FAKE_REPLY = "[[STAY]] That sounds important to you. What would make the biggest difference this week?"


class LocalHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        # The stock server_bind does a reverse-DNS lookup that can hang; loopback needs no name.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


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
                words = FAKE_REPLY.split(" ")
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
                self.wfile.write(b"data: [DONE]\n\n")
                return
            payload = json.dumps({
                "id": "fake",
                "object": "chat.completion",
                "created": 0,
                "model": "fake",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": FAKE_REPLY}, "finish_reason": "stop"}],
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


def start_app(app_dir: Path, port: int, llm_port: int) -> subprocess.Popen:
    env = {key: value for key, value in os.environ.items() if key not in ("ERICKSON_USERS", "SPACE_ID", "GRADIO_SERVER_NAME")}
    env.update({
        "OPENAI_API_KEY": "load-test",
        "OPENAI_BASE_URL": f"http://127.0.0.1:{llm_port}/v1",
        "OPENAI_MODEL": "fake",
        "GRADIO_SERVER_PORT": str(port),
        "ERICKSON_INBROWSER": "0",
    })
    proc = subprocess.Popen([sys.executable, "web_app.py"], cwd=app_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/config", timeout=2).status_code == 200:
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


def simulate_user(base: str, load_fn: int, respond_fn: int, messages: int) -> list[tuple[float, float]]:
    session_hash = uuid.uuid4().hex[:11]
    timings = []
    with httpx.Client(timeout=600) as client:
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

    llm = start_fake_llm(args.latency)
    app = start_app(args.app_dir.resolve(), args.port, llm.server_address[1])
    base = f"http://127.0.0.1:{args.port}"
    try:
        config = httpx.get(f"{base}/config", timeout=10).json()
        load_fn, respond_fn = find_fn_index(config, "initial_load"), find_fn_index(config, "respond")
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.users) as pool:
            results = list(pool.map(lambda _: simulate_user(base, load_fn, respond_fn, args.messages), range(args.users)))
        wall = time.monotonic() - started
    finally:
        app.terminate()
        app.wait(timeout=10)
        llm.shutdown()

    first = [t[0] for user in results for t in user]
    done = [t[1] for user in results for t in user]
    print(f"{args.users} users x {args.messages} messages against {args.app_dir.resolve().name} (fake model latency {args.latency}s)")
    print(f"  first words of reply:  median {statistics.median(first):.1f}s, p95 {percentile(first, 95):.1f}s, worst {max(first):.1f}s")
    print(f"  full reply:           median {statistics.median(done):.1f}s, p95 {percentile(done, 95):.1f}s, worst {max(done):.1f}s")
    print(f"  wall time {wall:.1f}s for {len(done)} replies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
