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

## Server Configuration

Set these environment variables before launching the hosted app:

```zsh
export OPENAI_API_KEY="your-server-side-key"
export OPENAI_MODEL="gpt-4o-mini"
# Optional for OpenRouter or another OpenAI-compatible gateway:
export OPENAI_BASE_URL="https://your-compatible-base-url"
```

If `OPENAI_API_KEY` is missing, AI mode stays selected and the chat shows a server-configuration message.

## Launch Commands

Run the web app locally with either entrypoint:

```zsh
python3 app.py
# or
python3 web_app.py
```

The app does not auto-open the system browser by default, which avoids Chrome crash-reopen prompts from the normal user profile in Codex/sandbox runs. Set `ERICKSON_INBROWSER=1` explicitly if you want Gradio to open the browser anyway. For screenshot checks, keep using `ERICKSON_INBROWSER=0` with `manual_ui_probe.py`.

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
It runs `mac_launcher.py`, starts Gradio with `ERICKSON_INBROWSER=0`, and opens the UI in an isolated Chrome profile at `/private/tmp/erickson-coach-chrome-profile` so the normal Chrome profile cannot show crash-reopen prompts. It reads server-side settings from this workspace `.env` file when present. If you have moved the project folder or added new dependencies, ensure that `Erickson Coach Launcher.applescript` has the correct `workspace_path_value` and re-compile the app if necessary using:

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
4. **Compile Check**: Run `python3 -m py_compile app.py cli_app.py mac_launcher.py coach_agent.py coach_data.py coachee_agent.py coachee_data.py coaching_core.py memory.py web_assets.py web_app.py tests.py manual_ui_probe.py scripts/deploy_hf_space.py scripts/check_project.py`.

`python3 scripts/check_project.py --browser --launcher` runs these checks through the project helper.

Before uploading to Hugging Face, exclude `.env`, `user_profile.json`, caches, and the local macOS app bundle. The project `.hfignore` and `.gitignore` list these local-only artifacts. Also remember that the Space entrypoint is remote `app.py` built from local `web_app.py`, not the local wrapper `app.py`.
