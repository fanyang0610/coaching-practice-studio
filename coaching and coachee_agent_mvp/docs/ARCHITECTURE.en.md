# Architecture and development checks

English · [简体中文](ARCHITECTURE.md)

## Requests and persistence

FastAPI verifies sign-in and passes the user to Gradio. Both AI roles share an OpenAI-compatible client but save their own conversation, stage and outcome. A new session generates and saves its opening before replacing the current one; switching modes resumes each independently. Continuations, reviews and insight analysis use the complete conversation rather than a trailing slice.

| Module | Responsibility |
| --- | --- |
| [app.py](../app.py) / [web_app.py](../web_app.py) | Local entry point, FastAPI assembly, Gradio events, restoration, drafts, saves, endings and capacity notices. |
| [coach_agent.py](../coach_agent.py) / [coachee_agent.py](../coachee_agent.py) | AI coach, AI coachee, five-stage progression, action cards and reviews; companion *_data.py files contain questions and cases. |
| [coaching_core.py](../coaching_core.py) | Model connection, streaming, capacity estimates, stage markers, usage, structured output and translation. |
| [accounts.py](../accounts.py) / [account_pages.py](../account_pages.py) | Signed login, passwords, form validation, permissions, and sign-in, invitation, account, mentor, admin and help pages. |
| [db.py](../db.py) / [memory.py](../memory.py) | SQLite/PostgreSQL, sessions separated by user and mode, profiles, owner insight corrections and the next practice goal. |
| [web_assets.py](../web_assets.py) / [DESIGN.md](../DESIGN.md) | Copy, styles, browser speech and design rules. |
| [quota.py](../quota.py) / [safety.py](../safety.py) / [mailer.py](../mailer.py) | Allowances, rate limits, fixed crisis responses and optional password-reset email. |

Sessions and profiles use JSON. Conditional version updates prevent stale tabs and late analysis from overwriting newer content. Profiles are separate by mode; subsequent reads use current corrected values. An explicitly fresh Be coached conversation starts from the current topic. Historical incorrect insights are not rewritten in bulk.

New action cards require a non-empty next step. Failure status is stored with the session; history recovery is owner-only and cannot replace an existing card. New AI reviews have five stages worth 20 points each, added by the program. Model judgments can still be wrong; old reviews are not recalculated. Template demos use separate rules and do not establish real AI quality.

Permissions are enforced at account and storage entry points. Mentors see assigned learners' practice and explicitly shared Be coached records; administrator pages do not provide transcript viewing. Account and mentor histories and administrator invitations have pagination. Changes affecting the last active administrator are serialized inside storage transactions.

## Limits and failures

A session allows 100 user messages, each up to 2,000 characters. Case topics and the next practice goal each allow 300 characters. Capacity estimates cover recognized model configurations; provider capacity errors remain authoritative. Requests retain the original text and allow wrapping up near capacity instead of dropping the middle of a conversation.

Allowances use a rolling 24-hour window. Completed/started sessions are counted separately by mode; tokens are shared. If several limits apply, the latest recovery time determines the notice; zero allowances require contacting an administrator. Rate limits are in-process, so deployment uses one process. Generation, translation and save failures should preserve existing records. Replies and manual stage progression preserve new composer drafts; unsent drafts are not promised to survive refresh.

## Development commands

Run from the application directory; see the [project README](../../README.en.md) for installation.

```sh
python scripts/dev_server.py
python tests.py
python scripts/check_project.py
```

- The demo uses temporary accounts, a temporary database and fake AI; `--ai-down` simulates an unavailable model.
- `tests.py` checks sessions, permissions, storage, model failures and web behavior. With Node.js installed it also checks browser scripts.
- `check_project.py` runs project tests, Python compilation checks and the Space file preview. `--browser` adds isolated Chrome screenshots with temporary login at desktop/iPhone dimensions. `--launcher` rebuilds the macOS launcher. These options do not run only the named extra operation.
- For storage or concurrency changes, use [pg_test.py](../scripts/pg_test.py) and [load_test.py](../scripts/load_test.py) as needed with isolated databases and fictional accounts.
- Choose checks for the actual impact and reuse valid results. Application code changes follow [AGENTS.md](../AGENTS.md) for browser checks and launcher rebuilding. Documentation and repository release-process changes alone do not require repeating application acceptance.

See [Handoff](HANDOFF.en.md) for limitations and [Releases](../../docs/RELEASES.en.md) for bilingual notes and the pre-release documentation review.
