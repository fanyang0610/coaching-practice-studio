# Project Instructions

- For any UI, UX, visual styling, or layout work, consult `DESIGN.md` first and keep new screens aligned with that design system unless the user explicitly asks for a different direction.
- After every fix or code change, validate both desktop web browser and iPhone-sized mobile browser compatibility before reporting completion.
- After every fix or code change, recompile the local `Erickson Coach.app` launcher in this folder so clicking the app opens the latest version in this workspace.
- Keep the launcher behavior aligned with the current workspace layout instead of hardcoding obsolete paths.
- For screenshot verification, start the app with `ERICKSON_INBROWSER=0` and use `python3 manual_ui_probe.py --url http://127.0.0.1:<port>` so Chrome runs with an isolated temporary profile and cannot trigger the normal browser reopen/crash prompt.
- The app requires sign-in. `scripts/check_project.py --browser` creates a throwaway probe account and passes its cookie to `manual_ui_probe.py --cookie`; do the same when probing by hand. The account, trainer and admin pages (`account_pages.py`) are UI too: check them at desktop and iPhone widths.
- Hugging Face deployment rule: do not upload the local `app.py` wrapper as the Space entrypoint, and do not upload `web_app.py` under its own name as the runnable Space file. For Hugging Face, upload local `web_app.py` to the remote path `app.py` so the Space's `app_file: app.py` contains the full Gradio app implementation.


<claude-mem-context>
# Memory Context

# [coaching and coachee_agent_mvp] recent context, 2026-05-02 1:23pm GMT+8

No previous sessions found.
</claude-mem-context>
