import contextlib
import datetime as dt
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import threading
import time
import uuid
import webbrowser
import weakref

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response

# Coaching conversations are private; don't send Gradio usage analytics to third parties.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr  # noqa: E402
from starlette.concurrency import run_in_threadpool

import accounts
import account_pages
from coach_agent import ACTION_CARD_FIELDS, CoachAgent, can_recover_action_card
import coaching_core
from coaching_core import CoachingState
from coachee_agent import CoacheeAgent, review_score
import db
import mailer
from memory import UserProfile, merge_analysis, profile_version
import quota
import safety
from studio_config import LEGACY_NAME, local_path, studio_env
from web_assets import (
    MODE_OPTIONS,
    STAGE_NAMES,
    UI,
    css,
    force_light_js,
    global_viewport_style,
    head,
    remember_lang_js,
    scroll_js,
    space_status_js,
    tts_js,
    voice_note_js,
    welcome_js,
)


ROOT = Path(__file__).resolve().parent
# Served publicly by account_pages so the header doesn't carry a 50 KB base64 image on every reply.
HEADER_ICON_SRC = "/icons/studio-icon-192.png"

logger = logging.getLogger("coaching_studio")


def _load_dotenv():
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


_load_dotenv()


def get_server_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def get_server_base_url() -> str | None:
    return os.environ.get("OPENAI_BASE_URL", "").strip() or None


def get_server_model() -> str:
    return os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"


def _is_public(env: dict[str, str] | None = None) -> bool:
    """True on a Space or any non-loopback bind: then secrets must come from the environment."""
    env = os.environ if env is None else env
    if env.get("SPACE_ID"):
        return True
    return env.get("GRADIO_SERVER_NAME", "127.0.0.1").strip() not in ("127.0.0.1", "localhost", "::1")


def _launch_inbrowser(env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return studio_env(env, "INBROWSER").strip().lower() in ("1", "true", "yes", "on")


default_mode = "llm"
default_lang = "zh"
default_module = "coach"
RESPOND_OUTPUT_COUNT = 17
NEXT_STAGE_OUTPUT_COUNT = 17
# New Session, switching mode, and starting a practice on one's own topic all fill the same outputs.
NEW_SESSION_OUTPUT_COUNT = 30
# The practice topic band: card, prompt, topic box, button (see _topic_updates).
TOPIC_OUTPUT_COUNT = 4

# Every event that can call the model shares one pool of worker slots. Calls mostly wait on
# the network, so 24 at once is comfortable for a 2-vCPU host and stays under Gradio's 40 threads.
LLM_CONCURRENCY = 24
MAX_MESSAGE_CHARS = 2000
# A practice client's topic, in the coach's words: a sentence or two is plenty.
MAX_TOPIC_CHARS = 300
MAX_USER_TURNS_PER_SESSION = quota.MESSAGES_PER_CONVERSATION
# A new AI Coach session asks about the last action card made in this window (not one from minutes ago).
FOLLOW_UP_WITHIN = dt.timedelta(days=60)
FOLLOW_UP_AFTER = dt.timedelta(hours=8)
# Sign-in is the real gate; hiding the endpoints just keeps them off the public API page.
LLM_EVENT = {"concurrency_id": "llm", "concurrency_limit": LLM_CONCURRENCY, "api_visibility": "private"}

_agent_locks: "weakref.WeakKeyDictionary[object, threading.Lock]" = weakref.WeakKeyDictionary()
_agent_locks_guard = threading.Lock()
_message_limiter = quota.MessageRateLimiter()

_store: db.Store | None = None
_store_guard = threading.Lock()


def get_store() -> db.Store:
    global _store
    with _store_guard:
        if _store is None:
            _store = db.Store(db.database_url())
        return _store


def set_store(store: db.Store) -> None:
    global _store
    with _store_guard:
        _store = store


def _agent_lock(agent) -> threading.Lock:
    """One lock per conversation, so a double send can't interleave two replies on the same agent."""
    with _agent_locks_guard:
        lock = _agent_locks.get(agent)
        if lock is None:
            lock = _agent_locks[agent] = threading.Lock()
        return lock


def _module_choices(lang_code: str) -> list[str]:
    return [UI[lang_code]["coach_module"], UI[lang_code]["coachee_module"]]


def _module_label(module_code: str, lang_code: str) -> str:
    return UI[lang_code]["coachee_module"] if module_code == "coachee" else UI[lang_code]["coach_module"]


def _safe_module(module_sel: str | None) -> str:
    if not module_sel:
        return default_module
    lowered = module_sel.lower()
    module_map = {
        "coach": "coach",
        "coachee": "coachee",
        "coach assistant": "coach",
        "ai coach": "coach",
        "教练助手": "coach",
        "ai教练": "coach",
        "coach training": "coachee",
        "ai coachee lab": "coachee",
        "教练陪练": "coachee",
        "ai学员陪练": "coachee",
    }
    return module_map.get(lowered, default_module)


def _module_button_text(module_code: str, lang_code: str, active_module: str) -> str:
    s = UI[lang_code]
    return s["coach_module_card"] if module_code == "coach" else s["coachee_module_card"]


def _module_button_updates(active_module: str, lang_code: str):
    coach_classes = ["module-card-btn", "selected"] if active_module == "coach" else ["module-card-btn"]
    coachee_classes = ["module-card-btn", "selected"] if active_module == "coachee" else ["module-card-btn"]
    return (
        gr.update(value=_module_button_text("coach", lang_code, active_module), elem_classes=coach_classes),
        gr.update(value=_module_button_text("coachee", lang_code, active_module), elem_classes=coachee_classes),
    )


def _mode_context_html(session: dict) -> str:
    agent = session["agent"]
    module_code = session["module"]
    s = UI[agent.language]
    mode_title = s["coach_module"] if module_code == "coach" else s["coachee_module"]
    mode_note = s["coach_module_note"] if module_code == "coach" else s["coachee_module_note"]
    # Today's allowance for this mode, next to its name.
    allowance = session.get("allowance")
    quota_pill = ""
    if allowance and allowance.session_limit is not None:
        quota_pill = f' <span class="studio-quota">{s["quota_pill"].format(left=allowance.sessions_left, limit=allowance.session_limit)}</span>'
    elif allowance:
        quota_pill = f' <span class="studio-quota">{s["quota_pill_unlimited"].format(used=allowance.sessions_used)}</span>'
    capacity_note = ""
    if agent.mode == "llm" and not agent.is_session_ended() and coaching_core.conversation_capacity(agent.context):
        capacity_note = f'<div class="context-capacity-note" role="status">{s["context_near"]}</div>'
    return f"""
    <section class="mode-context-card">
        <div class="mode-context-label">{s["mode_context"]}</div>
        <div class="mode-context-title">{mode_title}{quota_pill}</div>
        <p>{mode_note}</p>
        {capacity_note}
    </section>
    """


def _build_agent(module: str, mode: str, language: str, user_profile=None):
    if module == "coachee":
        return CoacheeAgent(mode=mode, language=language, user_profile=user_profile)
    return CoachAgent(mode=mode, language=language, user_profile=user_profile)


def _new_session(module: str = default_module, mode: str = default_mode, language: str = default_lang, user_profile=None) -> dict:
    """An unsaved conversation; the app replaces it with a stored one once it knows who is signed in."""
    return {
        "module": module,
        "agent": _build_agent(module=module, mode=mode, language=language, user_profile=user_profile),
    }


def _lang_code(lang_sel: str) -> str:
    return "zh" if lang_sel == "中文" else "en"


def _safe_mode(mode_sel: str | None) -> str:
    if not mode_sel:
        return default_mode
    lowered = mode_sel.lower()
    mode_map = {
        "template": "template",
        "模板": "template",
        "llm": "llm",
        "ai": "llm",
    }
    return mode_map.get(lowered, default_mode)


def _safe_lang(lang_sel: str | None) -> str:
    if not lang_sel:
        return default_lang
    return _lang_code(lang_sel)


def _safe_key() -> str:
    return get_server_api_key()


def _llm_config_message(lang_code: str) -> str:
    return UI[lang_code]["server_config_error"]


def _lang_selector(lang_code: str) -> str:
    return "中文" if lang_code == "zh" else "English"


def _mode_choices(lang_code: str) -> list[str]:
    return [MODE_OPTIONS[lang_code]["template"], MODE_OPTIONS[lang_code]["llm"]]


def _mode_label(mode_code: str, lang_code: str) -> str:
    return MODE_OPTIONS[lang_code][_safe_mode(mode_code)]


def _session_ui(agent, module_code: str) -> dict[str, str]:
    lc = agent.language
    s = UI[lc]
    if module_code == "coachee":
        return {
            "title": s["coachee_title"],
            "subtitle": s["coachee_sub"],
            "placeholder": s["coachee_placeholder"],
        }
    return {
        "title": s["coach_title"],
        "subtitle": s["coach_sub"],
        "placeholder": s["coach_placeholder"],
    }


def _chat_history_from_context(agent, session_id: str | None = None) -> list[dict[str, str]]:
    chat_history = []
    for msg in agent.context:
        role = "assistant" if msg["role"] == agent.assistant_role else "user"
        chat_history.append({"role": role, "content": msg["content"]})
    if isinstance(agent, CoachAgent) and agent.action_card_result:
        chat_history.append({"role": "assistant", "content": _action_card_outcome_text(agent, session_id)})
    return chat_history

def _memory_ui_updates(agent, lang_code: str):
    s = UI[lang_code]
    p = agent.user_profile
    if not p or not (p.last_updated or p.strengths or p.growth_areas or p.coaching_style_insights or p.learning_patterns):
        return (
            f"**{s['memory_strengths']}**\n\n{s['memory_no_data']}",
            f"**{s['memory_growth']}**\n\n- ",
            f"*{s['memory_last_sync']}: {s['memory_never']}*"
        )
    
    strengths = "\n".join([f"- {i}" for i in p.strengths]) if p.strengths else "- "
    growth = "\n".join([f"- {i}" for i in p.growth_areas]) if p.growth_areas else "- "
    
    summary = p.coaching_style_insights if isinstance(agent, CoachAgent) else p.learning_patterns
    return (
        (f"{summary}\n\n" if summary else "") + f"**{s['memory_strengths']}**\n\n{strengths}",
        f"**{s['memory_growth']}**\n\n{growth}",
        f"*{s['memory_last_sync']}: {p.last_updated or s['memory_never']}* · [" +
        ("管理洞察" if lang_code == "zh" else "Manage insights") + "](/account#insights)"
    )


def _header_markdown(session: dict) -> str:
    agent = session["agent"]
    s = UI[agent.language]
    return f"""
    <section class="studio-header">
        <img class="studio-mark" src="{HEADER_ICON_SRC}" alt="" aria-hidden="true">
        <div class="studio-title-group">
            <div class="studio-title">{s["coach_name"]}</div>
            <div class="studio-subtitle">{s["coach_sub"]}</div>
        </div>
        <div class="studio-account"><a class="studio-account-link" href="/help">{s["help_link"]}</a><a class="studio-account-link" href="/account">{s["account_link"]}</a></div>
    </section>
    """


def _tracker_html(agent, module_code: str) -> str:
    lc = agent.language
    s = UI[lc]
    states = list(CoachingState)
    current_idx = states.index(agent.current_state)
    current_name = STAGE_NAMES[lc][agent.current_state]
    next_name = STAGE_NAMES[lc][states[min(current_idx + 1, len(states) - 1)]]
    mode_badge = _module_label(module_code, lc)
    dots = []

    skipped = getattr(agent, "skipped_stages", set())
    for idx, state in enumerate(states):
        classes = ["tracker-dot"]
        title = STAGE_NAMES[lc][state]
        if idx < current_idx and state.value in skipped:
            # A stage the conversation jumped over isn't shown as done: for a coach in training that matters.
            classes.append("skipped")
            title = f"{title} · {s['stage_skipped']}"
        elif idx < current_idx:
            classes.append("done")
        elif idx == current_idx:
            classes.append("active")
        dots.append(
            f"<div class='{' '.join(classes)}' title='{title}'><span>{idx + 1}</span></div>"
        )

    return f"""
    <div class="tracker-shell">
        <div class="tracker-copy">
            <div class="tracker-eyebrow">{s["progress"]} · {mode_badge}</div>
            <div class="tracker-stage">{s["current_stage"]}: {current_name}</div>
            {f'<div class="tracker-next">{s["up_next"]}: {next_name}</div>' if current_idx < len(states) - 1 else ""}
        </div>
        <div class="tracker-dots">{''.join(dots)}</div>
    </div>
    """


def _rating_updates(session: dict):
    """The end-of-session question (card, its text, the 1-5 buttons): hidden until the session ends, then asked once."""
    agent = session["agent"]
    s = UI[agent.language]
    if not session.get("id") or not agent.is_session_ended():
        return gr.update(visible=False), gr.update(), gr.update()
    if session.get("rating"):
        return gr.update(visible=True), gr.update(value=f'<p class="rating-question">{s["rating_thanks"]}</p>'), gr.update(visible=False)
    text = f'<p class="rating-question">{s["rating_question"]}</p><p class="rating-scale">{s["rating_scale"]}</p>'
    return gr.update(visible=True), gr.update(value=text), gr.update(visible=True)


def _topic_updates(session: dict):
    """The "practise your own topic" band (card, prompt, topic box, button). It shows in practice mode until the coach
    asks their first question, so a coach who doesn't fancy the client the AI picked can describe their own. Once they
    have used their own topic it has done its job and goes (New Session brings a random client and the band back)."""
    agent = session["agent"]
    s = UI[agent.language]
    show = (session["module"] == "coachee" and agent.mode == "llm" and _user_turns(agent) == 0
            and not getattr(agent, "topic", "") and not agent.is_session_ended()
            and session.get("unavailable_reason") != "allowance")
    return (
        gr.update(visible=show),
        gr.update(value=f'<p class="topic-question">{s["topic_prompt"]}</p>'),
        gr.update(placeholder=s["topic_placeholder"]),
        gr.update(value=s["topic_start"]),
    )


def rate_session(choice: str, session, request: gr.Request = None):
    """One tap on the end-of-session question; tapping again changes the rating."""
    user = _current_user(request)
    rating = int(choice) if str(choice).isdigit() else 0
    if (user and session and session.get("user_id") == user["id"] and session.get("id")
            and session["agent"].is_session_ended() and 1 <= rating <= 5):
        get_store().rate_session(session["id"], user["id"], session["module"], rating)
        session["rating"] = rating
    if not session:
        return gr.update(visible=False), gr.update(), gr.update(), session
    return (*_rating_updates(session), session)


def _settings_button_label(session: dict) -> str:
    agent = session["agent"]
    s = UI[agent.language]
    return s["settings"]


def _tts_payload(text: str) -> str:
    return f"{time.time_ns()}|||{text}"


# Accounts and stored sessions -----------------------------------------------------------


def _current_user(request: gr.Request | None) -> dict | None:
    """The signed-in user; Gradio passes the id that the auth dependency returned as request.username."""
    username = getattr(request, "username", None) if request is not None else None
    if not username:
        return None
    try:
        user = get_store().get_user(int(username))
    except ValueError:
        return None
    return user if user and user["status"] == "active" else None


def _require_user(request: gr.Request | None, lang_code: str) -> dict:
    user = _current_user(request)
    if user is None:
        raise gr.Error(UI[lang_code]["signed_out"])
    return user


def _user_turns(agent) -> int:
    return sum(1 for item in agent.context if item["role"] == agent.user_role)


def _load_profile(user_id: int, module: str) -> UserProfile:
    return UserProfile.from_dict(get_store().get_profile(user_id, module))


def _attach(session: dict, user: dict) -> dict:
    """Bind a conversation to its owner: usage metering and today's allowance for the header."""
    store = get_store()
    user_id, session_id = user["id"], session["id"]
    session["user_id"] = user_id
    session["agent"].on_usage = lambda model, prompt, completion: store.record_usage(user_id, session_id, model, prompt, completion)
    session["allowance"] = quota.allowance(store, user, session["module"])
    return session


def _save(session: dict) -> bool:
    """Store the conversation, unless another tab or device saved it after this page last did: newer turns win."""
    if not session.get("id"):
        return False
    agent = session["agent"]
    score = None
    if session["module"] == "coachee" and agent.is_session_ended() and agent.context and not agent.review_failed:
        score = review_score(agent.context[-1]["content"])
    version = get_store().save_session(
        session["id"],
        state=agent.to_dict(),
        status="completed" if agent.is_session_ended() else "active",
        stage=agent.current_state.name,
        user_turns=_user_turns(agent),
        language=agent.language,
        mode=agent.mode,
        expected_version=session.get("version"),
        practice_score=score,
    )
    if version is None:
        # Both pages replied at the same moment. The other one saved first; this page reloads it on its next action.
        logger.warning("Session %s changed elsewhere; this page's last turn was not saved", session["id"])
        session["version"] = _STALE
        gr.Warning(UI[agent.language]["reply_not_saved"])
        return False
    session["version"] = version
    return True


# A version no stored session has, so the next action reloads the conversation (see _save).
_STALE = dt.datetime(1970, 1, 1)


def _reload_if_changed(session: dict, user: dict, lang_code: str) -> dict:
    """The stored conversation, when another tab or device has changed it since this page last saved or loaded it.

    The same conversation, still in this module and language, is reloaded and flagged "changed_elsewhere", so the
    action that found it shows the latest turns instead of acting on an old copy. Anything else (finished there and a
    new one started, or another language) needs a fresh page.
    """
    store = get_store()
    current = store.session_version(session["id"])
    if current is not None and current["updated_at"] == session.get("version"):
        return session
    if (current is None or current["status"] == "abandoned" or current["module"] != session["module"]
            or current["language"] != lang_code):
        raise gr.Error(UI[lang_code]["session_moved"])
    reloaded = _restore_session(store.get_session(session["id"]), user)
    if reloaded is None:
        raise gr.Error(UI[lang_code]["session_moved"])
    reloaded["changed_elsewhere"] = True
    return reloaded


def _unavailable_notice(user: dict, module_code: str, lang_code: str) -> str | None:
    """Why no AI session can start in this module now, and when it can, or None. There is no canned fallback:
    canned questions in an AI coaching app read as an AI that isn't listening."""
    store = get_store()
    allowance = quota.allowance(store, user, module_code)
    if allowance.blocked_reason is None:
        return None
    s = UI[lang_code]
    notice = s[f"quota_{allowance.blocked_reason}"].format(hours=allowance.hours_until_available())
    other = "coachee" if module_code == "coach" else "coach"
    if quota.allowance(store, user, other).blocked_reason is None:
        notice += " " + s["quota_other_mode"].format(mode=_module_label(other, lang_code))
    return notice


def _unavailable_session(user: dict, module_code: str, lang_code: str, notice: str, reason: str = "allowance") -> dict:
    """What the page shows when no session can start: the notice in the chat, nothing to type into, nothing stored.
    reason is "allowance" (today's sessions are used up) or "ai" (the AI couldn't answer)."""
    agent = _build_agent(module_code, "llm", lang_code)
    agent.context = [{"role": agent.assistant_role, "content": notice}]
    return {"module": module_code, "agent": agent, "user_id": user["id"], "unavailable": notice,
            "unavailable_reason": reason, "allowance": quota.allowance(get_store(), user, module_code)}


def _request_language(request: gr.Request | None, fallback: str | None) -> str | None:
    """The language this person last chose (shared with the account pages), else their browser's."""
    try:
        cookies, headers = request.cookies, request.headers
    except AttributeError:
        return fallback
    return account_pages.preferred_language(cookies, headers, fallback)


def _open_session(user: dict, module_code: str, mode_code: str, lang_code: str, topic: str = "", *,
                  explicit: bool = False, expected: tuple[str, dt.datetime] | None = None) -> dict:
    """Generate the opening before replacing the mode's previous session."""
    notice = _unavailable_notice(user, module_code, lang_code) if mode_code == "llm" else None
    if notice:
        return _unavailable_session(user, module_code, lang_code, notice)
    store = get_store()
    fresh_coach = explicit and module_code == "coach" and mode_code == "llm"
    try:
        agent = _build_agent(module_code, mode_code, lang_code, _load_profile(user["id"], module_code))
        if module_code == "coachee":
            agent.topic = topic
        if fresh_coach:
            agent.fresh_start = True
        elif module_code == "coach" and mode_code == "llm":
            now = db.utcnow()
            agent.last_card = store.latest_card(user["id"], since=now - FOLLOW_UP_WITHIN, until=now - FOLLOW_UP_AFTER)
        if explicit and mode_code == "llm" and not _safe_key():
            raise ValueError("AI model key is not configured.")
        session_id = str(uuid.uuid4())
        session = _attach({"module": module_code, "agent": agent, "id": session_id}, user)
        _append_opening_prompt(agent)
        version = store.insert_session(session_id, user["id"], module_code, lang_code, mode_code,
                                       agent.current_state.name, agent.to_dict(), replace_current=True, expected=expected)
    except Exception:
        logger.exception("Opening a session failed")
        key = "topic_failed" if topic else "new_session_failed" if explicit else "ai_unavailable"
        return _unavailable_session(user, module_code, lang_code, UI[lang_code][key], reason="ai")
    if version is None:
        return _unavailable_session(user, module_code, lang_code, UI[lang_code]["session_moved"], reason="conflict")
    session["version"] = version
    return session


def _restore_session(row: dict, user: dict) -> dict | None:
    """Reopen a stored session; an unreadable active session can be set aside if it hasn't changed."""
    agent_class = CoacheeAgent if row["module"] == "coachee" else CoachAgent
    try:
        agent = agent_class.from_dict(json.loads(row["state"]), user_profile=_load_profile(user["id"], row["module"]))
    except (KeyError, TypeError, ValueError):
        logger.exception("Stored session %s could not be reopened", row["id"])
        if row["status"] == "active":
            get_store().abandon_session(row["id"], expected_version=row["updated_at"])
        return None
    if row["module"] == "coach" and row["status"] == "completed" and row["mode"] == "llm" and not agent.action_card_result:
        # Older cards were saved as chat bubbles. Leave those in place; show a missing result explicitly otherwise.
        has_legacy_card = any(
            msg.get("role") == "coach" and any(msg.get("content", "").startswith(UI[lang]["card_title"] + "\n\n")
                                              and msg["content"].endswith(UI[lang]["card_saved"]) for lang in ("en", "zh"))
            for msg in agent.context
        )
        if not has_legacy_card:
            saved = row if "card" in row else get_store().get_session(row["id"])
            card = (saved or {}).get("card")
            agent.action_card_result = {"status": "ready", "card": card} if card else {"status": "unknown"}
    return _attach({"module": row["module"], "agent": agent, "id": row["id"], "version": row["updated_at"]}, user)


def _resume_mode(user: dict, module_code: str, mode_code: str, lang_code: str) -> dict:
    store = get_store()
    row = store.resumable_session(user["id"], module_code)
    while row:
        restored = _restore_session(row, user)
        if restored:
            return restored
        if row["status"] == "completed":
            unavailable = _unavailable_session(user, module_code, lang_code, UI[lang_code]["session_moved"], reason="conflict")
            return {**unavailable, "expected": (row["id"], row["updated_at"])}
        row = store.resumable_session(user["id"], module_code)
    session = _open_session(user, module_code, mode_code, lang_code)
    if session.get("unavailable_reason") == "conflict":
        # Another tab may have opened this mode while the first opening was being generated.
        row = store.resumable_session(user["id"], module_code)
        if row:
            return _restore_session(row, user) or session
    return session


def _ensure_session(session: dict | None, user: dict, module_sel: str, mode_sel: str, lang_sel: str):
    """Continue the page's conversation, checking for changes made in another tab."""
    if not session or session.get("user_id") != user["id"]:
        return _resume_mode(user, _safe_module(module_sel), _safe_mode(mode_sel), _safe_lang(lang_sel))
    if not session.get("id"):
        return session
    session = _reload_if_changed(session, user, session["agent"].language)
    session["agent"].user_profile = _load_profile(user["id"], session["module"])
    return session


def _append_opening_prompt(agent):
    """The AI's next prompt (a session's opening, or the next stage after Skip Ahead). Raises if the AI can't answer."""
    api_key = _safe_key()
    if agent.mode == "llm" and not api_key and not (
            isinstance(agent, CoacheeAgent) and agent.is_session_ended()):
        prompt = _llm_config_message(agent.language)
    else:
        prompt = agent.get_stage_prompt(api_key=api_key or None)
    agent.context.append({"role": agent.assistant_role, "content": prompt})
    return prompt


def _session_start_outputs(session: dict):
    """Everything the page shows for a conversation: used on load, new session and module switch."""
    agent = session["agent"]
    lc = agent.language
    copy = _session_ui(agent, session["module"])
    coach_btn, coachee_btn = _module_button_updates(session["module"], lc)
    m_s, m_g, m_f = _memory_ui_updates(agent, lc)
    return dict(
        chat=_chat_history_from_context(agent, session.get("id")),
        tracker=_tracker_html(agent, session["module"]),
        header=_header_markdown(session),
        coach_btn=coach_btn,
        coachee_btn=coachee_btn,
        mode_context=_mode_context_html(session),
        msg=gr.update(placeholder=copy["placeholder"], interactive=not agent.is_session_ended() and not session.get("unavailable"),
                      value=""),
        tts=gr.update(value=_tts_payload(agent.context[-1]["content"]) if agent.context else ""),
        memory=(m_s, m_g, m_f),
        module=gr.update(value=session["module"]),
        lang=gr.update(label=UI[lc]["language"], value=_lang_selector(lc)),
        # The hidden mode setting stays on the default; the daily allowance alone decides when a session uses templates.
        mode=gr.update(choices=_mode_choices(lc), value=_mode_label(default_mode, lc)),
        rating=_rating_updates(session),
        topic=_topic_updates(session),
    )


def initial_load(session: dict, module_sel: str, mode_sel: str, lang_sel: str, request: gr.Request = None):
    """Resume the last viewed mode and its conversation, opening only when needed."""
    user = _require_user(request, _safe_lang(lang_sel))
    store = get_store()
    first_visit = not store.list_sessions(user["id"], limit=1)
    module = store.last_module(user["id"])
    if not module:
        row = store.latest_active_session(user["id"]) or store.resumable_session(user["id"])
        module = row["module"] if row else default_module
    session = _resume_mode(user, module, _safe_mode(mode_sel), _request_language(request, None) or _safe_lang(lang_sel))
    agent = session["agent"]
    out = _session_start_outputs(session)
    welcome = _welcome_html(agent.language) if first_visit else ""
    return (
        out["chat"], out["tracker"], out["header"], out["coach_btn"], out["coachee_btn"], out["mode_context"],
        out["msg"], out["tts"], *out["memory"], out["module"], out["lang"], out["mode"],
        _memory_title(agent.language), welcome, *_language_control_updates(agent.language),
        *out["rating"], *out["topic"], session,
    )


def _memory_title(lang_code: str) -> str:
    return f"### {UI[lang_code]['memory_title']}"


def _welcome_html(lang_code: str) -> str:
    """A short orientation shown once, on someone's first visit; welcome_js closes it in the browser."""
    s = UI[lang_code]
    return f"""
    <div class="welcome-layer" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
        <div class="welcome-card">
            <h2 id="welcome-title">{s["welcome_title"]}</h2>
            <ul>
                <li>{s["welcome_coach"]}</li>
                <li>{s["welcome_coachee"]}</li>
                <li>{s["welcome_session"]}</li>
            </ul>
            <div class="welcome-actions">
                <button class="welcome-start" type="button" data-welcome-close>{s["welcome_start"]}</button>
                <a class="welcome-guide" href="/help">{s["welcome_guide"]}</a>
            </div>
        </div>
    </div>
    """


def _respond_outputs(message_update, chat_history, agent, session, tts_update=None, memory_updates=None):
    if tts_update is None:
        tts_update = gr.update()
    if memory_updates is None:
        memory_updates = _memory_ui_updates(agent, agent.language)
    return (
        message_update,
        chat_history,
        _tracker_html(agent, session["module"]),
        tts_update,
        _header_markdown(session),
        _mode_context_html(session),
        memory_updates[0],
        memory_updates[1],
        memory_updates[2],
        *_rating_updates(session),
        *_topic_updates(session),
        session,
    )


def _next_stage_outputs(message_update, chat_history, agent, session, tts_update=None, memory_updates=None):
    return _respond_outputs(message_update, chat_history, agent, session, tts_update, memory_updates)


def _streaming_outputs(chat_history, session):
    """Mid-reply update: the transcript changes and the practice topic band goes (a question has been asked); the other
    panels are left untouched."""
    untouched = (gr.update(),) * (RESPOND_OUTPUT_COUNT - 3 - TOPIC_OUTPUT_COUNT)
    topic = (gr.update(visible=False),) + (gr.update(),) * (TOPIC_OUTPUT_COUNT - 1)
    return (gr.update(value=""), chat_history) + untouched + topic + (session,)


def _learn_from_session(session: dict, api_key: str):
    """Fold a finished session into the person's profile. Runs off the request thread so the final reply isn't delayed."""
    agent = session["agent"]
    try:
        analysis = agent.analyze_session_for_memory(api_key)
        if not analysis:
            return
        store = get_store()
        data = store.get_profile(session["user_id"], session["module"])
        profile = merge_analysis(UserProfile.from_dict(data), analysis)
        # A concurrent owner edit wins; a late analysis must never replace it.
        store.save_profile(session["user_id"], session["module"], profile.to_dict(), expected_version=profile_version(data))
        agent.user_profile = _load_profile(session["user_id"], session["module"])
    except Exception:
        logger.exception("Updating the user profile from a finished session failed")


def retry_practice_review(row: dict, state: dict, user: dict) -> str:
    """Claim a failed review, then atomically replace its notice and save its score."""
    api_key = _safe_key()
    if not api_key:
        return "retry_failed"
    now = db.utcnow()
    if state.get("review_retry_until", "") > now.isoformat():
        return "retry_busy"

    store = get_store()
    agent = CoacheeAgent.from_dict(state)
    _attach({"id": row["id"], "module": "coachee", "agent": agent}, user)
    original = {key: value for key, value in state.items() if key != "review_retry_until"}
    # A crashed worker leaves a retry available again after the model's request window.
    claimed = {**original, "review_retry_until": (now + dt.timedelta(minutes=5)).isoformat()}
    version = store.save_review_attempt(row["id"], claimed, row["updated_at"])
    if version is None:
        return "retry_busy"

    agent.context.pop()  # The failed review occupies the last bubble, outside the original dialogue.
    if "stopped_at_limit" not in state and row["user_turns"] >= MAX_USER_TURNS_PER_SESSION:
        # Older limit endings left the stage in place and included the last client reply. A natural goodbye
        # moved to Closing and replaced the client reply with the review.
        if agent.current_state != CoachingState.CLOSING or (agent.context and agent.context[-1]["role"] == agent.assistant_role):
            agent.stopped_at_limit = MAX_USER_TURNS_PER_SESSION
    try:
        review = agent._build_final_review(api_key)
        if not agent.review_failed:
            agent.context.append({"role": agent.assistant_role, "content": review})
            saved = store.save_review_attempt(row["id"], agent.to_dict(), version, score=review_score(review))
            return "retry_saved" if saved is not None else "retry_busy"
    except Exception:
        logger.exception("Saving the regenerated practice review failed")
    try:
        store.save_review_attempt(row["id"], original, version)
    except Exception:
        logger.exception("Releasing the failed practice review retry failed")
    return "retry_failed"


def _action_card_text(card: dict, lang_code: str) -> str:
    s = UI[lang_code]
    sep = "：" if lang_code == "zh" else ": "
    fields = [f"{s['card_' + key]}{sep}{card[key]}" for key in ACTION_CARD_FIELDS if card.get(key)]
    return "\n".join([s["card_title"], "", *fields, "", s["card_saved"]])


def _makes_action_card(session: dict) -> bool:
    return session["module"] == "coach" and session["agent"].mode == "llm"


def _action_card_outcome_text(agent, session_id: str | None = None) -> str:
    result = agent.action_card_result
    if result.get("status") == "ready" and result.get("card"):
        return _action_card_text(result["card"], agent.language)
    key = "card_" + result.get("status", "unknown")
    if result.get("status") == "pending" and result.get("retry_until", "") <= db.utcnow().isoformat():
        key = "card_interrupted"
    s = account_pages.T[agent.language]
    notice = s.get(key, s["card_unknown"])
    if session_id:
        return f'{notice}\n\n[{s["card_history"]}](/sessions/{session_id})'
    return f'{notice}\n\n[{s["card_history"]}](/account)'


def retry_action_card(row: dict, state: dict, user: dict, *, api_key: str | None = None) -> str:
    """Claim a version before calling the model; save the result and its status in one transaction."""
    if row["user_id"] != user["id"] or not can_recover_action_card(row, state):
        return "card_busy"
    if state.get("action_card_result", {}).get("retry_until", "") > db.utcnow().isoformat():
        return "card_busy"
    store = get_store()
    claimed = {**state, "action_card_result": {"status": "pending",
               "retry_until": (db.utcnow() + dt.timedelta(minutes=5)).isoformat()}}
    try:
        version = store.save_action_card_attempt(row["id"], user["id"], claimed, row["updated_at"])
    except Exception:
        logger.exception("Claiming an action card request failed")
        return "card_save_failed"
    if version is None:
        return "card_busy"
    card = None
    try:
        api_key = _safe_key() if api_key is None else api_key
        if not api_key:
            raise ValueError("Action card model is unavailable")
        agent = CoachAgent.from_dict(state)
        _attach({"id": row["id"], "module": "coach", "agent": agent}, user)
        card = agent.action_card(api_key)
        result = {"status": "ready", "card": card} if card else {"status": "none"}
    except Exception:
        logger.exception("Generating an action card failed")
        result = {"status": "generation_failed"}
    try:
        saved = store.save_action_card_attempt(row["id"], user["id"], {**state, "action_card_result": result},
                                               version, card=card)
        if saved is None:
            return "card_busy"
        return "card_saved" if card else "card_" + result["status"]
    except Exception:
        logger.exception("Saving an action card failed")
        try:
            store.save_action_card_attempt(row["id"], user["id"],
                                          {**state, "action_card_result": {"status": "save_failed"}}, version)
        except Exception:
            logger.exception("Recording the action card save failure failed; its lease will expire")
        return "card_save_failed"


def _finish_session(session: dict, api_key: str) -> str | None:
    """Keep what a finished session produced, then learn from it in the background.

    The artifact stays outside the original dialogue. Returns its saved card or an explicit outcome notice.
    """
    agent = session["agent"]
    card_text = None
    if _makes_action_card(session):
        outcome = "card_save_failed"
        try:
            store = get_store()
            row = store.get_session(session["id"])
            if row and row["updated_at"] == session.get("version"):
                state = json.loads(row["state"])
                # Only the initial close is automatic; subsequent attempts use the history form.
                if not state.get("action_card_result") and not row.get("card"):
                    outcome = retry_action_card(row, state, store.get_user(session["user_id"]), api_key=api_key)
                else:
                    outcome = "card_saved"
                row = store.get_session(session["id"])
                if row:
                    agent.action_card_result = json.loads(row["state"]).get("action_card_result", {})
                    if row.get("card"):
                        agent.action_card_result = {"status": "ready", "card": row["card"]}
                    session["version"] = row["updated_at"]
            else:
                outcome = "card_busy"
        except Exception:
            logger.exception("Loading the action card result failed")
        if outcome == "card_save_failed":
            agent.action_card_result = {"status": "save_failed"}
        elif outcome == "card_busy":
            session["version"] = _STALE
        card_text = _action_card_outcome_text(agent, session["id"])
    if agent.mode == "llm" and api_key:
        threading.Thread(target=_learn_from_session, args=(session, api_key), daemon=True).start()
    return card_text


def respond(message, chat_history, session, module_sel, mode_sel, lang_sel, request: gr.Request = None):
    user = _require_user(request, _safe_lang(lang_sel))
    session = _ensure_session(session, user, module_sel, mode_sel, lang_sel)
    agent = session["agent"]
    s = UI[agent.language]
    user_msg = (message or "").strip()

    if session.get("unavailable"):
        gr.Info(session["unavailable"])
        yield _respond_outputs(gr.update(interactive=False), _chat_history_from_context(agent, session.get("id")), agent, session)
        return

    if session.pop("changed_elsewhere", False):
        # Show what was said in the other tab or device first; the person's message stays in the box to send again.
        gr.Info(s["session_changed_elsewhere"])
        yield _respond_outputs(gr.update(interactive=not agent.is_session_ended()), _chat_history_from_context(agent, session.get("id")),
                               agent, session)
        return

    if not user_msg:
        gr.Warning(s["empty_warning"])
        yield _respond_outputs(gr.update(), chat_history, agent, session)
        return

    if len(user_msg) > MAX_MESSAGE_CHARS:
        gr.Warning(s["message_too_long"].format(limit=MAX_MESSAGE_CHARS))
        yield _respond_outputs(gr.update(), chat_history, agent, session)
        return

    if agent.is_session_ended():
        gr.Info(s["session_ended"])
        yield _respond_outputs(gr.update(value="", interactive=False), chat_history, agent, session)
        return

    if not _message_limiter.allow(user["id"]):
        gr.Warning(s["rate_limited"])
        yield _respond_outputs(gr.update(), chat_history, agent, session)
        return

    lock = _agent_lock(agent)
    if not lock.acquire(blocking=False):
        gr.Warning(s["busy_warning"])
        yield (gr.skip(),) * RESPOND_OUTPUT_COUNT
        return
    try:
        if _user_turns(agent) >= MAX_USER_TURNS_PER_SESSION:
            # Only a conversation saved before reaching the limit ended it lands here: it ends now, with its review or
            # action card, rather than staying locked with no way to finish (Xiaofang's practice under the old cap).
            yield from _end_at_limit(_chat_history_from_context(agent, session.get("id")), session, _safe_key(), gr.update())
            return
        if (agent.mode == "llm" and coaching_core.conversation_capacity(agent.context, user_msg) == "full"
                and not (session["module"] == "coach" and safety.looks_like_crisis(user_msg))):
            gr.Warning(s["context_full"])
            yield _respond_outputs(gr.update(value=user_msg), chat_history, agent, session)
            return
        yield from _stream_reply(user_msg, chat_history, agent, session)
    finally:
        lock.release()


def _stage_change_notice(agent, module_code: str, skipped_before: set[int]) -> str:
    """The note when the tracker moves on. In practice it also names any stage the coach skipped, so a jump on the
    first question reads as "you skipped agreeing the goal" rather than the tracker racing ahead."""
    s = UI[agent.language]
    names = STAGE_NAMES[agent.language]
    stage_name = names.get(agent.current_state, "")
    newly_skipped = sorted(set(getattr(agent, "skipped_stages", set())) - skipped_before)
    if module_code == "coachee" and newly_skipped:
        separator = "」「" if agent.language == "zh" else ", "
        skipped = separator.join(names[CoachingState(value)] for value in newly_skipped)
        return s["stage_moved_skipping"].format(stage=stage_name, skipped=skipped)
    return s["stage_moved"].format(stage=stage_name)


def _stream_reply(user_msg, chat_history, agent, session):
    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": user_msg})
    yield _streaming_outputs(list(chat_history), session)
    old_state = agent.current_state
    skipped_before = set(getattr(agent, "skipped_stages", set()))

    api_key = _safe_key()
    if session["module"] == "coach" and safety.looks_like_crisis(user_msg):
        coach_response = safety.CRISIS_REPLY[agent.language]
        agent.context.append({"role": agent.user_role, "content": user_msg})
        agent.context.append({"role": agent.assistant_role, "content": coach_response})
        get_store().log(session["user_id"], "safety_flag", target_user_id=session["user_id"], target_session_id=session["id"])
    elif agent.mode == "llm" and not api_key:
        coach_response = _llm_config_message(agent.language)
        agent.context.append({"role": agent.user_role, "content": user_msg})
        agent.context.append({"role": agent.assistant_role, "content": coach_response})
    else:
        coach_response = ""
        try:
            for coach_response in agent.stream_response(user_msg, api_key=api_key or None):
                yield _streaming_outputs(chat_history + [{"role": "assistant", "content": coach_response}], session)
        except coaching_core.ContextCapacityError:
            gr.Warning(UI[agent.language]["context_full"])
            chat_history.pop()
            yield _respond_outputs(gr.update(value=user_msg), chat_history, agent, session)
            return
        except Exception:
            logger.exception("Model reply failed")
            gr.Warning(UI[agent.language]["ai_reply_error"])
            chat_history.pop()
            yield _respond_outputs(gr.update(value=user_msg), chat_history, agent, session)
            return

    if agent.current_state != old_state:
        gr.Info(_stage_change_notice(agent, session["module"], skipped_before))

    if not _save(session):
        store = get_store()
        latest = store.get_session(session["id"])
        restored = _restore_session(latest, store.get_user(session["user_id"])) if latest else None
        if restored and latest["status"] != "abandoned":
            session = restored
            agent = session["agent"]
        else:
            agent.context = json.loads(latest["state"])["context"] if latest else []
        yield _respond_outputs(gr.update(value=user_msg, interactive=not agent.is_session_ended()),
                               _chat_history_from_context(agent, session.get("id")), agent, session)
        return

    chat_history.append({"role": "assistant", "content": coach_response})
    tts_update = gr.update(value=_tts_payload(coach_response))
    if not agent.is_session_ended():
        left = MAX_USER_TURNS_PER_SESSION - _user_turns(agent)
        if left <= 0:
            yield from _end_at_limit(chat_history, session, api_key, tts_update)
            return
        if left <= quota.MESSAGES_LEFT_WARNING:
            # Says how far they have come as well as what is left, so the end is never a surprise.
            gr.Warning(UI[agent.language]["turns_left"].format(
                limit=MAX_USER_TURNS_PER_SESSION, used=MAX_USER_TURNS_PER_SESSION - left, left=left))
    yield from _close_turn(chat_history, session, api_key, tts_update)


def _end_at_limit(chat_history, session, api_key, tts_update):
    """The person used every message a conversation allows: it ends as if finished, with the practice review, or with a
    goodbye and the action card in AI Coach, instead of staying locked with no way to finish."""
    agent = session["agent"]
    notice = "turn_limit_review" if session["module"] == "coachee" else "turn_limit"
    gr.Info(UI[agent.language][notice].format(limit=MAX_USER_TURNS_PER_SESSION))
    # The notice and the last reply first: a practice review takes a few seconds to write.
    yield _respond_outputs(gr.update(value="", interactive=False), list(chat_history), agent, session, tts_update)
    chat_history.append({"role": "assistant", "content": agent.end_at_limit(MAX_USER_TURNS_PER_SESSION, api_key)})
    if _save(session):
        yield from _close_turn(chat_history, session, api_key, gr.update())


def _close_turn(chat_history, session, api_key, tts_update):
    """The end of a turn: a session that has just finished keeps its score or action card, then the page updates."""
    agent = session["agent"]
    is_ended = agent.is_session_ended()
    if is_ended:
        msg = "会话已结束" if agent.language == "zh" else "Session Complete"
        gr.Info(msg)
        session["allowance"] = quota.allowance(get_store(), get_store().get_user(session["user_id"]), session["module"])
        if _makes_action_card(session):
            # Show the closing words first; the action card follows a moment later.
            yield _respond_outputs(gr.update(value="", interactive=False), list(chat_history), agent, session, tts_update)
            tts_update = gr.update()
        card_text = _finish_session(session, api_key)
        if card_text:
            chat_history.append({"role": "assistant", "content": card_text})

    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    yield _respond_outputs(
        gr.update(value="", interactive=not is_ended),
        chat_history,
        agent,
        session,
        tts_update,
        (m_s, m_g, m_f),
    )


def next_stage(chat_history, session, module_sel, mode_sel, lang_sel, request: gr.Request = None):
    user = _require_user(request, _safe_lang(lang_sel))
    session = _ensure_session(session, user, module_sel, mode_sel, lang_sel)
    agent = session["agent"]
    if session.get("unavailable"):
        gr.Info(session["unavailable"])
        return _next_stage_outputs(gr.update(interactive=False), _chat_history_from_context(agent, session.get("id")), agent, session)
    if session.pop("changed_elsewhere", False):
        gr.Info(UI[agent.language]["session_changed_elsewhere"])
        return _next_stage_outputs(gr.update(interactive=not agent.is_session_ended()), _chat_history_from_context(agent, session.get("id")),
                                   agent, session)
    lock = _agent_lock(agent)
    if not lock.acquire(blocking=False):
        gr.Warning(UI[agent.language]["busy_warning"])
        return (gr.skip(),) * NEXT_STAGE_OUTPUT_COUNT
    try:
        return _advance_stage(chat_history, session)
    finally:
        lock.release()


def _advance_stage(chat_history, session):
    agent = session["agent"]
    s = UI[agent.language]

    old_state = agent.current_state
    old_sub = agent.current_sub_phase
    old_turns = agent.turns_in_current_stage
    old_complete = agent.session_complete

    if hasattr(agent, "manual_advance_guard"):
        blocker = agent.manual_advance_guard()
        if blocker:
            gr.Warning(blocker)
            return _next_stage_outputs(gr.update(), chat_history, agent, session)

    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    if not agent.force_next_state():
        gr.Info(s["session_ended"])
        return _next_stage_outputs(gr.update(value="", interactive=False), chat_history, agent, session, memory_updates=(m_s, m_g, m_f))

    if session["module"] == "coachee" and not agent.is_session_ended():
        # In practice the person is the coach: the tracker moves on and they ask the next question themselves.
        _save(session)
        return _next_stage_outputs(gr.update(), chat_history, agent, session, memory_updates=(m_s, m_g, m_f))

    try:
        new_prompt = _append_opening_prompt(agent)
    except coaching_core.ContextCapacityError:
        agent.current_state = old_state
        agent.current_sub_phase = old_sub
        agent.turns_in_current_stage = old_turns
        agent.session_complete = old_complete
        gr.Warning(s["context_full"])
        return _next_stage_outputs(gr.update(), chat_history, agent, session)
    except Exception:
        logger.exception("Next-stage prompt failed")
        agent.current_state = old_state
        agent.current_sub_phase = old_sub
        agent.turns_in_current_stage = old_turns
        agent.session_complete = old_complete
        gr.Warning(s["ai_reply_error"])
        return _next_stage_outputs(gr.update(), chat_history, agent, session)

    chat_history = list(chat_history or [])
    if not _save(session):
        return _next_stage_outputs(gr.update(), chat_history, agent, session)
    chat_history.append({"role": "assistant", "content": new_prompt})

    is_ended = agent.is_session_ended()
    if is_ended:
        msg = "会话已结束" if agent.language == "zh" else "Session Complete"
        gr.Info(msg)
        session["allowance"] = quota.allowance(get_store(), get_store().get_user(session["user_id"]), session["module"])
        card_text = _finish_session(session, _safe_key())
        if card_text:
            chat_history.append({"role": "assistant", "content": card_text})

    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    return _next_stage_outputs(
        gr.update(value="", interactive=not is_ended),
        chat_history,
        agent,
        session,
        gr.update(value=_tts_payload(new_prompt)),
        (m_s, m_g, m_f),
    )


def _navigate_session(user: dict, module: str, mode: str, language: str, session: dict | None, *,
                      explicit: bool = False, topic: str = "", voice_sel: str | None = None):
    current = session if session and session.get("user_id") == user["id"] else None
    lock = _agent_lock(current["agent"]) if current else None
    if lock and not lock.acquire(blocking=False):
        gr.Warning(UI[language]["busy_warning"])
        return (gr.skip(),) * NEW_SESSION_OUTPUT_COUNT
    try:
        if explicit:
            expected = None
            if current and current["module"] == module:
                expected = (current["id"], current["version"]) if current.get("id") else current.get("expected")
            target = _open_session(user, module, mode, language, topic, explicit=True, expected=expected)
        else:
            target = _resume_mode(user, module, mode, language)
        if target.get("unavailable") and (explicit or current):
            gr.Warning(target["unavailable"])
            return (gr.skip(),) * NEW_SESSION_OUTPUT_COUNT
        if not explicit and target.get("id"):
            get_store().remember_module(user["id"], module)
            if current and current.get("id") == target["id"] and current.get("version") == target["version"]:
                return (gr.skip(),) * NEW_SESSION_OUTPUT_COUNT
        return _new_session_outputs(target, voice_sel)
    finally:
        if lock:
            lock.release()


def reset_session(lang_sel, module_sel, mode_sel, session=None, request: gr.Request = None):
    lc = _safe_lang(lang_sel)
    user = _require_user(request, lc)
    return _navigate_session(user, _safe_module(module_sel), _safe_mode(mode_sel), lc, session, explicit=True)


def _new_session_outputs(session: dict, voice_sel: str | None = None):
    out = _session_start_outputs(session)
    controls = _language_control_updates(session["agent"].language, voice_sel) if voice_sel is not None else (gr.skip(),) * 7
    return (
        out["chat"], out["tracker"], out["tts"], out["header"], out["coach_btn"], out["coachee_btn"], out["mode_context"],
        out["msg"], *out["memory"], out["module"], out["mode"], out["lang"],
        _memory_title(session["agent"].language), *controls, *out["rating"], *out["topic"], session,
    )


def start_with_topic(topic: str, lang_sel, mode_sel, session=None, request: gr.Request = None):
    """A new practice client on the coach's own topic, instead of the one the AI picked."""
    lc = _safe_lang(lang_sel)
    user = _require_user(request, lc)
    topic = (topic or "").strip()
    problem = ("topic_empty" if not topic else "topic_too_long" if len(topic) > MAX_TOPIC_CHARS
               else "topic_crisis" if safety.crisis_topic(topic) else None)
    if problem:
        gr.Warning(UI[lc][problem].format(limit=MAX_TOPIC_CHARS))
        return (gr.skip(),) * NEW_SESSION_OUTPUT_COUNT
    return _navigate_session(user, "coachee", _safe_mode(mode_sel), lc, session, explicit=True, topic=topic)


def _language_control_updates(language: str, voice_sel: str | None = None):
    s = UI[language]
    return (
        gr.update(value=s["send"]),
        gr.update(value=s["advance"]),
        gr.update(value=s["reset"]),
        gr.update(label=s["settings"], open=False),
        gr.update(value=s["mode_hint"]),
        gr.update(label=s["tts_enable"]),
        gr.update(label=s["tts_voice"], choices=[s["voice_f"], s["voice_m"]],
                  value=s["voice_m"] if voice_sel in (UI["en"]["voice_m"], UI["zh"]["voice_m"]) else s["voice_f"]),
    )


def switch_lang(new_lang, session, module_sel, mode_sel, voice_sel=None, request: gr.Request = None):
    lc = _safe_lang(new_lang)
    user = _require_user(request, lc)
    session = _ensure_session(session, user, module_sel, mode_sel, new_lang)
    session.pop("changed_elsewhere", None)  # the latest turns are translated and shown below
    agent = session["agent"]
    with _agent_lock(agent):
        if lc == agent.language:
            pass  # The language control can update when restoring a conversation.
        elif agent.translate_history(new_lang=lc, api_key=_safe_key() or None):
            agent.set_language(lc)
            if not (session["module"] == "coachee" and agent.is_session_ended()):
                _save(session)
        else:
            # Stay in the conversation's language (the language choice switches back) rather than mixing the two.
            gr.Warning(UI[lc]["translate_failed"].format(language=UI[lc]["lang_" + agent.language]))
            lc = agent.language
            new_lang = _lang_selector(lc)
    s = UI[lc]
    copy = _session_ui(agent, session["module"])
    coach_btn, coachee_btn = _module_button_updates(session["module"], lc)
    send, advance, reset, settings, hint, tts_enabled, tts_voice = _language_control_updates(lc, voice_sel)

    m_s, m_g, m_f = _memory_ui_updates(agent, lc)
    return (
        _chat_history_from_context(agent, session.get("id")),
        _tracker_html(agent, session["module"]),
        _header_markdown(session),
        coach_btn,
        coachee_btn,
        _mode_context_html(session),
        gr.update(placeholder=copy["placeholder"], interactive=not agent.is_session_ended() and not session.get("unavailable")),
        send, advance, reset, settings, hint,
        gr.update(label=s["language"], value=new_lang),
        gr.update(label=s["mode"], choices=_mode_choices(lc), value=_mode_label(default_mode, lc)),
        tts_enabled, tts_voice,
        m_s, m_g, m_f,
        _memory_title(lc),
        gr.update(value=session["module"]),
        *_rating_updates(session),
        *_topic_updates(session),
        session,
    )


def select_module(module_code: str, lang_sel: str, mode_sel: str, session=None, voice_sel="",
                  request: gr.Request = None):
    lc = _safe_lang(lang_sel)
    user = _require_user(request, lc)
    return _navigate_session(user, _safe_module(module_code), _safe_mode(mode_sel), lc, session, voice_sel=voice_sel)


def record_feedback(session, feedback: gr.LikeData, request: gr.Request = None):
    """Thumbs up/down on a reply, saved against the message's position in the transcript."""
    user = _current_user(request)
    if (not user or not session or session.get("user_id") != user["id"] or not session.get("id")
            or not isinstance(feedback.index, int) or not 0 <= feedback.index < len(session["agent"].context)):
        return
    value = {True: "like", False: "dislike"}.get(feedback.liked)
    get_store().set_feedback(user["id"], session["id"], feedback.index, value)


clean_indigo_theme = gr.themes.Default(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.sky,
    neutral_hue=gr.themes.colors.slate,
    # Fonts already on people's devices: Google Fonts is blocked in mainland China and would stall page loads there.
    font=["Manrope", "Helvetica Neue", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
          "Noto Sans SC", "Noto Sans CJK SC", "Roboto", "Arial", "sans-serif"],
).set(
    body_background_fill="#f3f8fd",
    body_background_fill_dark="#f3f8fd",
    body_text_color="#18364a",
    body_text_color_dark="#18364a",
    background_fill_primary="#ffffff",
    background_fill_primary_dark="#ffffff",
    background_fill_secondary="#eef5fb",
    background_fill_secondary_dark="#eef5fb",
    block_background_fill="#ffffff",
    block_background_fill_dark="#ffffff",
    block_border_width="0px",
    block_radius="18px",
    block_shadow="0 16px 36px rgba(17, 73, 119, 0.10)",
    input_background_fill="#ffffff",
    input_background_fill_dark="#ffffff",
    input_border_color="#d8e5f2",
    input_border_color_dark="#d8e5f2",
    input_radius="18px",
    button_primary_background_fill="#1979ba",
    button_primary_background_fill_dark="#1979ba",
    button_primary_background_fill_hover="#0f6aa8",
    button_primary_background_fill_hover_dark="#0f6aa8",
    button_secondary_background_fill="#f5f9fd",
    button_secondary_background_fill_dark="#f5f9fd",
    button_secondary_background_fill_hover="#edf5fb",
    button_secondary_background_fill_hover_dark="#edf5fb",
    button_secondary_text_color="#155e95",
    button_secondary_text_color_dark="#155e95",
)











with gr.Blocks(
    title="Coaching Practice Studio · 教练练习室",
    fill_height=True,
    fill_width=True,
) as demo:
    session_state = gr.State(_new_session())
    module_state = gr.State(default_module)
    coach_module_value = gr.State("coach")
    coachee_module_value = gr.State("coachee")

    gr.HTML(global_viewport_style, elem_id="viewport-style-injector")

    with gr.Column(elem_id="app-shell", min_width=0):
        intro_md = gr.HTML("", elem_classes="intro-md")
        with gr.Row(elem_id="topbar", elem_classes="module-tabs"):
            coach_module_btn = gr.Button("", elem_classes="module-card-btn", min_width=0)
            coachee_module_btn = gr.Button("", elem_classes="module-card-btn", min_width=0)
        mode_context_md = gr.HTML("", elem_classes="mode-context-md")

        with gr.Accordion(UI["zh"]["settings"], open=False, elem_id="settings-sheet") as settings_sheet:
            # The AI/Template switch is a technical fallback, so members don't see it (template mode starts by itself
            # when today's allowance is used up). It stays in the page because every handler reads its value.
            settings_hint = gr.Markdown(UI["zh"]["mode_hint"], elem_classes="settings-hint", visible=False)
            with gr.Row(elem_classes="settings-controls"):
                lang_radio = gr.Radio(["English", "中文"], label=UI["zh"]["language"], value="中文", scale=1, min_width=0)
                mode_radio = gr.Radio(
                    _mode_choices("zh"),
                    label=UI["zh"]["mode"],
                    value=_mode_label(default_mode, "zh"),
                    scale=1,
                    min_width=0,
                    visible=False,
                )
                tts_voice = gr.Radio([UI["zh"]["voice_f"], UI["zh"]["voice_m"]], label=UI["zh"]["tts_voice"], value=UI["zh"]["voice_f"], scale=1, min_width=0)
                # Off until someone turns it on, so replies aren't read aloud unexpectedly, e.g. in an office.
                tts_toggle = gr.Checkbox(label=UI["zh"]["tts_enable"], value=False, scale=1, min_width=0)
            # Filled in the browser (voice_note_js) when this device has no natural male voice for the language.
            gr.HTML('<p id="voice-note-text" class="voice-note"></p>', elem_id="voice-note")

            # AI Insights Dashboard
            gr.Markdown("---")
            with gr.Column(elem_classes="memory-dashboard"):
                memory_title_md = gr.Markdown(_memory_title("zh"))
                with gr.Row():
                    memory_strengths_md = gr.Markdown(f"**{UI['zh']['memory_strengths']}**\n\n- (Pending)")
                    memory_growth_md = gr.Markdown(f"**{UI['zh']['memory_growth']}**\n\n- (Pending)")
                memory_footer_md = gr.Markdown(f"*{UI['zh']['memory_last_sync']}: {UI['zh']['memory_never']}*")

        tracker = gr.HTML(elem_classes="tracker-md")

        with gr.Column(elem_id="chat-stage", min_width=0):
            chatbot = gr.Chatbot(show_label=False, elem_classes="chatbot", buttons=[], feedback_options=("Like", "Dislike"),
                                 group_consecutive_messages=False, min_width=0)

            with gr.Column(elem_id="rating-card", visible=False, min_width=0) as rating_card:
                rating_prompt = gr.HTML("", elem_classes="rating-prompt")
                with gr.Row(elem_classes="rating-row", visible=False) as rating_row:
                    rating_buttons = [gr.Button(str(n), elem_classes="rating-btn", min_width=0) for n in range(1, 6)]

            with gr.Column(elem_id="topic-card", visible=False, min_width=0) as topic_card:
                topic_prompt = gr.HTML("", elem_classes="topic-prompt")
                with gr.Row(elem_classes="topic-row"):
                    topic_input = gr.Textbox(show_label=False, container=False, lines=1, max_lines=2, max_length=MAX_TOPIC_CHARS,
                                             placeholder=UI["zh"]["topic_placeholder"], elem_id="topic-input", scale=1, min_width=0)
                    topic_btn = gr.Button(UI["zh"]["topic_start"], elem_classes="topic-btn", scale=0, min_width=0)

            with gr.Column(elem_id="composer-shell"):
                with gr.Row(elem_classes="composer-grid"):
                    with gr.Column(elem_id="input-panel", scale=1, min_width=0):
                        msg = gr.Textbox(
                            show_label=False,
                            placeholder=UI["zh"]["placeholder"],
                            container=False,
                            elem_id="chat-input-msg",
                            lines=4,
                            max_lines=6,
                            max_length=MAX_MESSAGE_CHARS,
                        )

                    with gr.Column(elem_id="action-panel", scale=0, min_width=0):
                        with gr.Row(elem_classes="action-row", elem_id="top-action-row"):
                            with gr.Column(elem_id="mic-btn-wrap", scale=0, min_width=56):
                                mic_btn = gr.HTML(
                                    '<button id="custom-mic-btn" class="custom-mic-btn" type="button" title="语音输入"><svg class="mic-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3 3 0 0 0 3-3V8a3 3 0 1 0-6 0v4a3 3 0 0 0 3 3Z"/><path d="M6.5 11.5a5.5 5.5 0 0 0 11 0"/><path d="M12 17v3"/><path d="M9.5 20h5"/></svg></button>'
                                )
                            send_btn = gr.Button(UI["zh"]["send"], variant="primary", elem_classes="send-btn-custom")

                        with gr.Row(elem_classes="action-row", elem_id="bottom-action-row"):
                            next_btn = gr.Button(UI["zh"]["advance"], variant="secondary", elem_id="next-btn")
                            reset_btn = gr.Button(UI["zh"]["reset"], variant="secondary", elem_id="reset-btn")

                tts_text = gr.Textbox(visible=False, elem_id="tts-text")

        welcome_html = gr.HTML("", elem_id="welcome-host", js_on_load=welcome_js)

    rating_outputs = [rating_card, rating_prompt, rating_row]
    topic_outputs = [topic_card, topic_prompt, topic_input, topic_btn]

    language_outputs = [send_btn, next_btn, reset_btn, settings_sheet, settings_hint, tts_toggle, tts_voice]
    new_session_outputs = [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg,
                           memory_strengths_md, memory_growth_md, memory_footer_md, module_state, mode_radio, lang_radio,
                           memory_title_md, *language_outputs, *rating_outputs, *topic_outputs, session_state]

    demo.load(
        initial_load,
        [session_state, module_state, mode_radio, lang_radio],
        [chatbot, tracker, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, tts_text, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, lang_radio, mode_radio, memory_title_md, welcome_html, *language_outputs, *rating_outputs, *topic_outputs, session_state],
        js=force_light_js,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(
        None, [tts_voice, lang_radio], None, js=voice_note_js)

    send_btn.click(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, *rating_outputs, *topic_outputs, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    msg.submit(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, *rating_outputs, *topic_outputs, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    next_btn.click(
        next_stage,
        [chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, *rating_outputs, *topic_outputs, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    reset_btn.click(
        reset_session,
        [lang_radio, module_state, mode_radio, session_state],
        new_session_outputs,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    lang_radio.input(
        switch_lang,
        [lang_radio, session_state, module_state, mode_radio, tts_voice],
        [
            chatbot,
            tracker,
            intro_md,
            coach_module_btn,
            coachee_module_btn,
            mode_context_md,
            msg,
            send_btn,
            next_btn,
            reset_btn,
            settings_sheet,
            settings_hint,
            lang_radio,
            mode_radio,
            tts_toggle,
            tts_voice,
            memory_strengths_md,
            memory_growth_md,
            memory_footer_md,
            memory_title_md,
            module_state,
            *rating_outputs,
            *topic_outputs,
            session_state,
        ],
        **LLM_EVENT,
    ).then(None, [lang_radio], None, js=remember_lang_js).then(None, [tts_voice, lang_radio], None, js=voice_note_js)
    tts_voice.change(None, [tts_voice, lang_radio], None, js=voice_note_js)

    coach_module_btn.click(
        select_module,
        [coach_module_value, lang_radio, mode_radio, session_state, tts_voice],
        new_session_outputs,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    coachee_module_btn.click(
        select_module,
        [coachee_module_value, lang_radio, mode_radio, session_state, tts_voice],
        new_session_outputs,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    topic_btn.click(
        start_with_topic,
        [topic_input, lang_radio, mode_radio, session_state],
        new_session_outputs,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    chatbot.like(record_feedback, [session_state], None, api_visibility="private")
    for button in rating_buttons:
        button.click(rate_session, [button, session_state], [*rating_outputs, session_state], api_visibility="private")

    demo.queue(max_size=100)


LOCAL_SECRET_FILE = ROOT / ".studio_secret"

# A failing AI service fails every request; one note a minute in the audit log is plenty for the Admin page.
AI_FAILURE_LOG_EVERY = 60
CREDIT_CHECK_EVERY = 300
_failure_log_lock = threading.Lock()
_last_failure_logged: float | None = None
_credit_lock = threading.Lock()
_credit_cache: dict = {"checked": None, "value": None}


def _record_ai_failure(exc: Exception) -> None:
    """Note a failed AI request (e.g. out of credit) in the audit log, so the Admin page can warn the owner."""
    global _last_failure_logged
    now = time.monotonic()
    with _failure_log_lock:
        if _last_failure_logged is not None and now - _last_failure_logged < AI_FAILURE_LOG_EVERY:
            return
        _last_failure_logged = now
    try:
        get_store().log(None, "ai_error", detail=coaching_core.failure_summary(exc))
    except Exception:
        logger.exception("Recording a failed AI request failed")


def _ai_credit_left() -> float | None:
    """Dollars left on the AI account (OpenRouter only), read at most every five minutes."""
    with _credit_lock:
        checked = _credit_cache["checked"]
        if checked is None or time.monotonic() - checked >= CREDIT_CHECK_EVERY:
            value = coaching_core.openrouter_credit_left(get_server_api_key(), get_server_base_url())
            _credit_cache.update(checked=time.monotonic(), value=value)
        return _credit_cache["value"]


def _secret_key(env: dict[str, str] | None = None) -> str:
    """Signs sign-in cookies. Public deployments must set STUDIO_SECRET_KEY; a local run keeps one in .studio_secret."""
    env = os.environ if env is None else env
    key = studio_env(env, "SECRET_KEY").strip()
    if key:
        return key
    if _is_public(env):
        raise SystemExit("STUDIO_SECRET_KEY is not set. Generate one (python3 -c \"import secrets; print(secrets.token_hex(32))\") and add it as a secret.")
    secret_file = local_path(LOCAL_SECRET_FILE, f".{LEGACY_NAME}_secret")
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
        secret_file.chmod(0o600)
    return secret_file.read_text(encoding="utf-8").strip()


def _bootstrap_admin(store: db.Store, env: dict[str, str]) -> None:
    """Create the first admin from STUDIO_ADMIN_EMAIL / STUDIO_ADMIN_PASSWORD when no admin exists yet."""
    email = studio_env(env, "ADMIN_EMAIL").strip()
    password = studio_env(env, "ADMIN_PASSWORD")
    if not email or not password or store.count_admins() > 0 or store.get_user_by_email(email):
        return
    if accounts.password_problem(password):
        logger.error("STUDIO_ADMIN_PASSWORD needs at least %s characters; no admin was created.", accounts.MIN_PASSWORD_LENGTH)
        return
    user_id = store.create_user(email, email.split("@")[0], accounts.hash_password(password), role="admin", consented=True)
    store.log(user_id, "account_created", target_user_id=user_id, detail="admin from STUDIO_ADMIN_EMAIL")


def create_app(store: db.Store | None = None, env: dict[str, str] | None = None) -> FastAPI:
    """The web server: account pages first, then the coaching app mounted at / behind sign-in."""
    env = os.environ if env is None else env
    if store is not None:
        set_store(store)
    store = get_store()
    secret = _secret_key(env)
    public = _is_public(env)
    _bootstrap_admin(store, env)
    if public and store.is_sqlite:
        logger.warning("DATABASE_URL is not set: accounts and sessions live in a local SQLite file that a restart may erase.")
    if public and store.count_admins() == 0:
        logger.error("No admin account exists. Set STUDIO_ADMIN_EMAIL and STUDIO_ADMIN_PASSWORD, then restart.")

    settings = account_pages.PageSettings(
        secret=secret,
        secure_cookies=public,
        allow_local_setup=not public,
        public_url=studio_env(env, "PUBLIC_URL").strip(),
        storage_warning=public and store.is_sqlite,
        mailer=mailer.smtp_sender(env),
        data_locations=studio_env(env, "DATA_LOCATIONS").strip(),
        ai_credit=_ai_credit_left,
        contact=studio_env(env, "CONTACT").strip(),
    )
    coaching_core.on_request_failure = _record_ai_failure
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(account_pages.build_router(get_store, settings, retry_review=retry_practice_review,
                                                 retry_action_card=retry_action_card))

    def signed_in_user_id(request) -> str | None:
        user = account_pages.current_user(request, get_store(), secret)
        return str(user["id"]) if user else None

    @app.middleware("http")
    async def send_visitors_to_sign_in(request, call_next):
        if request.method != "GET" or request.url.path != "/":
            return await call_next(request)
        if await run_in_threadpool(signed_in_user_id, request) is None:
            return RedirectResponse("/login", status_code=303)
        response = await call_next(request)
        if not response.headers.get("content-type", "").startswith("text/html"):
            return response
        # Gradio's own scripts must find the Space-status answer already in place (see space_status_js).
        page = b"".join([chunk async for chunk in response.body_iterator])
        page = page.replace(b"<head>", b"<head><script>" + space_status_js.encode() + b"</script>", 1)
        headers = {name: value for name, value in response.headers.items() if name != "content-length"}
        return Response(page, status_code=response.status_code, headers=headers)

    return gr.mount_gradio_app(
        app,
        demo,
        path="/",
        auth_dependency=signed_in_user_id,
        theme=clean_indigo_theme,
        css=css,
        head=head,
        favicon_path=str(ROOT / "assets" / "icons" / "studio-icon-192.png"),
        allowed_paths=[str(ROOT / "assets")],
        footer_links=["gradio", "settings"],
        # Hugging Face turns on Gradio's server-side rendering, which puts a Node server in front that only forwards
        # Gradio's own routes, hiding the account pages (/privacy, /help, /account, /admin, /healthz).
        ssr_mode=False,
    )


def _server_port(env: dict[str, str]) -> int:
    for name in ("GRADIO_SERVER_PORT", "PORT"):  # PORT is what Render, Railway and similar hosts set.
        if env.get(name):
            return int(env[name])
    for port in range(7860, 7960):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("No free port between 7860 and 7959; set GRADIO_SERVER_PORT.")


def _init_error_reporting(env: dict[str, str]) -> None:
    """Send crashes to Sentry when SENTRY_DSN is set, without request bodies or local variables (they hold transcripts)."""
    dsn = env.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk isn't installed; error reports are off.")
        return
    sentry_sdk.init(dsn=dsn, send_default_pii=False, include_local_variables=False, max_request_body_size="never",
                    traces_sample_rate=0)


def launch_demo():
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    env = os.environ
    _init_error_reporting(env)
    app = create_app(env=env)
    host = env.get("GRADIO_SERVER_NAME", "127.0.0.1").strip()
    port = _server_port(env)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"
    started = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def announce(app_):
        async with started(app_) as state:
            # mac_launcher.py and scripts/check_project.py watch for this line.
            print(f"Running on local URL:  {url}", flush=True)
            if _launch_inbrowser():
                webbrowser.open(url)
            yield state

    app.router.lifespan_context = announce
    uvicorn.run(app, host=host, port=port, proxy_headers=True, forwarded_allow_ips="*", log_level="warning")


if __name__ == "__main__":
    launch_demo()
