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
| GitHub | `github.com/fanyang0610/coaching-practice-studio`. Renamed from `Erickson-Coach-MVP` and made **private** on 2026-10-15; no keys or secret files were ever in its history. `scale/phase-0-1` was pushed that day as a backup (with Fan's OK). `origin/main` is untouched, and local `main` is still 2 commits ahead of it (older work). Push only when Fan asks. |
| Hugging Face Space | `fanyang0610/Coaching-Practice-Studio` (renamed from `Erickson-Coach-App` on 2026-10-15; public, free CPU), at `https://fanyang0610-coaching-practice-studio.hf.space`. `DEFAULT_SPACE_ID` in `scripts/deploy_hf_space.py` matches. **The new version was deployed on 2026-10-15** (branch `scale/phase-0-1`, Neon database, admin created from the Space secrets), replacing the old open version. The old `erickson-coach-app` address no longer works. Variables: `OPENAI_BASE_URL`, `OPENAI_MODEL=deepseek/deepseek-chat`, `ERICKSON_DATA_LOCATIONS`. The `hf` CLI on this Mac is logged in as `fanyang0610`. |
| Local secrets | `.env` in the project folder (OpenRouter key, `OPENAI_MODEL=openrouter/free`). It is not committed. Never print its values. |

The branch has 8 commits on top of `main`:
`177b7b7` Phase 0–1 · `75e751e` HF helper fix · `d29a8bd` Phase 2–3 · `45da42d` Phase 4 · `ca20351` self-check fixes · `eba6490` DeepSeek / fonts / voice · `68b1f12` rebrand · `5ad48be` help page (plus this handoff commit).

## 3. Decisions already made (don't reopen them without Fan)

- **Hosting:** stay on **Hugging Face** (free). Fan reports (2026-10-15) that users in mainland China open the HF Space without a VPN. Still check the new version with China testers on several networks, because `.hf.space` access can vary and change. The fallback is a Hong Kong or Singapore server (not mainland: ICP filing plus generative-AI rules), with the database in the same region.
- **Database:** Neon free tier, region **AWS US East**, next to the HF Space. Use the direct connection (pooling off), which is the tested path.
- **Model:**
  - Plan for the first test: OpenRouter with `openai/gpt-4o-mini`. Fan's account currently has **$0 credit**.
  - `openrouter/free` is unusable: in a sample, 1 in 6 replies was usable.
  - DeepSeek is supported (`OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL=deepseek-flash`; thinking is switched off automatically) but **not yet tested with a real key**.
  - **Key test, 2026-10-14.** Fan added $5.
    - **`openai/gpt-4o-mini` is refused for this OpenRouter account** with HTTP 403 "The request is prohibited due to a violation of provider Terms Of Service". OpenRouter saw the test connection as US (`openrouter.ai/cdn-cgi/trace` gave `loc=US`, via Fan's VPN), so it is not about the caller's location. It looks account-level: a brand-new key didn't help on the HF Space either. The cause isn't confirmed; possibly the account or payment country.
    - `deepseek/deepseek-chat` through OpenRouter works on the same account.
    - `openrouter/free` returned an empty reply.
    - Fan deleted the key that was in `.env` and made a new one, which went into the HF Space secret. **The `.env` key is now dead**: Fan has to paste the new key into `.env` for local runs.
    - Refused (403) requests don't show up in a key's usage, so usage numbers can't tell you which key a Space is using.
    - **Fix applied (with Fan's OK):** the old Space's `OPENAI_MODEL` variable was changed from `openai/gpt-4o-mini` to `deepseek/deepseek-chat`. Both modes then opened correctly on the Space.
    - **For the new version's launch, use `OPENAI_MODEL=deepseek/deepseek-chat`** (via OpenRouter) unless Fan sorts out OpenAI access. Fan still needs to confirm the model choice. Before inviting people, check which provider OpenRouter routes DeepSeek to, and say where data is processed in `ERICKSON_DATA_LOCATIONS`.

## 4. What is built (module map)

| File | Role |
|---|---|
| `web_app.py` | Gradio UI and callbacks. `create_app()` mounts Gradio in FastAPI behind sign-in (`auth_dependency`), and `launch_demo()` runs uvicorn. Handlers take `request: gr.Request`, and `request.username` is the signed-in user id. Handles session open/restore/save, quotas, rate limits, the crisis check, feedback, and background profile learning. |
| `account_pages.py` | Server-rendered pages: `/login`, `/setup` (first admin, local only), `/invite/{code}`, `/reset/{token}`, `/forgot` (only with SMTP), `/account`, `/sessions/{id}`, `/mentor`, `/admin`, `/privacy`, `/help` (public), `/icons/*`, `/healthz`. All strings are in `T["en"]` / `T["zh"]`. |
| `db.py` | SQLAlchemy Core storage: users, invites, password_resets, coaching_sessions (state JSON), session_results (action card or practice score per finished session), session_ratings (the 1–5 "how useful" answer), profiles, usage_events, feedback, settings, audit_log. New tables are created at startup; existing ones are never altered (no migrations yet). SQLite by default; Postgres via `DATABASE_URL`. |
| `accounts.py` | scrypt passwords, signed cookies (invalid after a password change), CSRF, login throttle, `can_view_session`. |
| `quota.py` | Allowances, role defaults with admin overrides (settings key `role_limits`), per-minute message limiter. |
| `coaching_core.py` | Shared OpenAI-compatible client (45 s timeout, 1 retry), usage metering, streaming, the stage markers (`[[GOAL]]`/`[[REALITY]]`/`[[OPTIONS]]`/`[[COMMITMENT]]`/`[[END]]`, see Gotchas), batched translation, `OPENAI_EXTRA_BODY`, and DeepSeek thinking off. |
| `coach_agent.py` / `coachee_agent.py` | Agents with `stream_response()`, `to_dict()`/`from_dict()`. The reply itself decides the stage via markers, with no separate check call. Both send the model the first 6 and last 16 messages (`_conversation_window` in `coaching_core.py`), so the goal agreed at the start stays in view. `EricksonCoachingAgent.action_card()` writes the end-of-session card; `last_card` makes the opening follow up on the previous plan. |
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
   - `OPENAI_MODEL=deepseek/deepseek-chat` (gpt-4o-mini is refused for this account; see section 3)
   - `DATABASE_URL`
   - `ERICKSON_SECRET_KEY` (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
   - `ERICKSON_ADMIN_EMAIL`
   - `ERICKSON_ADMIN_PASSWORD` (at least 10 characters)
   - `ERICKSON_DATA_LOCATIONS` (e.g. "Server: Hugging Face (USA) · AI: OpenAI via OpenRouter (USA)")
4. ✅ GitHub repo renamed to `coaching-practice-studio` and made private (2026-10-15).

**Next steps for Claude, once Fan says "secrets are set, deploy":**

1. Update `DEFAULT_SPACE_ID` in `scripts/deploy_hf_space.py` and the Space address in `README.md`.
2. Run `python3 scripts/deploy_hf_space.py`. Ask before uploading, because it is outward-facing.
3. Watch the Space logs until it's running. This is the first time FastAPI + uvicorn + mounted Gradio runs on HF; HF sets `GRADIO_SERVER_NAME=0.0.0.0` and `GRADIO_SERVER_PORT=7860`.
4. Have Fan test using the direct `https://<space>.hf.space` address. Sign-in cookies don't work inside the huggingface.co page frame.
5. Run one real session per module to confirm the stage markers work with a paid model.

**Product improvements (Fan's review, 2026-10-14).** Items 1–3 are done (commit "Clearer first visit, …"):
1. ✅ Plain mode names ("Be coached" / "Practise coaching", 被教练 / 练习做教练), a one-time welcome card on the first visit (shown while the person has no sessions yet), and a Help link in the app header. The daily allowance pill moved from the header into the mode card, so the app name fits on phones.
2. ✅ The AI Coach (and the AI client in Coachee Lab) keeps the start of the conversation plus recent messages; the practice review reads (nearly) the whole session.
3. ✅ Takeaways: the AI Coach ends with an action card (goal, next step, by when, support) in the chat and on the Account page. A new AI Coach session asks how the last plan went, using cards that are 8 hours to 60 days old. Coachee Lab scores are saved and shown with a "Latest · Average" line. Mentors see their members' scores; the admin sees neither cards nor scores. Skipping to the end now gets a real AI closing summary. Each AI message is its own chat bubble.

Still open, in Fan's order:
4. ✅ (2026-10-15) The AI/Template switch is hidden (it stays in the page because every handler reads it, and it always holds the default). A session keeps the mode it opened with. Read-aloud is off by default. The insights heading in Settings now follows the language (it used to be fixed Chinese).
5. ✅ Compact phone layout (2026-10-15). The chat's share of the screen went from 31% to 56% on a 390x844 iPhone, and from 13% to 44% on a 375x667 iPhone SE; the laptop is unchanged. The styles are in the "Compact phone layout" block at the end of the CSS in `web_assets.py`. **Still open: a real test inside WeChat's built-in browser** (voice input especially). It needs the deployed app and Fan's phone.
6. ✅ (2026-10-15) A one-tap "How useful was this session?" (1–5) when a session ends, in both modes. Tapping again changes it. Stored in `session_ratings`; the Admin page's Recent sessions card shows the 30-day average per module and each session's rating (the privacy page says so).
7. Real sessions on DeepSeek: **partly done 2026-10-15.** I ran 20 full sessions on `deepseek/deepseek-chat` with a second model call playing the person (the script lives only in that session's scratchpad). Each session cost under one cent (5k–14k tokens), so the $4.84 balance covers roughly a thousand sessions. Found and fixed:
   - **Chinese Coachee Lab failed to start 4 times in 5:** the case JSON came back with mismatched brackets.
     - Every JSON request now goes through `_json_completion` (`coaching_core.py`): provider JSON mode, `_repair_json_brackets`, and one cooler retry.
     - A practice case that still can't be read falls back to a built-in case, so a session always opens.
     - Wrongly nested case sections are lifted back to the top level.
   - The case prompt now says each list holds the coachee's own first-person lines, never questions.
   - **Coach style:** no more praise words; never repeat a question; replies in plain sentences, no bullets; every reply ends with a question; openings ask what they want from the session, not for actions yet.
   - **Stray goodbyes:** a goodbye between stage checkpoints didn't end the session. Both agents now always offer an end marker (`_end_only_rules`). A thank-you alone is not a request to finish.
   - Quote marks wrapped around a whole reply are stripped (`_strip_wrapping_quotes`).
   - The follow-up opening asks exactly one question.
   - Insight profiles are now written in the session's language.
   - Translation returns `{"translations": [...]}`.
   - **Practice scoring:** a rubric of 20 per stage and a "Stage scores" line, plus a hard ceiling of 8 points per coach turn (`_score_ceiling`), so a 5-question session can't score 70. When capped, the stage scores are scaled to add up.
   - **Still to judge with real people:** sessions with an eager client end early (5–6 turns) once they have a concrete plan. The stage tracker often stays on Contract while the talk has moved on, because models rarely emit `[[NEXT]]`. Fan and a few friends should try both modes before the wider invite.
   - ✅ (2026-10-15) **Stage tracker fixed** (see Gotchas, "Stage markers"). In simulated sessions the tracker now follows the talk: AI Coach sessions mostly reach stage 3–4 before closing (before: stage 1–2), practice sessions follow the coach (e.g. 1 2 2 3 4 5), and the practice goodbye loop is gone. The AI coach may close before the commitment stage only if the person asks to finish.
8. Coachee Lab: choose the client type, a Hint button, and a one-line purpose for each stage.
9. A progress page with score history over time (the Account page shows the last six).
10. Mentor comments on sessions.

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
- **HF refuses to create Gradio Spaces on free hardware without PRO (402):** `hf upload` tries to create the repo first and fails, even though the Space exists. `scripts/deploy_hf_space.py` uses `HfApi().upload_folder` instead. Don't delete the Space: a new free Gradio Space can't be made.
- **Gradio SSR on Hugging Face:** HF enables Gradio's server-side rendering, so `mount_gradio_app` starts a Node server on the public port, moves the Python app to 7861, and forwards only Gradio's own routes. `/privacy`, `/help`, `/account`, `/admin` and `/healthz` then showed the Gradio shell. `create_app` passes `ssr_mode=False`, and a test guards it.
- **Mainland China "stuck at loading" (found 2026-10-15):** without SSR, Gradio's browser code asks `huggingface.co/api/spaces/by-subdomain/…` whether the Space is running before it shows the app (only on `*.hf.space` addresses). huggingface.co is blocked in mainland China, so the app page hung for 30 s or more while `/account`, `/login` and other plain pages opened fine. (The old version ran with SSR, where HF's server made that check.) `space_status_js` (`web_assets.py`) answers it in the browser, and the sign-in middleware in `create_app` puts it first in Gradio's `<head>`. A test checks the page and that the installed Gradio still asks that address; re-check after a Gradio upgrade.
- **Gradio's Space badge:** on Hugging Face, Gradio pins `#huggingface-space-header` (Space name and likes) at the top. It hides itself on phones only on a resize, so it covered the header, Help and Account on every phone visit. It's hidden by a rule in `head` (`web_assets.py`).
- **Language switch:** `switch_lang` must translate before setting the new language, otherwise `translate_history` sees nothing to do. `_ensure_session(..., set_language=False)` exists for this; a test drives the real switch.
- **Busy AI service (429):** OpenRouter sometimes answers "Too Many Requests", often on the first call after a restart. Every request goes through `_MeteredCompletions.create`, which now tries twice more (1.5 s, then 3 s) on 429, 5xx or connection errors, but never after a timeout. On 2026-10-15 a 429 made the reopen-in-English translation fail silently: the page showed English while the conversation stayed Chinese. `translate_history` now returns False and changes nothing when it fails, and `initial_load` / `switch_lang` keep the page in the conversation's language with a notice.
- **Stage markers (2026-10-15):** every AI reply starts with a marker naming the stage the talk is in (`STAGE_MARKER_GUIDE` in `coaching_core.py`); in practice mode it is the stage of the human coach's latest question. The tracker never moves back, and only `[[END]]` closes. Two lessons: (1) asked to *decide* when to move on (`[[NEXT]]`), models nearly always stayed; *naming* the stage works. Words beat numbers, which models copied from turn to turn. (2) Models copy their own earlier replies: replies are saved without markers, so after 2–3 turns the model stopped writing markers at all, and a coach's goodbye in practice mode looped forever. Each reply now keeps its `stage` in the saved context, and `_as_written` puts the marker back when the history is sent to the model. A trailing system reminder did not help (OpenRouter seems to move system messages to the front).
- **Gradio hidden components:** Gradio 6 hides a component with a `hide` class, so a custom `display` rule with `!important` makes it show all the time (the rating card did). Don't set `display` on things Gradio shows and hides.
- **Gradio CSS prefix:** Gradio 6 prefixes every custom CSS selector with `.gradio-container… .contain`, so selectors starting at `body` silently never match. Start at `#app-shell`. Check in the browser with `document.styleSheets` when a rule seems to do nothing.
- **Gradio fonts:** Gradio wraps theme font names in quotes, so generic names like `system-ui` stop working. Use concrete font names, ending with `sans-serif`.
- **`api_visibility="private"` is not security:** it only hides endpoints from the API page. Sign-in (`auth_dependency`) is the real gate.
- **Session state:** `gr.State` is copied only when a browser session starts, so the per-agent locks in a `WeakKeyDictionary` are valid.
- **Reopening sessions:** a stored session that can't be read back is marked abandoned and a fresh one opens. Don't let restore errors crash `initial_load`.
- **Hosted login loop:** cookies are `Secure` when the app is public, so plain `http` on a public server breaks sign-in. Any non-HF host needs HTTPS.
- **DNS hang:** Python's `http.server` `server_bind` does a reverse-DNS lookup that hung on this Mac. `scripts/load_test.py` overrides it (`LocalHTTPServer`).
- **Free models:** `openrouter/free` returns empty replies, a safety classifier's output, or leaked reasoning, and hits 429 rate limits often.
