# Handoff: Coaching Practice Studio / 教练练习室

Last updated 2026-10-14. Read this file fully before changing anything. Then read `AGENTS.md`, `README.md` and `DESIGN.md` in this folder.

## Prompt to start the next session

Open the new session in this folder:
`/Users/fanyang/Documents/My Documents/Vibe Coding/erickson-coach-scale/coaching and coachee_agent_mvp`

Then paste:

> Continue work on Coaching Practice Studio (教练练习室). Read `docs/HANDOFF.md` first, then `AGENTS.md`, `README.md` and `DESIGN.md`. We are on branch `scale/phase-0-1` in the worktree folder `erickson-coach-scale`. The original version on `main` is my fallback; don't touch it. Before deploying I still want to make some changes to the app. I'll describe them next. Confirm you've read the handoff by summarising the current state in five lines, then wait for my first change.

---

## 1. What this is and who it is for

- A bilingual (English / Simplified Chinese) Gradio web app for practising solution-focused coaching:
  - **AI Coach** (module key `coach`): the AI coaches the person on something real.
  - **AI Coachee Lab** (module key `coachee`): the person practises coaching an AI client, then gets a score and feedback.
- Both modules follow a five-stage flow: Contract → Reality → Possibilities → Commitment → Closing.
- The owner (Fan) built it for coaching friends. It is **free and non-commercial**.
- Goal: invite **50+ people**. That means a large group of learners in **mainland China**, plus English-speaking users in other countries.
- **Legal caution:** it was originally based on the Erickson coaching school. It has been deliberately rebranded so that no school's name, logo, colours or proprietary terms (e.g. "Arrow Model") appear in the UI or the AI prompts. The test class `TestIndependentBranding` enforces this. Keep it that way.

## 2. Where everything is

| What | Where |
|---|---|
| **Current work** | `Vibe Coding/erickson-coach-scale/coaching and coachee_agent_mvp/` on branch **`scale/phase-0-1`**. This is a git worktree of the repo rooted at `Vibe Coding/`. |
| Original (fallback) | `Vibe Coding/coaching and coachee_agent_mvp/` on `main`. Don't modify. |
| Stale copies | `Vibe Coding/coaching_agent_mvp/` and `Vibe Coding/coaching_agent_mvp branch/` (March, unused). A leftover worktree from a side session is at `coaching_agent_mvp branch/.claude/worktrees/hopeful-aryabhata-bef63a`; its fix is already merged and the folder can be removed. |
| GitHub | `github.com/fanyang0610/Erickson-Coach-MVP`. **Public**, still named "Erickson". **Nothing from this branch has been pushed.** `main` is also 2 commits ahead of `origin/main` (older work). Push only when Fan asks; suggest making the repo private first. |
| Hugging Face Space | `fanyang0610/Erickson-Coach-App` (public, free CPU). It still runs the **old** version, which has no sign-in and leaves the API key open to anyone. Fan plans to rename it. `scripts/deploy_hf_space.py` has `DEFAULT_SPACE_ID`, which must be updated after the rename. The `hf` CLI on this Mac is logged in as `fanyang0610`. |
| Local secrets | `.env` in the project folder (OpenRouter key, `OPENAI_MODEL=openrouter/free`). It is not committed. Never print its values. |

The branch has 8 commits on top of `main`:
`177b7b7` Phase 0–1 · `75e751e` HF helper fix · `d29a8bd` Phase 2–3 · `45da42d` Phase 4 · `ca20351` self-check fixes · `eba6490` DeepSeek / fonts / voice · `68b1f12` rebrand · `5ad48be` help page (plus this handoff commit).

## 3. Decisions already made (don't reopen them without Fan)

- **Hosting:** stay on **Hugging Face** for now. Alibaba Cloud and a Hong Kong server are undecided. Hugging Face is generally unreachable from mainland China, so a Hong Kong or Singapore server is the likely move before the China group joins.
- **Model:**
  - Plan for the first test: OpenRouter with `openai/gpt-4o-mini`. Fan's account currently has **$0 credit**.
  - `openrouter/free` is unusable: in a sample, 1 in 6 replies was usable.
  - DeepSeek is supported (`OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL=deepseek-flash`; thinking is switched off automatically) but **not yet tested with a real key**.
  - **Key test, 2026-10-14.** Fan added $5. The OpenRouter key in `.env` works and has its own $4 spending cap.
    - From this Mac (China time zone), `openai/gpt-4o-mini` is refused with HTTP 403 "violation of provider Terms Of Service". Most likely OpenAI doesn't serve mainland China or Hong Kong. **A Hong Kong server would hit the same block**, so pair HK hosting with DeepSeek, or host in Singapore.
    - `deepseek/deepseek-chat` through OpenRouter works from this Mac.
    - `openrouter/free` returned an empty reply.
    - The old HF Space (model variable `openai/gpt-4o-mini`) still shows "no valid opening", and its attempt didn't register on the `.env` key. The account has at least one other key (about $0.08 spent elsewhere), so the Space secret probably holds a different, capped or old key. Fan to check OpenRouter → Keys, and replace the Space's `OPENAI_API_KEY` if needed.
- **Signup:** invite-only. Roles are admin / **Mentor** (key `trainer`) / **Member** (key `user`).
  - Mentors are real people, such as coaching instructors, who review the practice of the members assigned to them. Both modules are always a person talking with the AI.
  - Fan was confused by "trainer/trainee" earlier. Always explain roles plainly.
- **Who sees transcripts** (Fan decided 2026-10-14 that the admin must not read conversations, so members feel safe to speak openly):
  - The member sees their own sessions.
  - Their assigned mentor sees their Coachee Lab sessions, plus any AI Coach session the member explicitly shares. This also applies to an admin who is assigned as someone's mentor, because the member can see who their mentor is.
  - **The admin sees no conversation content**, in either module. The Admin page lists sessions (who, when, stage, length) without "View" links.
  - Changing a member's mentor makes their shared AI Coach sessions private again.
  - Every view by someone other than the owner is written to the audit log.
  - The privacy page says honestly that whoever runs the server and the AI provider handle the data.
- **Allowances:** rolling 24 hours, per module.
  - Member: 3 AI Coach and 5 Coachee Lab finished sessions, 400k tokens shared.
  - Mentor: 10 / 20 / 1.5M. Admin: no limit.
  - Started sessions are capped at twice the finished allowance.
  - Admins can edit all of this on the Admin page. Over the limit, new sessions open in template mode, and a running session is never cut off.
- **Name:** "Coaching Practice Studio / 教练练习室". Internal identifiers keep the old prefix on purpose (`ERICKSON_*` settings, class names `EricksonCoachingAgent` / `EricksonCoacheeAgent`, cookies `erickson_session` / `erickson_lang`, `erickson.db`, `.erickson_secret`).
- **Language:**
  - The app and the account pages share one setting (cookie `erickson_lang`). A first visit follows the browser.
  - A reopened session is translated into the person's current language.
  - Every string must exist in both languages; tests check this.

## 4. What is built (module map)

| File | Role |
|---|---|
| `web_app.py` | Gradio UI and callbacks. `create_app()` mounts Gradio in FastAPI behind sign-in (`auth_dependency`), and `launch_demo()` runs uvicorn. Handlers take `request: gr.Request`, and `request.username` is the signed-in user id. Handles session open/restore/save, quotas, rate limits, the crisis check, feedback, and background profile learning. |
| `account_pages.py` | Server-rendered pages: `/login`, `/setup` (first admin, local only), `/invite/{code}`, `/reset/{token}`, `/forgot` (only with SMTP), `/account`, `/sessions/{id}`, `/mentor`, `/admin`, `/privacy`, `/help` (public), `/icons/*`, `/healthz`. All strings are in `T["en"]` / `T["zh"]`. |
| `db.py` | SQLAlchemy Core storage: users, invites, password_resets, coaching_sessions (state JSON), profiles, usage_events, feedback, settings, audit_log. SQLite by default; Postgres via `DATABASE_URL`. |
| `accounts.py` | scrypt passwords, signed cookies (invalid after a password change), CSRF, login throttle, `can_view_session`. |
| `quota.py` | Allowances, role defaults with admin overrides (settings key `role_limits`), per-minute message limiter. |
| `coaching_core.py` | Shared OpenAI-compatible client (45 s timeout, 1 retry), usage metering, streaming, the `[[STAY]]`/`[[NEXT]]`/`[[END]]` stage markers, batched translation, `OPENAI_EXTRA_BODY`, and DeepSeek thinking off. |
| `coach_agent.py` / `coachee_agent.py` | Agents with `stream_response()`, `to_dict()`/`from_dict()`. The reply itself decides the stage via markers, with no separate check call. |
| `memory.py` | Per-user, per-module insight profile, capped at 8 items per list. |
| `safety.py` | Crisis-language check (AI Coach only) and a fixed bilingual safety reply. |
| `mailer.py` | Optional SMTP for self-service password resets. |
| `web_assets.py` | UI strings (`UI`), CSS, browser JS (TTS, mic with failure hints, language cookie). |
| `scripts/` | `check_project.py` (full check), `load_test.py` (50 simulated users), `dev_server.py` (UI review with a fake model and seeded accounts), `pg_test.py` (Postgres tests), `manage.py` (shell admin), `deploy_hf_space.py`, `needs_hf_upload.py`. |
| `Dockerfile` | For an always-on host later. Never built (there's no Docker on this Mac). Excluded from HF uploads. |

## 5. How to run and verify

```bash
python3 tests.py                                   # 153 tests, about 3 s; tests blank the API key so they never call a real model
python3 scripts/check_project.py --browser --launcher   # tests, compile, HF dry-run, signed-in desktop and iPhone screenshots, launcher rebuild
python3 scripts/load_test.py --users 50 --messages 3    # median about 3.6 s to first words under a 50-user burst
python3 scripts/dev_server.py                       # UI review on http://127.0.0.1:8797 with seeded admin/mentor/member accounts
uv run -q --python 3.10 --no-project --with-requirements requirements.txt python tests.py   # the HF Space runs Python 3.10
```

Postgres check: run the `uv run …` command in the `scripts/pg_test.py` docstring (21 tests).

Screenshots from the browser check land in `/private/tmp/erickson-check/erickson-desktop.png` and `erickson-mobile.png`. For live UI review, run `scripts/dev_server.py` from Bash in the background, then open it in the built-in browser pane. The pane's own `preview_start` with a launch.json got stuck reading the Documents folder.

## 6. How Fan wants work done

- **Every UI/UX change must be checked at laptop and phone (about 375–390 px) widths, in both English and Chinese.** This is in `AGENTS.md` and Fan repeated it.
- After functional changes, rebuild the launcher (`check_project.py --launcher`). The launcher opens whichever folder it sits in.
- Follow `DESIGN.md`: a calm blue-white-gold palette, and **no web fonts** (Google Fonts is blocked in mainland China).
- Explain things in **plain language**. Fan is not a developer and gets confused by jargon.
- Fan said to keep going on implementation without stopping for opinions. Still **ask before outward actions**: pushing to GitHub, deploying to Hugging Face, spending money, or creating accounts. Fan said "worst case I just dump this branch".
- Commit on `scale/phase-0-1` with clear messages. Keep `main` untouched.

## 7. Open items

**Fan's to-dos before the first real user** (README, "Deploying for Invited Users"):

1. OpenRouter: add about $10 credit, and set a credit limit on the key.
2. Neon (neon.tech): create a free project in the AWS US East region, then copy the `postgresql://…?sslmode=require` connection string.
3. Hugging Face: rename the Space (e.g. `Coaching-Practice-Studio`), then add these Space secrets:
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
   - `OPENAI_MODEL=openai/gpt-4o-mini`
   - `DATABASE_URL`
   - `ERICKSON_SECRET_KEY` (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
   - `ERICKSON_ADMIN_EMAIL`
   - `ERICKSON_ADMIN_PASSWORD` (at least 10 characters)
   - `ERICKSON_DATA_LOCATIONS` (e.g. "Server: Hugging Face (USA) · AI: OpenAI via OpenRouter (USA)")
4. Rename the GitHub repo and consider making it private.

**Next steps for Claude, once Fan says "secrets are set, deploy":**

1. Update `DEFAULT_SPACE_ID` in `scripts/deploy_hf_space.py` and the Space address in `README.md`.
2. Run `python3 scripts/deploy_hf_space.py`. Ask before uploading, because it is outward-facing.
3. Watch the Space logs until it's running. This is the first time FastAPI + uvicorn + mounted Gradio runs on HF; HF sets `GRADIO_SERVER_NAME=0.0.0.0` and `GRADIO_SERVER_PORT=7860`.
4. Have Fan test using the direct `https://<space>.hf.space` address. Sign-in cookies don't work inside the huggingface.co page frame.
5. Run one real session per module to confirm the stage markers work with a paid model.

**Known limits (also in README "Known Limits"):**
- One server process only (in-memory rate limits).
- No schema migrations yet; Alembic is needed before changing existing columns after launch.
- One organisation.
- A few built-in Gradio labels stay in English.
- Sign-in is by email only.
- Gradio's page template still has Google Fonts preconnect hints and a Cloudflare script; these don't block the page.

## 8. Gotchas learned the hard way

- **Real model calls in tests:** `.env` loads the real key, so `tests.py` blanks `OPENAI_API_KEY` at the top, and so does the browser check in `scripts/check_project.py` (before 2026-10-14 it used up free-model requests on every run). Never open an `llm`-mode session in a test without patching. One test once did, which slowed the suite and spent free quota.
- **Python 3.10 on HF:** don't use `datetime.UTC` (it's 3.11+); use `datetime.timezone.utc`. Run the 3.10 suite before deploying.
- **JavaScript inside Python strings:** `\'` in a normal Python string becomes `'` and breaks JS. `TestProviderAndRegionSupport.test_browser_scripts_are_valid_javascript` runs `node --check` on the evaluated scripts. Use typographic apostrophes (’) in JS text.
- **Gradio fonts:** Gradio wraps theme font names in quotes, so generic names like `system-ui` stop working. Use concrete font names, ending with `sans-serif`.
- **`api_visibility="private"` is not security:** it only hides endpoints from the API page. Sign-in (`auth_dependency`) is the real gate.
- **Session state:** `gr.State` is copied only when a browser session starts, so the per-agent locks in a `WeakKeyDictionary` are valid.
- **Reopening sessions:** a stored session that can't be read back is marked abandoned and a fresh one opens. Don't let restore errors crash `initial_load`.
- **Hosted login loop:** cookies are `Secure` when the app is public, so plain `http` on a public server breaks sign-in. Any non-HF host needs HTTPS.
- **DNS hang:** Python's `http.server` `server_bind` does a reverse-DNS lookup that hung on this Mac. `scripts/load_test.py` overrides it (`LocalHTTPServer`).
- **Free models:** `openrouter/free` returns empty replies, a safety classifier's output, or leaked reasoning, and hits 429 rate limits often.
