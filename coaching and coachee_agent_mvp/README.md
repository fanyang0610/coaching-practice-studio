---
title: Erickson Coach App
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: "3.10"
app_file: app.py
pinned: false
fullWidth: true
---

# Erickson Coaching Agent MVP - Maintenance Guide

This original folder is the canonical project. Locally, `app.py` is a wrapper around `web_app.py`, and `web_app.py` contains the full UI implementation. For Hugging Face Spaces, the remote `app.py` must be uploaded from this local `web_app.py`; do not upload the local wrapper `app.py` as the Space entrypoint. The app defaults to AI mode and keeps the LLM API key on the server side; users do not enter or see API keys in the UI.

## Accounts and Roles

Erickson Coach is invite-only. Everyone signs in with an email and password, and new people join through one-use invite links.

Both coaching modules are always one person talking with the AI: in AI Coach the AI coaches the person, and in Coachee Lab the person practises coaching an AI coachee. The roles below are about people and who may read whose transcripts.

- **Admin** (管理员): sees every session, manages people, invites, roles, mentors and daily allowances, and reads the audit log (`/admin`).
- **Mentor** (导师; role key `trainer`): a real person, such as a coaching instructor, who reviews the practice of the members assigned to them. That covers their Coachee Lab sessions, plus any AI Coach session a member chooses to share (`/mentor`). Mentors can also invite members, who are then assigned to them. If you don't run supervised training, simply create no mentors.
- **Member** (成员; role key `user`): uses the coaching app, and manages their sessions, sharing, insights, password, data export and account deletion (`/account`).

AI Coach sessions are private by default, because people bring their real lives there; Coachee Lab sessions are visible to the member's mentor, because reviewing practice is the point of mentoring. Every time someone other than the owner opens a transcript, it is recorded in the audit log. Passwords are stored with scrypt, and sign-in cookies expire after 14 days and stop working when the password changes.

**Password resets.** An admin can always create a one-use reset link on the Admin page (or with `scripts/manage.py reset-link`) and send it however suits the person, for example by WeChat. If SMTP is configured (see below), the sign-in page also offers "Forgot your password?" and emails a link that works for 2 hours.

**First admin.** Locally, opening the app with an empty database shows a one-time setup page. On a hosted server, set `ERICKSON_ADMIN_EMAIL` and `ERICKSON_ADMIN_PASSWORD`; the admin is created at startup if no admin exists yet. From a shell you can also run `python3 scripts/manage.py create-admin you@example.com`.

## Configuration

| Variable | Needed | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | Server-side model key. Users never see it. |
| `OPENAI_MODEL` | yes | Use a paid model, e.g. `openai/gpt-4o-mini` on OpenRouter (about a cent per full session). `openrouter/free` routes to random free models that often return nothing or hit rate limits. |
| `OPENAI_BASE_URL` | for gateways | e.g. `https://openrouter.ai/api/v1`. |
| `DATABASE_URL` | hosted | Postgres URL, e.g. from Neon or Supabase. Without it, data goes to a local `erickson.db` SQLite file, which a Space restart erases. |
| `ERICKSON_SECRET_KEY` | hosted | Signs sign-in cookies. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`. Startup refuses to run publicly without it. |
| `ERICKSON_ADMIN_EMAIL`, `ERICKSON_ADMIN_PASSWORD` | first deploy | Creates the first admin (password at least 10 characters). |
| `ERICKSON_PUBLIC_URL` | optional | Base URL for invite and reset links if the server can't infer it. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | optional | Enables self-service password reset emails (port 587 uses STARTTLS, 465 uses SSL). |
| `SENTRY_DSN` | optional | Crash reports. Request bodies and local variables are never sent, so transcripts stay on the server. |
| `GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT` / `PORT` | hosting | Bind address and port. Hugging Face and Render set these. |

## Daily Allowances and Limits

Allowances use a rolling 24 hours and are checked when an AI session starts, so a session in progress is never cut off. Over the limit, new sessions open in template practice mode, with a notice saying roughly how many hours until AI is available again. AI Coach and Coachee Lab have separate session allowances, so practice drills don't use up someone's own coaching sessions; tokens are one shared daily backstop.

| Role | AI Coach sessions | Coachee Lab sessions | Tokens |
|---|---|---|---|
| Member | 3 | 5 | 400,000 |
| Mentor | 10 | 20 | 1,500,000 |
| Admin | no limit | no limit | no limit |

Started sessions (including ones left early, which still cost an opening call) are capped at twice the finished allowance. Admins change the role defaults in the "Daily AI allowances" panel on the Admin page, with no code change, and can override any one person's limits. A full session uses about 30,000–60,000 tokens; at gpt-4o-mini prices, even 50 members using every allowance every day would cost a few dollars a day, and typical use is far less. The defaults live in `quota.py`. Every model call's token usage is recorded per person and session. Other limits live in `web_app.py`: 2,000 characters per message, 40 messages per session, 10 messages per minute per person, and 24 model calls running at once, shared by all events.

Replies stream in. In one reply call the model also decides whether the coaching stage moves on (the `[[STAY]]`/`[[NEXT]]`/`[[END]]` markers), so a turn costs one model call.

## Deploying for Invited Users

1. Create a Postgres database (the Neon or Supabase free tiers are enough for 50 people) and set `DATABASE_URL`.
2. Switch `OPENAI_MODEL` to a paid model and set a monthly credit limit on the API key.
3. Set `ERICKSON_SECRET_KEY`, `ERICKSON_ADMIN_EMAIL` and `ERICKSON_ADMIN_PASSWORD`.
4. Deploy:
   - **Hugging Face Space:** add the variables above as Space secrets and run `python3 scripts/deploy_hf_space.py`. Share the direct `https://fanyang0610-erickson-coach-app.hf.space` URL; browsers block sign-in cookies inside the huggingface.co page frame.
   - **Always-on host (Render, Fly.io, Railway, Cloud Run):** build the included `Dockerfile` and set the same variables. It serves on `$PORT` (default 7860) and exposes `/healthz` for health checks.
5. Sign in as the admin, create trainer invites on the Admin page, and let trainers invite their trainees.
6. Point an uptime monitor at `/healthz`. Backups come from the managed Postgres provider.

To check concurrency before inviting people, simulate signed-in users against a fake model (nothing is billed):

```zsh
python3 scripts/load_test.py --users 50 --messages 3
```

## Languages

The app and the account pages share one language setting. On a first visit it follows the browser's language. Switching languages in the app, or with the link at the bottom of any account page, is remembered for both. A session reopened later is translated into the language the person uses now. Times on the account pages show in the reader's own time zone. Every page and message exists in English and Simplified Chinese, and the tests check that both sets of strings match.

## Privacy and Safety

- The privacy notice at `/privacy` explains what is stored and who can read it. New people must accept it when they sign up.
- Learners can download all their data as JSON or delete their account from the Account page.
- Messages in the AI Coach module that suggest someone may harm themselves get a fixed reply pointing to emergency services and findahelpline.com instead of coaching, and an entry in the audit log (without the message text). The coach prompt also tells the model to stop and point to help.
- Gradio's usage analytics are turned off.

## Known Limits

- **One server process.** Message rate limits and sign-in throttling live in memory, so run a single instance. That is plenty for 50 people.
- **No schema migrations yet.** New tables are created automatically, but changing existing columns after launch needs a migration tool such as Alembic.
- **One organisation.** Everyone shares one app with per-person data separation; there are no separate workspaces for different schools or teams.
- **Gradio's own small labels.** A few built-in Gradio labels, such as the thumbs-up tooltips, stay in English.
- **Sign-in is by email.** There is no phone-number or WeChat login.

## Launch Commands

Run the web app locally with either entrypoint:

```zsh
python3 app.py
# or
python3 web_app.py
```

The first local run opens a one-time page to create your admin account; after that, sign in at `/login`. The app does not auto-open the system browser by default, which avoids Chrome crash-reopen prompts from the normal user profile in Codex/sandbox runs. Set `ERICKSON_INBROWSER=1` explicitly if you want Gradio to open the browser anyway. For screenshot checks, keep using `ERICKSON_INBROWSER=0` with `manual_ui_probe.py`.

Run the terminal-only coaching flow with:

```zsh
python3 cli_app.py
```

Run the repeatable local verification suite with:

```zsh
python3 scripts/check_project.py
# Include desktop/mobile screenshots and launcher rebuild:
python3 scripts/check_project.py --browser --launcher
```

For Hugging Face Spaces, keep the README front matter pointed at `app_file: app.py`, but deploy by uploading local `web_app.py` to the remote path `app.py`:

```zsh
python3 scripts/deploy_hf_space.py
```

The helper stages a temporary Space folder using `.hfignore`, excludes the local wrapper `app.py`, copies local `web_app.py` to staged `app.py`, verifies that `web_app.py` is not uploaded under its own name, and then runs `hf upload`. Use `python3 scripts/deploy_hf_space.py --dry-run` to inspect the staged file list without uploading.

Before deploying an in-progress local diff, run `python3 scripts/needs_hf_upload.py` to report whether the changed files affect the hosted Space boundary or are local-only verification/development tooling.

## 1. One-Click Launch (macOS)

The project includes an **Erickson Coach.app** which can be double-clicked to start the application.
It runs `mac_launcher.py`, starts the server with `ERICKSON_INBROWSER=0`, and opens the UI in an isolated Chrome profile at `/private/tmp/erickson-coach-chrome-profile` so the normal Chrome profile cannot show crash-reopen prompts. It reads server-side settings from this workspace `.env` file when present, and stores local accounts and sessions in `erickson.db` in this folder. The launcher opens whichever folder the `.app` sits in, so copies of the project each launch their own version. After changing the AppleScript, re-compile the app with:

```zsh
osacompile -o "Erickson Coach.app" "Erickson Coach Launcher.applescript"
```

## Design Direction

The app uses `DESIGN.md` plus `DESIGN.erickson-edu.md`. The UI is intended to fit in one viewport on laptop and phone; only the chat transcript scrolls internally.

## 2. iOS Adaptation Checklist

Before every commit or major change, ensure the following iOS-specific adaptations are verified:

- **Vertical Layout**: The CSS in `web_app.py` (specifically `#app-shell`) uses `100dvh` (dynamic viewport height) to prevent address bar issues in Safari iOS.
- **Microphone Permissions**: The JavaScript `bindMic()` function manages permissions for the Web Audio API on mobile browsers.
- **Audio Autoplay**: iOS strictly blocks unmuted autoplay. The `unlockTts()` function in `web_app.py` primes the audio context on the first user interaction (click/touch).
- **Smooth Scrolling**: The `scroll_js` ensures the chatbot scrolls to the bottom correctly on mobile after each message.

## 3. Mandatory Pre-update Steps

For every change to the project:

1. **Re-verify State Transitions**: Run `python3 tests.py` to ensure the Erickson coaching logic is intact.
2. **Re-compile App Bundle**: Run the `osacompile` command above to ensure the `.app` remains synced with the latest codebase.
3. **Check iOS Viewport**: Verify that no new elements break the "One Page" layout on mobile Safari.
4. **Compile Check**: `scripts/check_project.py` compiles every Python file in the project.

`python3 scripts/check_project.py --browser --launcher` runs these checks through the project helper. The browser check signs in with a throwaway probe account in a temporary database, then captures desktop and iPhone screenshots of the coaching page.

Before uploading to Hugging Face, exclude `.env`, `erickson.db`, `user_profile.json`, caches, the Docker files and the local macOS app bundle. The project `.hfignore` and `.gitignore` list these local-only artifacts. Also remember that the Space entrypoint is remote `app.py` built from local `web_app.py`, not the local wrapper `app.py`.
