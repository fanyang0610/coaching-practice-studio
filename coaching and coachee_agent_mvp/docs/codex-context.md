# Codex Project Context

This file captures durable context from recent Codex work on the Erickson Coach MVP. Use it as a handoff note before making future changes.

## 1. Project Goal

Erickson Coach is a bilingual Gradio web app for practicing Erickson-style coaching conversations.

The app has two main modules:

- Coach Assistant: the AI acts as coach, and the user enters as the coachee/client.
- Coach Training / AI Coachee Lab: the AI acts as coachee, the user practices as coach, and the app can score or review the coaching close.

The intended product feel is a calm, credible coaching practice environment, not a dashboard or playful chat app. It should stay usable in one viewport on laptop and phone, with only the chat transcript scrolling internally.

## 2. Completed Design Decisions

- The canonical visual direction is defined in `DESIGN.md`, supplemented by `DESIGN.erickson-edu.md`.
- The interface uses a bright white and soft-blue institutional coaching style, with restrained gold accent.
- Module switching is treated as compact tabs/segmented controls, especially on mobile, rather than oversized cards.
- The stage tracker remains visible and compact; all five coaching stages should fit on phone widths.
- The composer, chat, tracker, module switcher, and key actions should remain visible around `390x844`.
- The app is intentionally mobile-safe:
  - `head` injects a mobile viewport meta tag through `demo.launch(...)`.
  - CSS uses `100dvh` to handle mobile browser chrome better than plain `100vh`.
  - iOS speech and microphone behavior is handled in JavaScript with user-gesture priming.
- Client users should not enter or see API keys in the UI. AI mode uses server-side `OPENAI_API_KEY` from environment or `.env`.

## 3. Current Code Structure

- `web_app.py`: Gradio UI, theme/CSS, event wiring, launch configuration, server-side environment config, TTS/mic JavaScript, and UI callback glue.
- `web_assets.py`: Static UI copy, CSS, viewport style, and browser JavaScript used by `web_app.py`.
- `coach_agent.py` and `coach_data.py`: Coach Assistant behavior plus static template prompts.
- `coachee_agent.py` and `coachee_data.py`: AI Coachee Lab behavior plus static scenario data, manual advance guard, scoring/review flow.
- `coaching_core.py`: Shared enums, OpenAI-compatible client construction, model selection, response parsing, language cleanup.
- `memory.py`: Local `user_profile.json` persistence and optional encrypted remote-sync scaffolding.
- `tests.py`: Regression and behavior tests for agent progression, module boundaries, response parsing, server config, mobile layout contracts, and callback output counts.
- `manual_ui_probe.py`: Chrome screenshot utility for desktop and iPhone-sized visual verification with an isolated browser profile.
- `scripts/check_project.py`: Repeatable local verification runner for tests, compile checks, HF dry-run, optional screenshots, and optional launcher compilation.
- `README.md`: Maintenance and launch instructions.
- `AGENTS.md`: Project-specific operating rules for Codex.
- `Erickson Coach Launcher.applescript` and `Erickson Coach.app`: local macOS launcher.

Older generic files such as `agent.py` should not be reintroduced. Tests assert that explicit agent modules replace the generic agent file.

## 4. Key Technical Choices

- Frontend/runtime: Gradio.
- LLM client: `openai` Python package, with OpenAI-compatible gateway support through `OPENAI_BASE_URL`.
- Default model: `gpt-4o-mini`, configurable with `OPENAI_MODEL`.
- Default app mode: AI (`llm`), with template mode available as backup.
- API key handling: server-side only through `OPENAI_API_KEY`; do not add client-side API key fields back.
- State model: five Erickson stages in `CoachingState`: Contract, Experience/Reality, Action/Possibilities, Value/Commitment, Closing.
- Conversation modes:
  - Template mode provides deterministic fallback and testable behavior.
  - LLM mode uses server key when configured, but initial openings should not block on an LLM call.
- Verification approach:
  - Run `python3 tests.py`.
  - Run compile checks for core Python files when changing runtime code.
  - Use `ERICKSON_INBROWSER=0` and `manual_ui_probe.py` for screenshots.
  - Recompile `Erickson Coach.app` after code changes.

## 5. Known Pitfalls

- Gradio callback output counts must match exactly. Intermittent red `Error` UI appeared when guard/error branches returned fewer values than their wired outputs. Keep `RESPOND_OUTPUT_COUNT` and `NEXT_STAGE_OUTPUT_COUNT` tests in sync with callback wiring.
- Do not pass `head` only to `gr.Blocks(...)` for this Gradio version. The viewport meta must be passed through `demo.launch(..., head=head)`.
- Missing mobile viewport meta caused the phone browser to lay out wider than the visible device surface, creating clipping. Keep `width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content`.
- Avoid fixed widths and viewport clamps like `calc(100vw - 72px)` or narrow `max-width: 300px` hacks. Prefer `minmax(0, 1fr)`, `min-width: 0`, `box-sizing: border-box`, and internal scrolling.
- The app can show different behavior depending on whether the page is a true mobile viewport, a desktop window with an iPhone user agent, or a parent iframe. Use real mobile emulation when diagnosing layout width.
- Gradio launch can fail if the default port range is occupied. For verification, use a known port such as `GRADIO_SERVER_PORT=8787`.
- Headless Chrome may need sandbox escalation on this macOS/Codex environment. The documented `manual_ui_probe.py` path avoids normal browser profile prompts.
- `osacompile` may print macOS `hiservices` connection warnings while still exiting 0. Treat exit code as the important signal unless the app bundle is actually not updated.
- iOS audio and microphone APIs are gesture-gated. Keep the TTS unlock and mic binding logic tied to user interactions.
- `MemoryManager` local persistence writes `user_profile.json`. Remote sync is disabled by default and should remain optional unless explicitly productized.

## 6. Suggested Next Development Steps

- Add a small browser-level regression script for the two previously intermittent UI paths: empty send and blocked next-stage. Current unit tests cover callback arity; a browser test would catch Gradio frontend regressions.
- Keep consolidating layout rules around the one-page contract: no outer document scroll, no horizontal scroll, chat transcript scrolls internally.
- Add tests around server-side key behavior for hosted deployment, especially missing `OPENAI_API_KEY`, custom `OPENAI_BASE_URL`, and `OPENAI_MODEL`.
- Consider extracting long CSS and JavaScript strings from `web_app.py` only if edits become risky. Do not refactor just for cleanliness.
- Decide whether `MemoryManager` remote sync should be removed, documented as experimental, or made production-ready with a real backend.
- Before any UI change, reread `DESIGN.md` and `DESIGN.erickson-edu.md`, then verify desktop and `390x844` screenshots.
- Before reporting any fix complete, run:
  - `python3 scripts/check_project.py --browser --launcher`
