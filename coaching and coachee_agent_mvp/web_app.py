import base64
import os
from pathlib import Path
import time

import gradio as gr

from coach_agent import EricksonCoachingAgent
from coaching_core import CoachingState
from coachee_agent import EricksonCoacheeAgent
from memory import MemoryManager
from web_assets import (
    MODE_OPTIONS,
    STAGE_NAMES,
    UI,
    css,
    force_light_js,
    global_viewport_style,
    head,
    scroll_js,
    tts_js,
)


ROOT = Path(__file__).resolve().parent
HEADER_ICON_PATH = ROOT / "assets" / "icons" / "erickson-icon-192.png"
HEADER_ICON_SRC = f"data:image/png;base64,{base64.b64encode(HEADER_ICON_PATH.read_bytes()).decode('ascii')}"


def _load_dotenv():
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def get_server_api_key() -> str:
    _load_dotenv()
    return os.environ.get("OPENAI_API_KEY", "").strip()


def get_server_base_url() -> str | None:
    _load_dotenv()
    return os.environ.get("OPENAI_BASE_URL", "").strip() or None


def get_server_model() -> str:
    _load_dotenv()
    return os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"


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
    return f"""
    <section class="mode-context-card">
        <div class="mode-context-label">{s["mode_context"]}</div>
        <div class="mode-context-title">{mode_title}</div>
        <p>{mode_note}</p>
    </section>
    """


def _build_agent(module: str, mode: str, language: str, user_profile=None):
    if module == "coachee":
        return EricksonCoacheeAgent(mode=mode, language=language, user_profile=user_profile)
    return EricksonCoachingAgent(mode=mode, language=language, user_profile=user_profile)


def _new_session(module: str = default_module, mode: str = default_mode, language: str = default_lang, user_profile=None) -> dict:
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

def _profile_local_path() -> str | None:
    if os.environ.get("SPACE_ID") or os.environ.get("SPACE_HOST"):
        return None
    return "user_profile.json"


def _get_memory():
    return MemoryManager(api_key=_safe_key(), local_path=_profile_local_path())


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
            f"*{s['memory_last_sync']}: Never*"
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
            <div class="tracker-next">{s["up_next"]}: {next_name}</div>
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


def _ensure_session(session: dict | None, module_sel: str, mode_sel: str, lang_sel: str):
    module_code = _safe_module(module_sel)
    mode_code = _safe_mode(mode_sel)
    lang_code = _safe_lang(lang_sel)

    if not session or session.get("module") != module_code:
        memory = _get_memory()
        return _new_session(module=module_code, mode=mode_code, language=lang_code, user_profile=memory.profile)

    agent = session["agent"]
    agent.set_language(lang_code)
    agent.set_mode(mode_code)
    
    # Update profile if not present
    if not hasattr(agent, "user_profile") or not agent.user_profile:
        memory = _get_memory()
        agent.user_profile = memory.profile
    
    session["module"] = module_code
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
            prompt = UI[agent.language]["ai_opening_error"]
    agent.context.append({"role": agent.assistant_role, "content": prompt})
    return prompt


def initial_load(session: dict, module_sel: str, mode_sel: str, lang_sel: str):
    session = _ensure_session(session, module_sel, mode_sel, lang_sel)
    agent = session["agent"]
    lc = agent.language

    if not agent.context:
        _append_opening_prompt(agent)

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
        gr.update(placeholder=copy["placeholder"]),
        gr.update(value=_tts_payload(agent.context[-1]["content"])),
        m_s, m_g, m_f,
        session,
    )


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


def respond(message, chat_history, session, module_sel, mode_sel, lang_sel):
    session = _ensure_session(session, module_sel, mode_sel, lang_sel)
    agent = session["agent"]
    s = UI[agent.language]
    user_msg = (message or "").strip()

    if not user_msg:
        gr.Warning(s["empty_warning"])
        return _respond_outputs(gr.update(), chat_history, agent, session)

    if agent.is_session_ended():
        gr.Info(s["session_ended"])
        return _respond_outputs(gr.update(value="", interactive=False), chat_history, agent, session)

    chat_history = list(chat_history or [])
    chat_history.append({"role": "user", "content": user_msg})
    old_state = agent.current_state

    api_key = _safe_key()
    if agent.mode == "llm" and not api_key:
        coach_response = _llm_config_message(agent.language)
        agent.context.append({"role": agent.user_role, "content": user_msg})
        agent.context.append({"role": agent.assistant_role, "content": coach_response})
    else:
        try:
            coach_response = agent.generate_response(user_msg, api_key=api_key or None)
        except Exception as exc:
            gr.Warning(str(exc))
            chat_history.pop()
            return _respond_outputs(gr.update(), chat_history, agent, session)

    if agent.current_state != old_state:
        stage_name = STAGE_NAMES[agent.language].get(agent.current_state, "")
        msg = f"进入下一阶段：{stage_name}" if agent.language == "zh" else f"Advanced to next stage: {stage_name}"
        gr.Info(msg)

    chat_history.append({"role": "assistant", "content": coach_response})

    is_ended = agent.is_session_ended()
    if is_ended:
        msg = "会话已结束" if agent.language == "zh" else "Session Complete"
        gr.Info(msg)
        
        # TRIGGER LEARNING
        if agent.mode == "llm" and api_key:
            try:
                analysis = agent.analyze_session_for_memory(api_key)
                if analysis:
                    memory = _get_memory()
                    memory.update_from_analysis(analysis)
                    agent.user_profile = memory.profile
                    gr.Info("AI has updated your personality profile based on this session." if agent.language == "en" else "AI 已根据本次会话更新了你的个性化画像。")
            except Exception:
                pass

    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    return _respond_outputs(
        gr.update(value="", interactive=not is_ended),
        chat_history,
        agent,
        session,
        gr.update(value=_tts_payload(coach_response)),
        (m_s, m_g, m_f),
    )


def next_stage(chat_history, session, module_sel, mode_sel, lang_sel):
    session = _ensure_session(session, module_sel, mode_sel, lang_sel)
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
    except Exception as exc:
        agent.current_state = old_state
        agent.current_sub_phase = old_sub
        agent.turns_in_current_stage = old_turns
        gr.Warning(str(exc))
        return _next_stage_outputs(gr.update(), chat_history, agent, session)

    chat_history = list(chat_history or [])
    chat_history.append({"role": "assistant", "content": new_prompt})

    is_ended = agent.is_session_ended()
    if is_ended:
        msg = "会话已结束" if agent.language == "zh" else "Session Complete"
        gr.Info(msg)
        
    m_s, m_g, m_f = _memory_ui_updates(agent, agent.language)
    return _next_stage_outputs(
        gr.update(value="", interactive=not is_ended),
        chat_history,
        agent,
        session,
        gr.update(value=_tts_payload(new_prompt)),
        (m_s, m_g, m_f),
    )


def reset_session(lang_sel, module_sel, mode_sel):
    lc = _safe_lang(lang_sel)
    module_code = _safe_module(module_sel)
    memory = _get_memory()
    session = _new_session(module=module_code, mode=_safe_mode(mode_sel), language=lc, user_profile=memory.profile)
    agent = session["agent"]
    prompt = _append_opening_prompt(agent)
    copy = _session_ui(agent, module_code)
    coach_btn, coachee_btn = _module_button_updates(module_code, lc)

    m_s, m_g, m_f = _memory_ui_updates(agent, lc)
    return (
        [{"role": "assistant", "content": prompt}],
        _tracker_html(agent, module_code),
        gr.update(value=_tts_payload(prompt)),
        _header_markdown(session),
        coach_btn,
        coachee_btn,
        _mode_context_html(session),
        gr.update(placeholder=copy["placeholder"], interactive=True, value=""),
        m_s, m_g, m_f,
        gr.update(value=module_code),
        session,
    )


def switch_lang(new_lang, session, module_sel, mode_sel):
    module_code = _safe_module(module_sel)
    mode_code = _safe_mode(mode_sel)
    lc = _safe_lang(new_lang)

    if not session or session.get("module") != module_code:
        session = _new_session(module=module_code, mode=mode_code, language=lc)

    session = _ensure_session(session, module_sel, mode_sel, new_lang)
    agent = session["agent"]
    agent.translate_history(new_lang=lc, api_key=_safe_key() or None)
    agent.set_language(lc)
    agent.set_mode(mode_code)
    session["module"] = module_code
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
        gr.update(label=s["mode"], choices=_mode_choices(lc), value=_mode_label(agent.mode, lc)),
        gr.update(label=s["tts_enable"]),
        gr.update(label=s["tts_voice"], choices=[s["voice_f"], s["voice_m"]]),
        m_s, m_g, m_f,
        gr.update(value=session["module"]),
        session,
    )


def select_module(module_code: str, lang_sel: str, mode_sel: str):
    return reset_session(lang_sel, module_code, mode_sel)


clean_indigo_theme = gr.themes.Default(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.sky,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Noto Sans SC"), gr.themes.GoogleFont("Manrope"), "sans-serif"],
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
    title="Erickson Coach",
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
            settings_hint = gr.Markdown(UI["zh"]["mode_hint"], elem_classes="settings-hint")
            with gr.Row(elem_classes="settings-controls"):
                lang_radio = gr.Radio(["English", "中文"], label=UI["zh"]["language"], value="中文", scale=1, min_width=0)
                mode_radio = gr.Radio(
                    _mode_choices("zh"),
                    label=UI["zh"]["mode"],
                    value=_mode_label(default_mode, "zh"),
                    scale=1,
                    min_width=0,
                )
                tts_voice = gr.Radio([UI["zh"]["voice_f"], UI["zh"]["voice_m"]], label=UI["zh"]["tts_voice"], value=UI["zh"]["voice_f"], scale=1, min_width=0)
                tts_toggle = gr.Checkbox(label=UI["zh"]["tts_enable"], value=True, scale=1, min_width=0)
            
            # AI Insights Dashboard
            gr.Markdown("---")
            with gr.Column(elem_classes="memory-dashboard"):
                memory_title_md = gr.Markdown(f"### {UI['zh']['memory_title']}")
                with gr.Row():
                    memory_strengths_md = gr.Markdown(f"**{UI['zh']['memory_strengths']}**\n\n- (Pending)")
                    memory_growth_md = gr.Markdown(f"**{UI['zh']['memory_growth']}**\n\n- (Pending)")
                memory_footer_md = gr.Markdown(f"*{UI['zh']['memory_last_sync']}: Never*")

        tracker = gr.HTML()

        with gr.Column(elem_id="chat-stage", min_width=0):
            chatbot = gr.Chatbot(show_label=False, elem_classes="chatbot", buttons=[], feedback_options=None, min_width=0)

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

    demo.load(
        initial_load,
        [session_state, module_state, mode_radio, lang_radio],
        [chatbot, tracker, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, tts_text, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
        js=force_light_js,
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js)

    send_btn.click(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    msg.submit(
        respond,
        [msg, chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    next_btn.click(
        next_stage,
        [chatbot, session_state, module_state, mode_radio, lang_radio],
        [msg, chatbot, tracker, tts_text, intro_md, mode_context_md, memory_strengths_md, memory_growth_md, memory_footer_md, session_state],
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    reset_btn.click(
        reset_session,
        [lang_radio, module_state, mode_radio],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, session_state],
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
            module_state,
            session_state,
        ],
    )

    coach_module_btn.click(
        select_module,
        [coach_module_value, lang_radio, mode_radio],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, session_state],
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)

    coachee_module_btn.click(
        select_module,
        [coachee_module_value, lang_radio, mode_radio],
        [chatbot, tracker, tts_text, intro_md, coach_module_btn, coachee_module_btn, mode_context_md, msg, memory_strengths_md, memory_growth_md, memory_footer_md, module_state, session_state],
    ).then(None, [tts_text, tts_toggle, tts_voice, lang_radio], None, js=tts_js).then(None, None, None, js=scroll_js)


def launch_demo():
    return demo.launch(
        theme=clean_indigo_theme,
        css=css,
        head=head,
        inbrowser=_launch_inbrowser(),
        favicon_path="assets/icons/erickson-icon-192.png",
        allowed_paths=["assets", "site.webmanifest"],
    )


if __name__ == "__main__":
    launch_demo()
