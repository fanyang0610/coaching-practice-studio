import contextlib
import datetime as dt
import json
import logging
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
import webbrowser
import weakref

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# Coaching conversations are private; don't send Gradio usage analytics to third parties.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr  # noqa: E402
from starlette.concurrency import run_in_threadpool

import accounts
import account_pages
from coach_agent import ACTION_CARD_FIELDS, EricksonCoachingAgent
from coaching_core import CoachingState
from coachee_agent import EricksonCoacheeAgent
import db
import mailer
from memory import UserProfile, merge_analysis
import quota
import safety
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
    tts_js,
    welcome_js,
)


ROOT = Path(__file__).resolve().parent
# Served publicly by account_pages so the header doesn't carry a 50 KB base64 image on every reply.
HEADER_ICON_SRC = "/icons/studio-icon-192.png"

logger = logging.getLogger("erickson_coach")


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
    if "ERICKSON_INBROWSER" in env:
        value = env.get("ERICKSON_INBROWSER", "1").strip().lower()
        return value in ("1", "true", "yes", "on")
    return False


default_mode = "llm"
default_lang = "zh"
default_module = "coach"
RESPOND_OUTPUT_COUNT = 10
NEXT_STAGE_OUTPUT_COUNT = 10

# Every event that can call the model shares one pool of worker slots. Calls mostly wait on
# the network, so 24 at once is comfortable for a 2-vCPU host and stays under Gradio's 40 threads.
LLM_CONCURRENCY = 24
MAX_MESSAGE_CHARS = 2000
MAX_USER_TURNS_PER_SESSION = 40
# A new AI Coach session asks about the last action card made in this window (not one from minutes ago).
FOLLOW_UP_WITHIN = dt.timedelta(days=60)
FOLLOW_UP_AFTER = dt.timedelta(hours=8)
# Sign-in is the real gate; hiding the endpoints just keeps them off the public API page.
LLM_EVENT = {"concurrency_id": "llm", "concurrency_limit": LLM_CONCURRENCY, "api_visibility": "private"}

_agent_locks: "weakref.WeakKeyDictionary[object, threading.Lock]" = weakref.WeakKeyDictionary()
_agent_locks_guard = threading.Lock()
_profile_lock = threading.Lock()
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
    return f"""
    <section class="mode-context-card">
        <div class="mode-context-label">{s["mode_context"]}</div>
        <div class="mode-context-title">{mode_title}{quota_pill}</div>
        <p>{mode_note}</p>
    </section>
    """


def _build_agent(module: str, mode: str, language: str, user_profile=None):
    if module == "coachee":
        return EricksonCoacheeAgent(mode=mode, language=language, user_profile=user_profile)
    return EricksonCoachingAgent(mode=mode, language=language, user_profile=user_profile)


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


def _chat_history_from_context(agent) -> list[dict[str, str]]:
    chat_history = []
    for msg in agent.context:
        role = "assistant" if msg["role"] == agent.assistant_role else "user"
        chat_history.append({"role": role, "content": msg["content"]})
    return chat_history

def _memory_ui_updates(agent, lang_code: str):
    s = UI[lang_code]
    p = agent.user_profile
    if not p or not p.last_updated:
        return (
            f"**{s['memory_strengths']}**\n\n{s['memory_no_data']}",
            f"**{s['memory_growth']}**\n\n- ",
            f"*{s['memory_last_sync']}: {s['memory_never']}*"
        )
    
    strengths = "\n".join([f"- {i}" for i in p.strengths]) if p.strengths else "- "
    growth = "\n".join([f"- {i}" for i in p.growth_areas]) if p.growth_areas else "- "
    
    return (
        f"**{s['memory_strengths']}**\n\n{strengths}",
        f"**{s['memory_growth']}**\n\n{growth}",
        f"*{s['memory_last_sync']}: {p.last_updated}*"
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

    for idx, state in enumerate(states):
        classes = ["tracker-dot"]
        if idx < current_idx:
            classes.append("done")
        elif idx == current_idx:
            classes.append("active")
        dots.append(
            f"<div class='{' '.join(classes)}'><span>{idx + 1}</span></div>"
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


def _save(session: dict) -> None:
    agent = session["agent"]
    get_store().save_session(
        session["id"],
        state=agent.to_dict(),
        status="completed" if agent.is_session_ended() else "active",
        stage=agent.current_state.name,
        user_turns=_user_turns(agent),
        language=agent.language,
        mode=agent.mode,
    )


def _allowed_mode(user: dict, mode_code: str, lang_code: str, module_code: str) -> str:
    """AI mode only while today's allowance for this module lasts; otherwise template mode, with a notice."""
    if mode_code != "llm":
        return mode_code
    allowance = quota.allowance(get_store(), user, module_code)
    if allowance.blocked_reason is None:
        return "llm"
    gr.Warning(UI[lang_code][f"quota_{allowance.blocked_reason}"].format(hours=allowance.hours_until_available()))
    return "template"


def _request_language(request: gr.Request | None, fallback: str | None) -> str | None:
    """The language this person last chose (shared with the account pages), else their browser's."""
    try:
        cookies, headers = request.cookies, request.headers
    except AttributeError:
        return fallback
    return account_pages.preferred_language(cookies, headers, fallback)


def _open_session(user: dict, module_code: str, mode_code: str, lang_code: str) -> dict:
    mode_code = _allowed_mode(user, mode_code, lang_code, module_code)
    agent = _build_agent(module_code, mode_code, lang_code, _load_profile(user["id"], module_code))
    if module_code == "coach" and mode_code == "llm":
        now = db.utcnow()
        agent.last_card = get_store().latest_card(user["id"], since=now - FOLLOW_UP_WITHIN, until=now - FOLLOW_UP_AFTER)
    session_id = get_store().create_session(user["id"], module_code, lang_code, mode_code, agent.current_state.name, agent.to_dict())
    session = _attach({"module": module_code, "agent": agent, "id": session_id}, user)
    _append_opening_prompt(agent)
    _save(session)
    return session


def _restore_session(row: dict, user: dict) -> dict | None:
    """Reopen a stored session; one that can no longer be read is set aside so the person can start fresh."""
    agent_class = EricksonCoacheeAgent if row["module"] == "coachee" else EricksonCoachingAgent
    try:
        agent = agent_class.from_dict(json.loads(row["state"]), user_profile=_load_profile(user["id"], row["module"]))
    except Exception:
        logger.exception("Stored session %s could not be reopened", row["id"])
        get_store().set_session_status(row["id"], "abandoned")
        return None
    return _attach({"module": row["module"], "agent": agent, "id": row["id"]}, user)


def _leave_session(session: dict | None) -> None:
    if session and session.get("id") and not session["agent"].is_session_ended():
        get_store().set_session_status(session["id"], "abandoned")


def _ensure_session(session: dict | None, user: dict, module_sel: str, mode_sel: str, lang_sel: str,
                    set_language: bool = True):
    """The person's current session, reopened or started as needed.

    set_language=False leaves an existing conversation in its own language, so switch_lang can translate it first.
    """
    module_code = _safe_module(module_sel)
    mode_code = _safe_mode(mode_sel)
    lang_code = _safe_lang(lang_sel)

    if not session or session.get("user_id") != user["id"] or not session.get("id"):
        row = get_store().latest_active_session(user["id"])
        session = _restore_session(row, user) if row else None
    if not session or session.get("module") != module_code:
        _leave_session(session)
        return _open_session(user, module_code, mode_code, lang_code)

    agent = session["agent"]
    if set_language:
        agent.set_language(lang_code)
    # A session keeps the mode it opened with: AI, or templates once today's allowance was used up.
    return session


def _append_opening_prompt(agent):
    api_key = _safe_key()
    if agent.mode == "llm" and not api_key:
        prompt = _llm_config_message(agent.language)
    else:
        try:
            prompt = agent.get_stage_prompt(api_key=api_key or None)
        except Exception:
            if agent.mode != "llm":
                raise
            logger.exception("Opening prompt failed")
            prompt = UI[agent.language]["ai_opening_error"]
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
        chat=_chat_history_from_context(agent),
        tracker=_tracker_html(agent, session["module"]),
        header=_header_markdown(session),
        coach_btn=coach_btn,
        coachee_btn=coachee_btn,
        mode_context=_mode_context_html(session),
        msg=gr.update(placeholder=copy["placeholder"], interactive=not agent.is_session_ended(), value=""),
        tts=gr.update(value=_tts_payload(agent.context[-1]["content"]) if agent.context else ""),
        memory=(m_s, m_g, m_f),
        module=gr.update(value=session["module"]),
        lang=gr.update(value=_lang_selector(lc)),
        # The hidden mode setting stays on the default; the daily allowance alone decides when a session uses templates.
        mode=gr.update(choices=_mode_choices(lc), value=_mode_label(default_mode, lc)),
    )


def initial_load(session: dict, module_sel: str, mode_sel: str, lang_sel: str, request: gr.Request = None):
    """Reopen the person's unfinished session if there is one, otherwise start a new one."""
    user = _require_user(request, _safe_lang(lang_sel))
    preferred = _request_language(request, None)
    first_visit = not get_store().list_sessions(user["id"], limit=1)
    if not session or session.get("user_id") != user["id"] or not session.get("id"):
        row = get_store().latest_active_session(user["id"])
        session = _restore_session(row, user) if row else None
        if session is None:
            session = _open_session(user, _safe_module(module_sel), _safe_mode(mode_sel), preferred or _safe_lang(lang_sel))
    agent = session["agent"]
    if preferred and preferred != agent.language:
        # A reopened session follows the language the person uses now.
        with _agent_lock(agent):
            agent.translate_history(new_lang=preferred, api_key=_safe_key() or None)
            agent.set_language(preferred)
            _save(session)
    out = _session_start_outputs(session)
    welcome = _welcome_html(agent.language) if first_visit else ""
    return (
        out["chat"], out["tracker"], out["header"], out["coach_btn"], out["coachee_btn"], out["mode_context"],
        out["msg"], out["tts"], *out["memory"], out["module"], out["lang"], out["mode"],
        _memory_title(agent.language), welcome, session,
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
        session,
    )


def _next_stage_outputs(message_update, chat_history, agent, session, tts_update=None, memory_updates=None):
    return _respond_outputs(message_update, chat_history, agent, session, tts_update, memory_updates)


def _streaming_outputs(chat_history, session):
    """Mid-reply update: only the transcript changes, so the other panels are left untouched."""
    return (gr.update(value=""), chat_history) + (gr.update(),) * (RESPOND_OUTPUT_COUNT - 3) + (session,)


def _learn_from_session(session: dict, api_key: str):
    """Fold a finished session into the person's profile. Runs off the request thread so the final reply isn't delayed."""
    agent = session["agent"]
    try:
        analysis = agent.analyze_session_for_memory(api_key)
        if not analysis:
            return
        store = get_store()
        with _profile_lock:
            profile = merge_analysis(_load_profile(session["user_id"], session["module"]), analysis)
            store.save_profile(session["user_id"], session["module"], profile.to_dict())
        agent.user_profile = profile
    except Exception:
        logger.exception("Updating the user profile from a finished session failed")


def _review_score(review: str) -> int | None:
    """The score in a practice review, written as "N/100"."""
    match = re.search(r"(\d{1,3})\s*/\s*100", review or "")
    return min(int(match.group(1)), 100) if match else None


def _action_card_text(card: dict, lang_code: str) -> str:
    s = UI[lang_code]
    sep = "：" if lang_code == "zh" else ": "
    fields = [f"{s['card_' + key]}{sep}{card[key]}" for key in ACTION_CARD_FIELDS if card.get(key)]
    return "\n".join([s["card_title"], "", *fields, "", s["card_saved"]])


def _makes_action_card(session: dict, api_key: str) -> bool:
    return session["module"] == "coach" and session["agent"].mode == "llm" and bool(api_key)


def _finish_session(session: dict, api_key: str) -> str | None:
    """Keep what a finished session produced, then learn from it in the background.

    An AI Coach session gets an action card: shown in the chat, listed on the Account page, and followed up on in the
    next session. A practice session's score is read from its review. Returns the card's text when one was made.
    """
    agent = session["agent"]
    card_text = None
    try:
        if session["module"] == "coachee":
            score = _review_score(agent.context[-1]["content"]) if agent.context else None
            if score is not None:
                get_store().save_session_result(session["id"], session["user_id"], "coachee", score=score)
        elif _makes_action_card(session, api_key):
            card = agent.action_card(api_key)
            if card:
                get_store().save_session_result(session["id"], session["user_id"], "coach", card=card)
                card_text = _action_card_text(card, agent.language)
                agent.context.append({"role": agent.assistant_role, "content": card_text})
                _save(session)
    except Exception:
        logger.exception("Keeping the result of a finished session failed")
    if agent.mode == "llm" and api_key:
        threading.Thread(target=_learn_from_session, args=(session, api_key), daemon=True).start()
    return card_text


def respond(message, chat_history, session, module_sel, mode_sel, lang_sel, request: gr.Request = None):
    user = _require_user(request, _safe_lang(lang_sel))
    session = _ensure_session(session, user, module_sel, mode_sel, lang_sel)
    agent = session["agent"]
    s = UI[agent.language]
    user_msg = (message or "").strip()

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

    if _user_turns(agent) >= MAX_USER_TURNS_PER_SESSION:
        gr.Warning(s["turn_limit"])
        yield _respond_outputs(gr.update(value="", interactive=False), chat_history, agent, session)
        return

    if not _message_limiter.allow(user["id"]):
        gr.Warning(s["rate_limited"])
        yield _respond_outputs(gr.update(), chat_history, agent, session)
        return

    lock = _agent_lock(agent)
    if not lock.acquire(blocking=False):
        gr.Warning(s["busy_warning"])
        yield _respond_outputs(gr.update(), chat_history, agent, session)
        return
    try:
        yield from _stream_reply(user_msg, chat_history, agent, session)
    finally:
        lock.release()


def _stream_reply(user_msg, chat_history, agent, session):
    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": user_msg})
    yield _streaming_outputs(list(chat_history), session)
    old_state = agent.current_state

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
        except Exception:
            logger.exception("Model reply failed")
            _save(session)
            gr.Warning(UI[agent.language]["ai_reply_error"])
            chat_history.pop()
            yield _respond_outputs(gr.update(value=user_msg), chat_history, agent, session)
            return

    if agent.current_state != old_state:
        stage_name = STAGE_NAMES[agent.language].get(agent.current_state, "")
        msg = f"进入下一阶段：{stage_name}" if agent.language == "zh" else f"Advanced to next stage: {stage_name}"
        gr.Info(msg)

    chat_history.append({"role": "assistant", "content": coach_response})
    _save(session)

    tts_update = gr.update(value=_tts_payload(coach_response))
    is_ended = agent.is_session_ended()
    if is_ended:
        msg = "会话已结束" if agent.language == "zh" else "Session Complete"
        gr.Info(msg)
        session["allowance"] = quota.allowance(get_store(), get_store().get_user(session["user_id"]), session["module"])
        if _makes_action_card(session, api_key):
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
    lock = _agent_lock(agent)
    if not lock.acquire(blocking=False):
        gr.Warning(UI[agent.language]["busy_warning"])
        return _next_stage_outputs(gr.update(), chat_history, agent, session)
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

    if hasattr(agent, "manual_advance_guard"):
        blocker = agent.manual_advance_guard()
        if blocker:
            gr.Warning(blocker)
            return _next_stage_outputs(gr.update(), chat_history, agent, session)

    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    if not agent.force_next_state():
        gr.Info(s["session_ended"])
        return _next_stage_outputs(gr.update(value="", interactive=False), chat_history, agent, session, memory_updates=(m_s, m_g, m_f))

    try:
        new_prompt = _append_opening_prompt(agent)
    except Exception:
        logger.exception("Next-stage prompt failed")
        agent.current_state = old_state
        agent.current_sub_phase = old_sub
        agent.turns_in_current_stage = old_turns
        gr.Warning(s["ai_reply_error"])
        return _next_stage_outputs(gr.update(), chat_history, agent, session)

    chat_history = list(chat_history or [])
    chat_history.append({"role": "assistant", "content": new_prompt})
    _save(session)

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


def reset_session(lang_sel, module_sel, mode_sel, session=None, request: gr.Request = None):
    lc = _safe_lang(lang_sel)
    user = _require_user(request, lc)
    if session and session.get("user_id") == user["id"]:
        _leave_session(session)
    session = _open_session(user, _safe_module(module_sel), _safe_mode(mode_sel), lc)
    out = _session_start_outputs(session)
    return (
        out["chat"], out["tracker"], out["tts"], out["header"], out["coach_btn"], out["coachee_btn"], out["mode_context"],
        out["msg"], *out["memory"], out["module"], out["mode"], session,
    )


def switch_lang(new_lang, session, module_sel, mode_sel, request: gr.Request = None):
    lc = _safe_lang(new_lang)
    user = _require_user(request, lc)
    # Keep the conversation in its old language until it has been translated; setting the new language first made
    # translate_history think there was nothing to do, so the opening question stayed in the old language.
    session = _ensure_session(session, user, module_sel, mode_sel, new_lang, set_language=False)
    agent = session["agent"]
    with _agent_lock(agent):
        agent.translate_history(new_lang=lc, api_key=_safe_key() or None)
        agent.set_language(lc)
        _save(session)
    s = UI[lc]
    copy = _session_ui(agent, session["module"])
    coach_btn, coachee_btn = _module_button_updates(session["module"], lc)

    m_s, m_g, m_f = _memory_ui_updates(agent, lc)
    return (
        _chat_history_from_context(agent),
        _tracker_html(agent, session["module"]),
        _header_markdown(session),
        coach_btn,
        coachee_btn,
        _mode_context_html(session),
        gr.update(placeholder=copy["placeholder"], interactive=not agent.is_session_ended()),
        gr.update(value=s["send"]),
        gr.update(value=s["advance"]),
        gr.update(value=s["reset"]),
        gr.update(label=s["settings"], open=False),
        gr.update(value=s["mode_hint"]),
        gr.update(label=s["language"], value=new_lang),
        gr.update(label=s["mode"], choices=_mode_choices(lc), value=_mode_label(default_mode, lc)),
        gr.update(label=s["tts_enable"]),
        gr.update(label=s["tts_voice"], choices=[s["voice_f"], s["voice_m"]]),
        m_s, m_g, m_f,
        _memory_title(lc),
        gr.update(value=session["module"]),
        session,
    )


def select_module(module_code: str, lang_sel: str, mode_sel: str, session=None, request: gr.Request = None):
    return reset_session(lang_sel, module_code, mode_sel, session, request)


def record_feedback(session, feedback: gr.LikeData, request: gr.Request = None):
    """Thumbs up/down on a reply, saved against the message's position in the transcript."""
    user = _current_user(request)
    if not user or not session or session.get("user_id") != user["id"] or not isinstance(feedback.index, int):
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

    demo.load(
        initial_load,
        [session_state, module_state, mode_radio, lang_radio],
        [chatbot, tracker, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, tts_text, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, lang_radio, mode_radio, memory_title_md, welcome_html, session_state],
        js=force_light_js,
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js)

    send_btn.click(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    msg.submit(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    next_btn.click(
        next_stage,
        [chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    reset_btn.click(
        reset_session,
        [lang_radio, module_state, mode_radio, session_state],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, mode_radio, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    lang_radio.change(
        switch_lang,
        [lang_radio, session_state, module_state, mode_radio],
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
            session_state,
        ],
        **LLM_EVENT,
    ).then(None, [lang_radio], None, js=remember_lang_js)

    coach_module_btn.click(
        select_module,
        [coach_module_value, lang_radio, mode_radio, session_state],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, mode_radio, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    coachee_module_btn.click(
        select_module,
        [coachee_module_value, lang_radio, mode_radio, session_state],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, mode_radio, session_state],
        **LLM_EVENT,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    chatbot.like(record_feedback, [session_state], None, api_visibility="private")

    demo.queue(max_size=100)


LOCAL_SECRET_FILE = ROOT / ".erickson_secret"


def _secret_key(env: dict[str, str] | None = None) -> str:
    """Signs sign-in cookies. Public deployments must set ERICKSON_SECRET_KEY; a local run keeps one in .erickson_secret."""
    env = os.environ if env is None else env
    key = env.get("ERICKSON_SECRET_KEY", "").strip()
    if key:
        return key
    if _is_public(env):
        raise SystemExit("ERICKSON_SECRET_KEY is not set. Generate one (python3 -c \"import secrets; print(secrets.token_hex(32))\") and add it as a secret.")
    if not LOCAL_SECRET_FILE.exists():
        LOCAL_SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        LOCAL_SECRET_FILE.chmod(0o600)
    return LOCAL_SECRET_FILE.read_text(encoding="utf-8").strip()


def _bootstrap_admin(store: db.Store, env: dict[str, str]) -> None:
    """Create the first admin from ERICKSON_ADMIN_EMAIL / ERICKSON_ADMIN_PASSWORD when no admin exists yet."""
    email = env.get("ERICKSON_ADMIN_EMAIL", "").strip()
    password = env.get("ERICKSON_ADMIN_PASSWORD", "")
    if not email or not password or store.count_admins() > 0 or store.get_user_by_email(email):
        return
    if accounts.password_problem(password):
        logger.error("ERICKSON_ADMIN_PASSWORD needs at least %s characters; no admin was created.", accounts.MIN_PASSWORD_LENGTH)
        return
    user_id = store.create_user(email, email.split("@")[0], accounts.hash_password(password), role="admin", consented=True)
    store.log(user_id, "account_created", target_user_id=user_id, detail="admin from ERICKSON_ADMIN_EMAIL")


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
        logger.error("No admin account exists. Set ERICKSON_ADMIN_EMAIL and ERICKSON_ADMIN_PASSWORD, then restart.")

    settings = account_pages.PageSettings(
        secret=secret,
        secure_cookies=public,
        allow_local_setup=not public,
        public_url=env.get("ERICKSON_PUBLIC_URL", "").strip(),
        storage_warning=public and store.is_sqlite,
        mailer=mailer.smtp_sender(env),
        data_locations=env.get("ERICKSON_DATA_LOCATIONS", "").strip(),
    )
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(account_pages.build_router(get_store, settings))

    def signed_in_user_id(request) -> str | None:
        user = account_pages.current_user(request, get_store(), secret)
        return str(user["id"]) if user else None

    @app.middleware("http")
    async def send_visitors_to_sign_in(request, call_next):
        if request.method == "GET" and request.url.path == "/" and await run_in_threadpool(signed_in_user_id, request) is None:
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

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
