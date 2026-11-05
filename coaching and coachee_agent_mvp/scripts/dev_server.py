#!/usr/bin/env python3
"""Run the app locally for UI review: a fake AI model, a throwaway database and three seeded test accounts.

    python3 scripts/dev_server.py            # then open http://127.0.0.1:8797
    python3 scripts/dev_server.py --email    # also show "Forgot your password?" (mail goes nowhere)
    python3 scripts/dev_server.py --ai-down  # every AI request fails, as when the AI account is out of credit

Accounts (all share the printed throwaway password): admin@example.test, mentor@example.test and
member@example.test (assigned to the mentor, with one finished practice session and one open coaching session).
Nothing here touches your real API key or database.
"""

import argparse
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import runpy
import secrets
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import accounts  # noqa: E402
from coach_agent import CoachAgent  # noqa: E402
from coachee_agent import CoacheeAgent  # noqa: E402
import db  # noqa: E402
import load_test  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--port", default="8797")
parser.add_argument("--email", action="store_true", help="Pretend SMTP is configured.")
parser.add_argument("--ai-down", action="store_true", help="Refuse every AI request with 402, like an account out of credit.")
args = parser.parse_args()

database_url = f"sqlite:///{tempfile.mkdtemp(prefix='studio-dev-')}/dev.db"
store = db.Store(database_url)
password = secrets.token_urlsafe(12)
hashed = accounts.hash_password(password)
admin = store.create_user("admin@example.test", "Avery Admin", hashed, role="admin", consented=True)
mentor = store.create_user("mentor@example.test", "Taylor Mentor", hashed, role="trainer", consented=True)
member = store.create_user("member@example.test", "Lin Member", hashed, trainer_id=mentor, consented=True)

practice = CoacheeAgent(mode="llm", language="en")
practice.context = [
    {"role": "coachee", "content": "I keep stepping in to fix every problem on my team."},
    {"role": "coach", "content": "What would it look like if you trusted them with one problem this week?"},
    {"role": "coachee", "content": "Honestly, scary. But I think Maya could own the release checklist."},
]
practice.session_complete = True
practice_id = store.create_session(member, "coachee", "en", "llm", "CLOSING", practice.to_dict())
store.save_session(practice_id, state=practice.to_dict(), status="completed", stage="CLOSING", user_turns=1, language="en", mode="llm")
coach = CoachAgent(mode="llm", language="en")
coach.context = [{"role": "coach", "content": "What would you like to focus on today?"}]
store.create_session(member, "coach", "en", "llm", "CONTRACT", coach.to_dict())
store.save_profile(member, "coachee", {"strengths": ["Asks open questions"], "growth_areas": ["Leaves too little silence"],
                                       "last_updated": "2026-10-14 01:00 UTC"})
store.record_usage(member, practice_id, "fake", 4200, 800)
store.create_invite(admin, role="trainer", email="new.mentor@example.test")

def start_out_of_credit_llm():
    """A stand-in AI service that refuses every request the way OpenRouter does when the account has no credit left."""
    class Refuse(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            body = json.dumps({"error": {"message": "Insufficient credits", "code": 402}}).encode()
            self.send_response(402)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = load_test.LocalHTTPServer(("127.0.0.1", 0), Refuse)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


llm = start_out_of_credit_llm() if args.ai_down else load_test.start_fake_llm(0.8)
os.environ.update({
    "OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": f"http://127.0.0.1:{llm.server_address[1]}/v1", "OPENAI_MODEL": "fake",
    "DATABASE_URL": database_url, "STUDIO_SECRET_KEY": secrets.token_hex(32), "GRADIO_SERVER_PORT": args.port,
    "STUDIO_INBROWSER": "0", "GRADIO_SERVER_NAME": "127.0.0.1",
})
if args.email:
    os.environ.update({"SMTP_HOST": "127.0.0.1", "SMTP_PORT": "2525"})
print(f"Test accounts: admin@example.test, mentor@example.test, member@example.test — password: {password}", flush=True)
runpy.run_path("web_app.py", run_name="__main__")
