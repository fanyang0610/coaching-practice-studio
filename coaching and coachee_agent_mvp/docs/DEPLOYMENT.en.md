# Configuration and deployment

English · [简体中文](DEPLOYMENT.md)

## Runtime configuration

Locally, use `.env` in the application directory. Hosted environments use platform variables and secrets. See [.env.example](../.env.example); the example model does not identify the hosted configuration. Do not commit keys, databases or real conversations.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Server-side model key. |
| `OPENAI_MODEL`, `OPENAI_BASE_URL` | Model ID and OpenAI-compatible endpoint. Omit the endpoint for direct OpenAI access; otherwise use your provider's endpoint and model ID. |
| `OPENAI_EXTRA_BODY` | Optional provider-specific JSON parameters. |
| `DATABASE_URL` | Persistent PostgreSQL for hosting; defaults locally to SQLite in the application directory. |
| `STUDIO_SECRET_KEY` | Required for hosted login signing. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`; retain the existing value when upgrading. |
| `STUDIO_ADMIN_EMAIL`, `STUDIO_ADMIN_PASSWORD` | Create the first hosted administrator; password minimum is 10 characters. Local setup can use the initial setup page. |
| `STUDIO_PUBLIC_URL` | Optional external base URL for invitation and reset links. |
| `STUDIO_DATA_LOCATIONS`, `STUDIO_CONTACT` | Privacy-page processing locations and help contact; match actual hosting and model configuration. |
| `STUDIO_INBROWSER` | Set to 1 to open the browser locally; off by default. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Optional self-service password-reset email. Administrators can also generate single-use reset links. |
| `GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT` / `PORT` | Bind address and port. Use HTTPS for public access. |
| `SENTRY_DSN` | Optional error reporting, configured without request bodies or local-variable collection. |

Existing installations retain compatibility with legacy environment variables; new `STUDIO_*` values take precedence. Existing local databases, signing files, login and language settings remain readable. Fresh installations use `studio.db` and `.studio_secret`. When renaming configuration, copy existing values, especially the signing key.

## GitHub releases and documentation

GitHub Releases identify source versions and do not automatically update the Space. Before every release, follow the [bilingual release rules](../../docs/RELEASES.en.md): review the README, feature status, architecture, configuration and maintenance handoff; update affected documents in both languages and record the documentation decision in release notes.

Capacity rules are in [coaching_core.py](../coaching_core.py). Some limits are recognized from the configured model ID; provider errors remain authoritative. Model changes call for checking full-history behavior, structured output, language and capacity. Support for an ID in code does not establish real validation of that direct provider. This update does not change models or configuration.

## Hugging Face Spaces

1. Configure model, persistent PostgreSQL and signing secrets in the existing Space. Retain the database URL when upgrading. First deployment also needs administrator configuration.
2. From the application directory, run `python scripts/deploy_hf_space.py --dry-run`. The script's `SPACE_FILES` defines the upload list; `scripts/needs_hf_upload.py` uses the same mapping. To check committed changes, pass paths relative to the application directory.
3. Once deployment is authorized, run `python scripts/deploy_hf_space.py --commit-message "Deploy <GitHub commit>"`. Local `web_app.py` becomes remote `app.py`. Application [README.md](../README.md) retains the Space configuration header; its `sdk_version` must match Gradio in [requirements.txt](../requirements.txt).
4. After the build starts running, use the direct URL to check sign-in, both conversation modes and the account page. `/ping` checks the process; `/healthz` checks the database. Inspect the remote file list before separately removing development tools or local files left by older deployments.

Only application README.md is uploaded, so it retains an English entry point; the complete English README stays on GitHub. Also verify the running SHA matches the deployment commit. Health responses do not establish model or business-flow correctness.

As of 13 November 2026, the deployed application is GitHub v2.8.1 / `731a880`, Space [f8aa9f7](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/f8aa9f73ecdc1156ae796b44c68606acc8c1c187), confirmed RUNNING with a matching runtime SHA, the latest bilingual mobile Help entry and successful health checks. v2.8.2 changes documentation and project instructions only; the deployed application remains v2.8.1. See the [Space commit history](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commits/main) for subsequent deployments and source references.

## Docker and databases

The application [Dockerfile](../Dockerfile) uses the application directory as build context. Use PostgreSQL, HTTPS and one process for public hosting; current rate limits are in-process.

Startup creates missing tables. Changes to existing schemas need separately designed migrations and rollback. Database-platform or local operations own backup and restore; retain the existing database and signing key during upgrades.

Current insights and practice goals use the existing profile JSON and need no new tables. Reverting code must not overwrite real data or user corrections. Application v2.8.1 involves no data migration; the previous hosted version is GitHub v2.8.0 / `ff01d17`, Space `3cc22cca953c5457823b48aa0e01f852ba4a22cf`. Reassess data compatibility before rollback.
