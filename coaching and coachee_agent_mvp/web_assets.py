from coaching_core import CoachingState

STAGE_NAMES = {
    "en": {
        CoachingState.CONTRACT: "Contract",
        CoachingState.EXPERIENCE: "Reality",
        CoachingState.ACTION: "Possibilities",
        CoachingState.VALUE: "Commitment",
        CoachingState.CLOSING: "Closing",
    },
    "zh": {
        CoachingState.CONTRACT: "目标合同",
        CoachingState.EXPERIENCE: "现实探索",
        CoachingState.ACTION: "可能方案",
        CoachingState.VALUE: "行动承诺",
        CoachingState.CLOSING: "结束回顾",
    },
}


UI = {
    "en": {
        "placeholder": "Type what is on your mind...",
        "coach_placeholder": "Type what is on your mind...",
        "coachee_placeholder": "Ask your next coaching question as the coach...",
        "send": "Send",
        "advance": "Skip Ahead",
        "reset": "New Session",
        "empty_warning": "Please type a message first.",
        "session_ended": "Session complete. Start a new session to continue.",
        "coach_name": "Coaching Practice Studio",
        "coach_sub": "Solution-focused coaching companion",
        "progress": "Session Progress",
        "current_stage": "Current stage",
        "up_next": "Up next",
        "settings": "Settings",
        "close_settings": "Close",
        "language": "Language",
        "mode": "Mode",
        "tts_enable": "Auto-play replies",
        "tts_voice": "Voice style",
        "voice_f": "Female",
        "voice_m": "Male",
        "mode_hint": "AI is the default. Template is available as a backup.",
        "server_config_error": "AI mode is waiting for server configuration. Ask the app owner to set OPENAI_API_KEY on the hosted server.",
        "ai_opening_error": "AI did not return a valid opening. Check the server model configuration, then start a new session.",
        "ai_reply_error": "The AI didn't respond this time. Please try again in a moment.",
        "message_too_long": "Please keep each message under {limit} characters.",
        "turn_limit": "This session has reached its message limit. Start a new session to continue.",
        "busy_warning": "Still working on the last reply. One moment, please.",
        "rate_limited": "You're sending messages quickly. Please wait a moment before the next one.",
        "signed_out": "Your sign-in has expired. Please reload the page and sign in again.",
        "quota_sessions": "You've used today's AI sessions in this module. This session runs in template practice mode; AI is available again in about {hours} h.",
        "quota_starts": "You've started many AI sessions in this module today. This one runs in template practice mode; AI is available again in about {hours} h.",
        "quota_tokens": "You've reached today's AI usage limit. This session runs in template practice mode; AI is available again in about {hours} h.",
        "quota_pill": "AI today {left}/{limit}",
        "account_link": "Account",
        "module": "Module",
        "coach_module": "AI Coach",
        "coachee_module": "AI Coachee Lab",
        "coach_module_card": "Be coached\nby the AI",
        "coachee_module_card": "Practise coaching\nwith an AI client",
        "coach_title": "Coaching Practice Studio",
        "coach_sub": "Solution-focused coaching companion",
        "coachee_title": "AI Coachee Lab",
        "coachee_sub": "The AI plays the coachee. You coach, and the app scores how well you led the five coaching stages.",
        "hero_eyebrow": "Transformation Studio",
        "hero_title": "Turn reflection into your next clear step.",
        "hero_sub": "A structured coaching space for clarity, choice, and committed action.",
        "mode_context": "Current mode",
        "coach_module_note": "The AI coaches you on something real in your life.",
        "coachee_module_note": "The AI plays a client. You coach, then get a score.",
        "memory_title": "AI Insights (Your Profile)",
        "memory_strengths": "Your Strengths",
        "memory_growth": "Areas for Challenge",
        "memory_last_sync": "Last Sync",
        "memory_never": "Never",
        "memory_no_data": "Complete a session in AI mode to unlock insights.",
        "help_link": "Help",
        "welcome_title": "Welcome to Coaching Practice Studio",
        "welcome_coach": "<b>Be coached</b>: the AI coaches you on something real, such as a goal, a decision or a challenge. Only you can see these sessions.",
        "welcome_coachee": "<b>Practise coaching</b>: the AI plays a client and you ask the questions. At the end you get a score and feedback.",
        "welcome_session": "Switch between the two at the top of the screen. A session takes 15 to 20 minutes and moves through five stages. If you leave, it waits for you next time.",
        "welcome_start": "Start",
        "welcome_guide": "Read the full guide",
        "card_title": "Your action card",
        "card_goal": "Goal",
        "card_next_step": "Next step",
        "card_by_when": "By when",
        "card_support": "Support",
        "card_saved": "Saved on your Account page.",
    },
    "zh": {
        "placeholder": "把你现在最想理清的事写下来...",
        "coach_placeholder": "把你现在最想理清的事写下来...",
        "coachee_placeholder": "请以教练身份输入你的下一个提问...",
        "send": "发送",
        "advance": "跳到下一阶段",
        "reset": "新会话",
        "empty_warning": "请先输入内容。",
        "session_ended": "本次会话已结束，请开启新会话。",
        "coach_name": "教练练习室",
        "coach_sub": "聚焦解决的教练式对话空间",
        "progress": "会话进度",
        "current_stage": "当前阶段",
        "up_next": "下一阶段",
        "settings": "设置",
        "close_settings": "收起",
        "language": "语言",
        "mode": "模式",
        "tts_enable": "自动朗读回复",
        "tts_voice": "声音偏好",
        "voice_f": "女声",
        "voice_m": "男声",
        "mode_hint": "默认使用 AI。模板模式仅作为备用。",
        "server_config_error": "AI 模式正在等待服务器配置。请让应用管理员在托管服务器上设置 OPENAI_API_KEY。",
        "ai_opening_error": "AI 没有返回有效开场。请检查服务器模型配置后开启新会话。",
        "ai_reply_error": "AI 这次没有回应，请稍后再试。",
        "message_too_long": "每条消息请控制在 {limit} 字以内。",
        "turn_limit": "本次会话已达到消息上限，请开启新会话继续。",
        "busy_warning": "上一条回复还在生成中，请稍候。",
        "rate_limited": "消息发送得有点快，请稍等片刻再发下一条。",
        "signed_out": "登录已过期，请刷新页面并重新登录。",
        "quota_sessions": "你今天在此模块的 AI 会话已用完。本次会话使用模板练习模式，约 {hours} 小时后可再次使用 AI。",
        "quota_starts": "你今天在此模块开启了较多 AI 会话。本次会话使用模板练习模式，约 {hours} 小时后可再次使用 AI。",
        "quota_tokens": "你已达到今天的 AI 用量上限。本次会话使用模板练习模式，约 {hours} 小时后可再次使用 AI。",
        "quota_pill": "今日AI {left}/{limit}",
        "account_link": "账户",
        "module": "模块",
        "coach_module": "AI教练",
        "coachee_module": "AI学员陪练",
        "coach_module_card": "被教练\nAI 为你做教练",
        "coachee_module_card": "练习做教练\nAI 扮演来访者",
        "coach_title": "教练练习室",
        "coach_sub": "聚焦解决的教练式对话空间",
        "coachee_title": "AI 学员陪练",
        "coachee_sub": "AI 扮演被教练者，由你来做教练。结束后系统会按五个教练阶段的完成度给你评分和反馈。",
        "hero_eyebrow": "Transformation Studio",
        "hero_title": "把困惑变成下一步。",
        "hero_sub": "专业、可信，也让成长更可感。",
        "mode_context": "当前模式",
        "coach_module_note": "AI 就你生活中的真实话题为你做教练。",
        "coachee_module_note": "AI 扮演来访者，你来提问，结束后获得评分和反馈。",
        "memory_title": "AI 洞察 (个人画像)",
        "memory_strengths": "你的强项",
        "memory_growth": "建议挑战的领域",
        "memory_last_sync": "最近同步",
        "memory_never": "暂无",
        "memory_no_data": "在 AI 模式下完成一次会话以解锁洞察。",
        "help_link": "帮助",
        "welcome_title": "欢迎来到教练练习室",
        "welcome_coach": "<b>被教练</b>：AI 针对你生活中的真实话题为你做教练，比如一个目标、一个决定或一个挑战。这些会话只有你能看到。",
        "welcome_coachee": "<b>练习做教练</b>：AI 扮演来访者，由你来提问。结束后你会得到评分和反馈。",
        "welcome_session": "在页面顶部可以随时切换两种模式。一次会话约 15 到 20 分钟，会经历五个阶段。中途离开也没关系，下次会接着进行。",
        "welcome_start": "开始",
        "welcome_guide": "查看完整指南",
        "card_title": "你的行动卡",
        "card_goal": "目标",
        "card_next_step": "下一步",
        "card_by_when": "时间",
        "card_support": "支持",
        "card_saved": "已保存在你的账户页面。",
    },
}


MODE_OPTIONS = {
    "en": {
        "template": "Template",
        "llm": "AI",
    },
    "zh": {
        "template": "模板",
        "llm": "AI",
    },
}


head = """
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#f3f8fd">
<link rel="icon" type="image/png" sizes="192x192" href="/icons/studio-icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/icons/studio-icon-180.png">
<link rel="manifest" href="/site.webmanifest">
"""


css = """
:root {
    --paper: #ffffff;
    --paper-strong: #f8fbff;
    --bg: #f3f8fd;
    --border: #d8e5f2;
    --ink: #18364a;
    --muted: #62809a;
    --primary: #1979ba;
    --primary-soft: #eef5fb;
    --accent: #f0b95a;
    --shadow: 0 16px 36px rgba(17, 73, 119, 0.10);
}

body, .gradio-container {
    background:
        radial-gradient(circle at 0% 0%, rgba(56, 154, 217, 0.10) 0, transparent 24%),
        radial-gradient(circle at 100% 10%, rgba(97, 183, 221, 0.08) 0, transparent 22%),
        linear-gradient(180deg, #f8fbfe 0%, #eef5fb 100%) !important;
    background-size: auto !important;
}

html, body, .gradio-container {
    min-height: 100dvh !important;
}

footer {
    display: none !important;
}

.gradio-container {
    padding: 12px !important;
}

#app-shell {
    max-width: 980px;
    margin: 0 auto;
    display: flex !important;
    flex-direction: column !important;
    min-height: calc(100dvh - 24px);
    height: calc(100dvh - 24px);
    gap: 10px;
    position: relative;
    box-sizing: border-box;
    padding-bottom: 16px;
}

#app-shell::before,
#app-shell::after {
    content: "";
    position: fixed;
    width: 160px;
    height: 160px;
    pointer-events: none;
    opacity: 0.22;
    z-index: 0;
}

#app-shell::before {
    top: 72px;
    left: 28px;
    background:
        radial-gradient(circle at 50% 50%, rgba(25, 121, 186, 0.18) 0 1px, transparent 1px 18px),
        radial-gradient(circle at 50% 50%, transparent 0 63%, rgba(25, 121, 186, 0.24) 63% 64%, transparent 65%);
    background-size: 18px 18px, 100% 100%;
}

#app-shell::after {
    right: 30px;
    bottom: 72px;
    background:
        linear-gradient(135deg, transparent 0 44%, rgba(25, 121, 186, 0.22) 44% 48%, transparent 48% 100%),
        linear-gradient(45deg, transparent 0 52%, rgba(25, 121, 186, 0.16) 52% 56%, transparent 56% 100%);
}

#topbar {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: stretch !important;
    justify-content: space-between !important;
    gap: 10px !important;
    width: 100% !important;
}

#topbar > div {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 10px !important;
    width: 100% !important;
}

#topbar .form {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 10px !important;
    width: 100% !important;
}

.module-card-slot {
    flex: 1 1 50% !important;
    min-width: 0 !important;
    width: 50% !important;
    display: flex !important;
}

.module-card-btn {
    width: 100% !important;
    min-height: 132px !important;
    height: 132px !important;
    border-radius: 26px !important;
    text-align: center !important;
    white-space: pre-line !important;
    line-height: 1.2 !important;
    padding: 24px 8px 18px 8px !important;
    border: 1px solid rgba(33, 109, 165, 0.18) !important;
    background:
        linear-gradient(158deg, rgba(255, 255, 255, 0.97), rgba(234, 245, 252, 0.96)),
        radial-gradient(circle at 12% 18%, rgba(87, 170, 223, 0.24) 0 18%, transparent 46%),
        radial-gradient(circle at 88% 84%, rgba(245, 188, 120, 0.24) 0 20%, transparent 48%),
        repeating-linear-gradient(135deg, rgba(44, 132, 193, 0.18) 0 10px, rgba(44, 132, 193, 0) 10px 18px) !important;
    background-size: 100% 100%, 100% 100%, 100% 100%, 84px 26px !important;
    background-position: 0 0, 0 0, 0 0, 16px 14px !important;
    background-repeat: no-repeat !important;
    box-shadow: 0 18px 34px rgba(17, 73, 119, 0.10) !important;
    color: #183f5a !important;
    font-size: 16px !important;
    font-weight: 800 !important;
    transition: transform 140ms ease, box-shadow 160ms ease, border-color 160ms ease !important;
}

.module-card-btn:hover {
    border-color: rgba(25, 121, 186, 0.42) !important;
    box-shadow: 0 22px 38px rgba(17, 73, 119, 0.14) !important;
    transform: translateY(-1px);
}

.module-card-btn.selected {
    background:
        linear-gradient(146deg, rgba(14, 88, 140, 0.99), rgba(35, 132, 190, 0.98)),
        radial-gradient(circle at 86% 18%, rgba(253, 201, 137, 0.30) 0 18%, transparent 42%),
        radial-gradient(circle at 10% 80%, rgba(146, 220, 247, 0.24) 0 18%, transparent 40%),
        repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.28) 0 10px, rgba(255, 255, 255, 0) 10px 18px) !important;
    background-size: 100% 100%, 100% 100%, 100% 100%, 84px 26px !important;
    background-position: 0 0, 0 0, 0 0, 16px 14px !important;
    background-repeat: no-repeat !important;
    border-color: rgba(24, 104, 162, 0.88) !important;
    color: #f8fbff !important;
    box-shadow: 0 24px 42px rgba(17, 73, 119, 0.20) !important;
}

.module-card-btn.selected:hover {
    border-color: rgba(194, 233, 255, 0.82) !important;
}

.intro-md {
    display: none !important;
}

@media (max-width: 600px) {
    #topbar, #topbar > div, #topbar > .form {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        width: 100% !important;
    }
    .module-card-slot {
        flex: 1 1 50% !important;
        min-width: 0 !important;
        width: 50% !important;
    }
    .module-card-btn {
        height: 110px !important;
        min-height: 110px !important;
        padding: 14px 6px !important;
        font-size: 13px !important;
        border-radius: 18px !important;
        letter-spacing: -0.2px !important;
    }
}

.tracker-shell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px;
    border-radius: 20px;
    background:
        linear-gradient(135deg, rgba(17, 84, 136, 0.98), rgba(34, 125, 183, 0.98));
    border: 1px solid rgba(21, 94, 149, 0.42);
    box-shadow: 0 18px 34px rgba(17, 73, 119, 0.18);
    position: relative;
    overflow: hidden;
    z-index: 1;
}

.tracker-shell::after {
    content: "";
    position: absolute;
    inset: auto 22px 0 22px;
    height: 1px;
    background: rgba(255, 255, 255, 0.22);
}

.tracker-copy {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.tracker-eyebrow {
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.72);
    font-weight: 800;
}

.tracker-stage {
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
}

.tracker-next {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.72);
}

.tracker-dots {
    display: flex;
    gap: 10px;
    flex-wrap: nowrap;
}

.tracker-dot {
    width: 30px;
    height: 30px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.15);
    color: rgba(255, 255, 255, 0.82);
    font-size: 12px;
    font-weight: 800;
    border: 1px solid rgba(255, 255, 255, 0.22);
}

.tracker-dot.done {
    background: rgba(255, 255, 255, 0.22);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.30);
}

.tracker-dot.active {
    background: #ffffff;
    color: white;
    border-color: #ffffff;
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.16);
}

.tracker-dot.active span {
    color: var(--primary) !important;
}

#chat-stage {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: 0 !important;
    max-height: none !important;
    gap: 10px !important;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 251, 255, 0.98)) !important;
    border-radius: 22px !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow) !important;
    overflow: hidden !important;
    position: relative !important;
    z-index: 1 !important;
    padding-bottom: 12px !important;
    box-sizing: border-box !important;
}

#chat-stage > div,
#chat-stage > .form,
#chat-stage > .wrap {
    min-height: 0 !important;
}

[data-testid="chatbot"] {
    border: none !important;
    background: transparent !important;
    padding: 18px 18px 10px 18px !important;
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: 100% !important;
    overflow: hidden !important;
}

.chatbot {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}

.chatbot > .bubble-wrap,
.chatbot > div,
[data-testid="chatbot"] > .wrap,
.chatbot > .wrap,
.chatbot .wrap {
    flex: 1 1 0 !important;
    height: 100% !important;
    max-height: none !important;
    overflow-y: auto !important;
    padding-right: 4px !important;
}

.message-wrap {
    gap: 18px !important;
}

.message.assistant {
    background: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px 16px 16px 6px !important;
    color: var(--ink) !important;
    box-shadow: none !important;
}

.message.user {
    background: #eef6fd !important;
    border: 1px solid #d7e8f6 !important;
    border-radius: 16px 16px 6px 16px !important;
    color: var(--ink) !important;
    box-shadow: none !important;
}

.chatbot button[title="Clear"],
.chatbot button[aria-label="Clear"],
[data-testid="chatbot"] button[title="Clear"],
[data-testid="chatbot"] button[aria-label="Clear"],
[data-testid="chatbot"] [aria-label="Clear"] {
    display: none !important;
}

#composer-shell {
    position: sticky !important;
    bottom: 10px !important;
    z-index: 20 !important;
    flex: 0 0 auto !important;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.95) 24%, rgba(247, 251, 255, 1) 54%) !important;
    margin-top: 4px !important;
    padding: 8px 14px 0 14px !important;
    border-top: 1px solid rgba(21, 94, 149, 0.10) !important;
}

.composer-grid {
    align-items: stretch !important;
    gap: 10px !important;
}

#input-panel {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    display: flex !important;
    min-height: 136px !important;
    max-height: 136px !important;
}

#chat-input-msg {
    width: 100% !important;
    min-width: 0 !important;
    height: 100% !important;
}

#input-panel > div,
#input-panel > div.form {
    width: 100% !important;
    height: 100% !important;
}

#chat-input-msg textarea {
    min-height: 136px !important;
    max-height: 136px !important;
    height: 136px !important;
    font-size: 16px !important;
    line-height: 1.5 !important;
    border-radius: 18px !important;
    padding: 14px 16px !important;
    background: #ffffff !important;
}

#action-panel {
    width: 268px !important;
    min-width: 268px !important;
    max-width: 268px !important;
    display: grid !important;
    grid-template-rows: 62px 62px !important;
    gap: 12px !important;
    min-height: 136px !important;
    height: 136px !important;
    max-height: 136px !important;
    overflow: visible !important;
    align-content: start !important;
}

.action-row {
    display: grid !important;
    align-items: center !important;
    width: 100% !important;
    min-height: 62px !important;
    height: 62px !important;
    margin: 0 !important;
}

#action-panel > div,
#action-panel > .form {
    min-width: 0 !important;
    margin: 0 !important;
}

#top-action-row {
    grid-template-columns: 60px minmax(0, 1fr) !important;
    column-gap: 18px !important;
    width: 100% !important;
    justify-items: stretch !important;
}

#bottom-action-row {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    column-gap: 12px !important;
    width: 100% !important;
}

.action-row > div,
.action-row > div.form {
    min-width: 0 !important;
}

.send-btn-custom,
#next-btn,
#reset-btn,
#mic-btn-wrap {
    text-transform: none !important;
    font-size: 15px !important;
    font-weight: 800 !important;
    letter-spacing: 0 !important;
}

.send-btn-custom {
    width: 100% !important;
    height: 56px !important;
    border-radius: 14px !important;
    margin: 0 !important;
    padding: 0 16px !important;
    background: linear-gradient(180deg, #2389cb, #1566a5) !important;
    border: 1px solid #125889 !important;
    box-shadow: 0 10px 20px rgba(17, 73, 119, 0.16) !important;
}

#mic-btn-wrap {
    width: 60px !important;
    min-width: 60px !important;
    max-width: 60px !important;
    margin: 0 !important;
    padding: 0 !important;
    justify-self: start !important;
}

#mic-btn-wrap > div,
#mic-btn-wrap > div.form {
    width: 60px !important;
    min-width: 60px !important;
    max-width: 60px !important;
    margin: 0 !important;
    padding: 0 !important;
}

#mic-btn-wrap .html-container,
#mic-btn-wrap .html-container > div {
    width: 60px !important;
    margin: 0 !important;
    padding: 0 !important;
}

.custom-mic-btn {
    width: 60px !important;
    height: 56px !important;
    border-radius: 14px !important;
    border: 1px solid var(--border) !important;
    background: linear-gradient(180deg, #ffffff, #f3f8fd) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    color: var(--primary) !important;
    transition: background 160ms ease, color 160ms ease, border-color 160ms ease, transform 160ms ease !important;
}

.custom-mic-btn.listening {
    background: linear-gradient(180deg, #2389cb, #1566a5) !important;
    color: #ffffff !important;
    border-color: #125889 !important;
}

.mic-glyph {
    width: 24px;
    height: 24px;
    display: block;
}

.mic-glyph path,
.mic-glyph circle {
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
    fill: none;
}

#next-btn,
#reset-btn {
    width: 100% !important;
    height: 56px !important;
    border-radius: 14px !important;
    margin: 0 !important;
    padding: 0 14px !important;
    border: 1px solid #d8e5f2 !important;
    background: linear-gradient(180deg, #ffffff, #f2f8fd) !important;
}

#settings-sheet {
    position: static !important;
    width: 100% !important;
    max-width: 980px !important;
    background: rgba(255, 255, 255, 0.98) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    box-shadow: var(--shadow) !important;
    z-index: 1 !important;
    margin-top: -2px !important;
}

#settings-sheet > .label-wrap {
    padding: 0 !important;
    margin: 0 !important;
}

#settings-sheet > .label-wrap .label-text {
    width: 100% !important;
    text-align: center !important;
    font-size: 15px !important;
    font-weight: 800 !important;
    color: var(--primary) !important;
    letter-spacing: 0.08em !important;
}

#settings-sheet > .label-wrap button {
    min-height: 44px !important;
    border-radius: 999px !important;
    background: linear-gradient(180deg, #ffffff, #f1f7fd) !important;
    border: 1px solid var(--border) !important;
    padding: 0 16px !important;
}

#settings-sheet > .wrap {
    padding: 12px 16px 16px 16px !important;
    overflow: visible !important;
    max-height: none !important;
}

.settings-hint {
    margin: 0 0 10px 0 !important;
    padding-left: 2px !important;
    color: var(--muted) !important;
    font-size: 14px !important;
    line-height: 1.45 !important;
    overflow: visible !important;
}

.settings-controls {
    display: block !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    overflow: visible !important;
}

.settings-controls > .form {
    display: grid !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 12px !important;
    overflow: visible !important;
}

/* Read-aloud sits alone on its row now that the mode switch is hidden, so it takes the full width */
.settings-controls > .form > div:last-child {
    grid-column: 1 / -1 !important;
}

.settings-controls > div,
.settings-controls > .form > div {
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    overflow: visible !important;
}

#settings-sheet .settings-controls label,
#settings-sheet .settings-controls .wrap,
#settings-sheet .settings-controls fieldset {
    min-width: 0 !important;
    max-width: 100% !important;
    white-space: normal !important;
    overflow: visible !important;
}

.memory-dashboard,
.memory-dashboard .form,
.memory-dashboard > div {
    min-width: 0 !important;
    overflow: visible !important;
}

.memory-dashboard {
    padding-left: 2px !important;
    padding-right: 2px !important;
}

/* The insight text sat on the edge of a scrolling box, which cut off its first letter */
.memory-dashboard .block {
    overflow: visible !important;
    padding-left: 4px !important;
}

.memory-dashboard ul {
    margin-left: 0 !important;
    padding-left: 1.15em !important;
    overflow: visible !important;
}

.memory-dashboard li {
    padding-left: 0.15em !important;
    overflow: visible !important;
}

@media (max-width: 768px) {
    .gradio-container {
        padding:
            max(12px, env(safe-area-inset-top))
            max(12px, env(safe-area-inset-right))
            max(12px, env(safe-area-inset-bottom))
            max(12px, env(safe-area-inset-left)) !important;
    }

    #app-shell {
        min-height: calc(100dvh - 24px);
        height: auto !important;
        gap: 10px;
        padding-bottom: calc(16px + env(safe-area-inset-bottom));
    }

    #topbar, #topbar > div, #topbar .form {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        display: flex !important;
        gap: 8px !important;
    }

    .module-card-btn {
        min-height: 112px !important;
        height: 112px !important;
        border-radius: 18px !important;
        padding: 20px 16px 16px 16px !important;
        font-size: 15px !important;
    }

    .tracker-shell {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
        padding: 12px 14px;
    }

    .tracker-shell,
    .tracker-shell .tracker-copy,
    .tracker-shell .tracker-eyebrow,
    .tracker-shell .tracker-stage,
    .tracker-shell .tracker-next,
    .tracker-shell .tracker-dot,
    .tracker-shell .tracker-dot span {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    .tracker-stage {
        font-size: 16px;
    }

    .tracker-next {
        font-size: 13px;
    }

    .tracker-dots {
        width: 100%;
        justify-content: space-between;
    }

    .tracker-dot {
        width: 28px;
        height: 28px;
        font-size: 11px;
    }

    .tracker-dot.active,
    .tracker-dot.active span {
        color: var(--primary) !important;
        -webkit-text-fill-color: var(--primary) !important;
    }

    .chatbot {
        min-height: 0 !important;
        height: auto !important;
    }

    #chat-stage {
        flex: 1 1 auto !important;
        height: auto !important;
        min-height: 470px !important;
        gap: 8px !important;
        padding-bottom: calc(10px + env(safe-area-inset-bottom)) !important;
    }

    #composer-shell {
        bottom: calc(8px + env(safe-area-inset-bottom)) !important;
        margin-top: 2px !important;
        padding: 8px 12px 0 12px !important;
    }

    .composer-grid {
        flex-direction: column !important;
        gap: 8px !important;
    }

    #action-panel {
        display: grid !important;
        grid-template-rows: auto auto !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: none !important;
        min-height: 0 !important;
        height: auto !important;
        max-height: none !important;
        gap: 8px !important;
    }

    .action-row {
        gap: 8px !important;
        display: grid !important;
        min-height: 48px !important;
        height: auto !important;
    }

    #input-panel {
        min-height: 56px !important;
        max-height: 56px !important;
    }

    #chat-input-msg textarea {
        min-height: 56px !important;
        max-height: 56px !important;
        height: 56px !important;
        line-height: 1.35 !important;
        padding: 14px 14px !important;
    }

    #top-action-row {
        grid-template-columns: 56px minmax(0, 1fr) !important;
        column-gap: 10px !important;
    }

    #bottom-action-row {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        column-gap: 8px !important;
    }

    #settings-sheet {
        width: 100% !important;
        border-radius: 16px !important;
    }

    #settings-sheet .form {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }

    #settings-sheet .form > div {
        min-width: min(100%, 164px) !important;
    }

    .memory-dashboard .form {
        flex-direction: column !important;
    }
}

/* One-page layout overrides */
html,
body,
.gradio-container {
    width: 100% !important;
    height: 100dvh !important;
    min-height: 100dvh !important;
    max-height: 100dvh !important;
    overflow: hidden !important;
}

* {
    box-sizing: border-box;
}

body,
.gradio-container {
    background: #f8fbff !important;
    color: #18364a !important;
}

.gradio-container {
    padding: 10px !important;
}

#app-shell {
    width: min(100%, 1040px) !important;
    max-width: 1040px !important;
    height: calc(100dvh - 20px) !important;
    min-height: 0 !important;
    max-height: calc(100dvh - 20px) !important;
    overflow: hidden !important;
    gap: 8px !important;
    padding: 0 !important;
}

#app-shell::before,
#app-shell::after {
    opacity: 0.10 !important;
}

#topbar.module-tabs,
#topbar.module-tabs .form {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 8px !important;
    width: 100% !important;
}

#topbar.module-tabs > div,
#topbar.module-tabs > .form > div {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    width: 100% !important;
}

.module-card-slot {
    width: 100% !important;
    min-width: 0 !important;
}

.module-card-btn,
.module-card-btn.selected {
    width: 100% !important;
    height: 58px !important;
    min-height: 58px !important;
    border-radius: 8px !important;
    padding: 0 12px !important;
    white-space: pre-line !important;
    line-height: 1.22 !important;
    font-size: 14px !important;
    letter-spacing: 0 !important;
    box-shadow: none !important;
}

.module-card-btn {
    background: #ffffff !important;
    color: #115488 !important;
    border: 1px solid #d8e5f2 !important;
}

.module-card-btn.selected {
    background: #1979ba !important;
    color: #ffffff !important;
    border-color: #115488 !important;
}

#settings-sheet {
    flex: 0 0 auto !important;
    margin: 0 !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    background: #ffffff !important;
}

#settings-sheet > .label-wrap button {
    min-height: 34px !important;
    border-radius: 8px !important;
}

#settings-sheet > .wrap {
    max-height: min(56dvh, 460px) !important;
    overflow-y: auto !important;
}

.tracker-shell {
    flex: 0 0 auto !important;
    min-height: 64px !important;
    padding: 10px 14px !important;
    border-radius: 8px !important;
    background: #115488 !important;
    box-shadow: none !important;
}

.tracker-eyebrow {
    letter-spacing: 0.08em !important;
}

.tracker-dots {
    flex-shrink: 0 !important;
}

#chat-stage {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: auto !important;
    max-height: none !important;
    border-radius: 10px !important;
    box-shadow: none !important;
    border-color: #d8e5f2 !important;
    padding-bottom: 8px !important;
}

[data-testid="chatbot"],
.chatbot {
    min-height: 0 !important;
}

#composer-shell {
    flex: 0 0 auto !important;
    position: static !important;
    margin: 0 !important;
    padding: 8px 12px 0 12px !important;
}

#chat-input-msg textarea {
    border-radius: 8px !important;
    border-color: #d8e5f2 !important;
}

.send-btn-custom,
.custom-mic-btn,
#next-btn,
#reset-btn {
    border-radius: 8px !important;
}

.send-btn-custom {
    background: #1979ba !important;
    border-color: #115488 !important;
}

@media (max-width: 768px) {
    .gradio-container {
        padding: max(8px, env(safe-area-inset-top)) max(8px, env(safe-area-inset-right)) max(8px, env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left)) !important;
        align-items: stretch !important;
        justify-content: flex-start !important;
    }

    .gradio-container,
    .gradio-container > div,
    main,
    .main,
    .contain {
        width: 100vw !important;
        max-width: 100vw !important;
        min-width: 0 !important;
        overflow: hidden !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }

    .gradio-container main.contain,
    .gradio-container > main.contain {
        position: fixed !important;
        inset: 0 !important;
        flex: 0 0 100vw !important;
        width: 100vw !important;
        max-width: 100vw !important;
        height: 100dvh !important;
        max-height: 100dvh !important;
        padding: 8px !important;
        margin: 0 !important;
        overflow: hidden !important;
    }

    #app-shell {
        width: 100% !important;
        max-width: 100% !important;
        height: calc(100dvh - 16px) !important;
        max-height: calc(100dvh - 16px) !important;
        gap: 7px !important;
        margin: 0 !important;
    }

    #topbar.module-tabs,
    #topbar.module-tabs .form {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
    }

    #topbar.module-tabs > div,
    #topbar.module-tabs .form,
    .module-card-slot,
    .module-card-btn {
        min-width: 0 !important;
        max-width: 100% !important;
    }

    .tracker-shell,
    #chat-stage,
    #composer-shell,
    .composer-grid,
    #input-panel,
    #action-panel,
    #settings-sheet,
    #settings-sheet .form,
    #settings-sheet .wrap {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
    }

    .module-card-btn,
    .module-card-btn.selected {
        height: 58px !important;
        min-height: 58px !important;
        padding: 0 8px !important;
        font-size: 13px !important;
    }

    #settings-sheet > .label-wrap button {
        min-height: 32px !important;
    }

    #settings-sheet > .wrap {
        max-height: min(54dvh, 420px) !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }

    .settings-controls {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        display: block !important;
        overflow: visible !important;
    }

    .settings-controls > .form {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 8px !important;
        overflow: visible !important;
    }

    .settings-controls > div,
    .settings-controls > .form > div {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: visible !important;
    }

    .tracker-shell {
        min-height: 78px !important;
        padding: 9px 12px !important;
        gap: 7px !important;
    }

    .tracker-copy {
        gap: 2px !important;
    }

    .tracker-stage {
        font-size: 15px !important;
    }

    .tracker-next {
        font-size: 12px !important;
    }

    .tracker-dots {
        gap: 6px !important;
    }

    .tracker-dot {
        width: 26px !important;
        height: 26px !important;
        font-size: 11px !important;
    }

    #chat-stage {
        min-height: 0 !important;
        padding-bottom: 7px !important;
    }

    [data-testid="chatbot"] {
        padding: 12px 12px 7px 12px !important;
    }

    .message-wrap {
        gap: 10px !important;
    }

    #composer-shell {
        padding: 7px 10px 0 10px !important;
    }

    .composer-grid {
        gap: 7px !important;
    }

    #input-panel,
    #chat-input-msg textarea {
        min-height: 50px !important;
        height: 50px !important;
        max-height: 50px !important;
    }

    #action-panel {
        gap: 7px !important;
        min-height: 99px !important;
        height: 99px !important;
        max-height: 99px !important;
        overflow: visible !important;
    }

    #top-action-row,
    #bottom-action-row {
        min-height: 46px !important;
    }

    .send-btn-custom,
    .custom-mic-btn,
    #next-btn,
    #reset-btn {
        height: 46px !important;
        min-height: 46px !important;
    }
}

@media (max-width: 768px) {
    body .gradio-container {
        padding: 0 !important;
    }

    body main.contain {
        position: fixed !important;
        inset: 0 !important;
        flex: 0 0 100vw !important;
        width: 100vw !important;
        max-width: 100vw !important;
        height: 100dvh !important;
        max-height: 100dvh !important;
        padding: 8px !important;
        margin: 0 !important;
        overflow: hidden !important;
    }
}

@media (max-width: 768px) {
    #app-shell,
    body main.contain #app-shell {
        width: calc(100vw - 16px) !important;
        max-width: calc(100vw - 16px) !important;
        min-width: 0 !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    #topbar.module-tabs,
    #topbar.module-tabs > div,
    #topbar.module-tabs .form {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
    }

    #topbar.module-tabs > div,
    #topbar.module-tabs > .form > div,
    #topbar.module-tabs .form > div,
    #topbar.module-tabs .module-card-slot {
        flex: 1 1 0 !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }

    #topbar.module-tabs .module-card-btn {
        min-width: 0 !important;
        width: 100% !important;
    }

    .tracker-shell,
    .tracker-copy,
    .tracker-dots,
    #chat-stage,
    [data-testid="chatbot"],
    .chatbot,
    .message-wrap,
    .message,
    #composer-shell,
    .composer-grid {
        min-width: 0 !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
    }

    .message,
    .message * {
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }

    .tracker-dots {
        display: grid !important;
        grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
        gap: 6px !important;
        justify-items: center !important;
    }

    .action-row,
    .action-row > div,
    .action-row .form,
    .action-row .form > div {
        min-width: 0 !important;
        max-width: 100% !important;
        overflow-x: hidden !important;
    }

    #bottom-action-row {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        grid-template-rows: 42px !important;
        gap: 7px !important;
        height: auto !important;
    }

    #action-panel {
        height: auto !important;
        max-height: none !important;
    }

    .action-row > div,
    .action-row .form > div {
        width: 100% !important;
    }
}

/* Transformational studio finish */
body,
.gradio-container {
    background:
        linear-gradient(135deg, rgba(18, 111, 168, 0.07) 0 1px, transparent 1px 44px),
        linear-gradient(45deg, rgba(244, 180, 77, 0.07) 0 1px, transparent 1px 52px),
        linear-gradient(180deg, #f9fcff 0%, #eaf4fb 100%) !important;
}

#app-shell {
    width: min(100%, 1080px) !important;
    max-width: 1080px !important;
    gap: 9px !important;
}

.intro-md {
    display: block !important;
    flex: 0 0 auto !important;
    min-width: 0 !important;
    z-index: 1 !important;
}

.transformation-hero {
    display: grid;
    grid-template-rows: 58px 104px;
    gap: 9px;
    min-width: 0;
}

.studio-header {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
    padding: 0 18px;
    border: 1px solid #d8e5f2;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.94);
    box-shadow: 0 14px 32px rgba(13, 78, 122, 0.08);
}

.studio-mark {
    width: 34px;
    height: 34px;
    flex: 0 0 34px;
    border-radius: 10px;
    display: block;
    object-fit: cover;
    background: #ffffff;
    border: 1px solid rgba(24, 63, 90, 0.10);
    position: relative;
}

.studio-mark::after {
    content: none;
}

.studio-title-group {
    min-width: 0;
}

.studio-title {
    font-size: 15px;
    line-height: 1.12;
    font-weight: 900;
    color: #18364a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.studio-subtitle {
    margin-top: 2px;
    font-size: 10px;
    line-height: 1.2;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 900;
    color: #5d7486;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.hero-panel {
    position: relative;
    display: flex;
    align-items: center;
    min-width: 0;
    overflow: hidden;
    padding: 15px 22px;
    border-radius: 20px;
    border: 1px solid rgba(13, 78, 122, 0.28);
    background:
        linear-gradient(128deg, #115488 0%, #1979ba 58%, #2b8fbe 100%),
        repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0 1px, transparent 1px 18px);
    box-shadow: 0 20px 42px rgba(13, 78, 122, 0.20);
}

.hero-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.11) 0 1px, transparent 1px 18px);
    opacity: 0.35;
}

.hero-copy {
    position: relative;
    z-index: 1;
    min-width: 0;
    max-width: 620px;
}

.hero-eyebrow {
    font-size: 11px;
    line-height: 1.15;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 900;
    color: rgba(255, 255, 255, 0.76) !important;
    -webkit-text-fill-color: rgba(255, 255, 255, 0.76) !important;
}

.hero-copy h1 {
    margin: 6px 0 4px 0;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-size: 26px;
    line-height: 1.08;
    letter-spacing: 0;
    font-weight: 900;
}

.hero-copy p {
    margin: 0;
    max-width: 580px;
    color: rgba(255, 255, 255, 0.82) !important;
    -webkit-text-fill-color: rgba(255, 255, 255, 0.82) !important;
    font-size: 13px;
    line-height: 1.35;
}

.hero-arc {
    position: absolute;
    right: 36px;
    top: 22px;
    width: 260px;
    height: 70px;
    border: 2px solid rgba(244, 180, 77, 0.62);
    border-left-color: transparent;
    border-bottom-color: transparent;
    border-radius: 50%;
    transform: rotate(-8deg);
}

#topbar.module-tabs,
#topbar.module-tabs .form {
    gap: 10px !important;
}

.module-card-btn,
.module-card-btn.selected {
    height: 68px !important;
    min-height: 68px !important;
    border-radius: 16px !important;
    padding: 0 18px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    white-space: pre-line !important;
    line-height: 1.18 !important;
    overflow-wrap: normal !important;
    word-break: keep-all !important;
    font-size: 15px !important;
    font-weight: 900 !important;
    box-shadow: 0 12px 28px rgba(13, 78, 122, 0.08) !important;
}

.module-card-btn {
    background: linear-gradient(180deg, #ffffff, #f8fbff) !important;
    color: #115488 !important;
    -webkit-text-fill-color: #115488 !important;
    border: 1px solid #d8e5f2 !important;
}

.module-card-btn.selected {
    background: linear-gradient(145deg, #115488, #1979ba) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-color: #115488 !important;
    box-shadow: 0 16px 34px rgba(13, 78, 122, 0.18) !important;
}

.tracker-shell {
    min-height: 68px !important;
    border-radius: 17px !important;
    padding: 10px 18px !important;
    background: rgba(255, 255, 255, 0.96) !important;
    border: 1px solid #d8e5f2 !important;
    box-shadow: 0 12px 28px rgba(13, 78, 122, 0.08) !important;
}

.tracker-eyebrow {
    color: #5d7486 !important;
    -webkit-text-fill-color: #5d7486 !important;
    font-size: 10px !important;
    letter-spacing: 0.12em !important;
}

.tracker-stage {
    color: #18364a !important;
    -webkit-text-fill-color: #18364a !important;
    font-size: 16px !important;
}

.tracker-next {
    color: #5d7486 !important;
    -webkit-text-fill-color: #5d7486 !important;
}

.tracker-dot {
    background: #e7f3fa !important;
    color: #115488 !important;
    border: 3px solid #ffffff !important;
    box-shadow: 0 0 0 1px #d8e5f2 !important;
}

.tracker-dot.done {
    background: #1979ba !important;
    color: #ffffff !important;
}

.tracker-dot.active {
    background: #f0b95a !important;
    color: #4f3600 !important;
    box-shadow: 0 0 0 4px rgba(244, 180, 77, 0.18) !important;
}

.tracker-dot.active span {
    color: #4f3600 !important;
    -webkit-text-fill-color: #4f3600 !important;
}

#chat-stage {
    border-radius: 20px !important;
    box-shadow: 0 16px 38px rgba(13, 78, 122, 0.10) !important;
}

.send-btn-custom {
    background: linear-gradient(180deg, #2389cb, #1979ba) !important;
    border-color: #115488 !important;
}

.custom-mic-btn {
    color: #1979ba !important;
    background: linear-gradient(180deg, #ffffff, #f8fbff) !important;
}

@media (max-width: 768px) {
    #app-shell,
    body main.contain #app-shell {
        gap: 7px !important;
    }

    .module-card-btn,
    .module-card-btn.selected {
        height: 48px !important;
        min-height: 48px !important;
        border-radius: 15px !important;
        padding: 0 12px !important;
        font-size: 12px !important;
        line-height: 1.15 !important;
    }

    .tracker-shell {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        grid-template-rows: auto auto !important;
        min-height: 70px !important;
        padding: 8px 12px !important;
        border-radius: 16px !important;
    }

    .tracker-shell,
    .tracker-shell .tracker-copy,
    .tracker-shell .tracker-eyebrow,
    .tracker-shell .tracker-stage,
    .tracker-shell .tracker-next,
    .tracker-shell .tracker-dot,
    .tracker-shell .tracker-dot span {
        color: #18364a !important;
        -webkit-text-fill-color: #18364a !important;
    }

    .tracker-shell .tracker-eyebrow,
    .tracker-shell .tracker-next {
        color: #5d7486 !important;
        -webkit-text-fill-color: #5d7486 !important;
    }

    .tracker-next {
        display: none !important;
    }

    .tracker-copy {
        width: 100% !important;
        min-width: 0 !important;
        overflow: hidden !important;
    }

    .tracker-eyebrow,
    .tracker-stage {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }

    .tracker-dots {
        display: grid !important;
        grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
        width: 100% !important;
        justify-items: center !important;
        gap: 6px !important;
        overflow: visible !important;
    }

    .tracker-dot {
        display: flex !important;
        width: 26px !important;
        height: 26px !important;
        min-width: 0 !important;
        border: 3px solid #ffffff !important;
        border-radius: 999px !important;
        box-shadow: 0 0 0 1px #d8e5f2 !important;
    }

    .tracker-dot span {
        display: inline !important;
    }

    #chat-stage {
        border-radius: 18px !important;
    }

    #composer-shell {
        border-radius: 16px !important;
    }

    .custom-mic-btn {
        border-radius: 13px !important;
    }
}

/* Unified compact top layout */
.intro-md {
    display: block !important;
    flex: 0 0 auto !important;
    margin: 0 !important;
}

.studio-header {
    min-height: 52px !important;
    height: 52px !important;
    padding: 0 16px !important;
    border-radius: 16px !important;
    box-shadow: 0 10px 24px rgba(13, 78, 122, 0.08) !important;
}

.studio-mark {
    width: 32px !important;
    height: 32px !important;
    flex-basis: 32px !important;
}

#topbar.module-tabs,
#topbar.module-tabs .form {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: 8px !important;
    width: 100% !important;
}

#topbar.module-tabs {
    margin: 0 0 -9px 0 !important;
    padding: 10px !important;
    border: 1px solid #d8e5f2 !important;
    border-bottom: 0 !important;
    border-radius: 16px 16px 0 0 !important;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 250, 255, 0.98)),
        repeating-linear-gradient(135deg, rgba(18, 111, 168, 0.06) 0 1px, transparent 1px 18px) !important;
    box-shadow: 0 12px 28px rgba(13, 78, 122, 0.08) !important;
    overflow: hidden !important;
}

#topbar.module-tabs > div,
#topbar.module-tabs > .form > div,
#topbar.module-tabs .form > div,
#topbar.module-tabs .module-card-slot {
    min-width: 0 !important;
    width: 100% !important;
}

.module-card-btn,
.module-card-btn.selected {
    height: 50px !important;
    min-height: 50px !important;
    border-radius: 14px !important;
    padding: 0 14px !important;
    font-size: 14px !important;
    line-height: 1.15 !important;
    box-shadow: none !important;
}

.mode-context-md {
    display: block !important;
    flex: 0 0 auto !important;
    margin: 0 !important;
    min-width: 0 !important;
    z-index: 1 !important;
}

.mode-context-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    column-gap: 10px;
    row-gap: 2px;
    min-height: 40px;
    margin: 0;
    padding: 8px 14px 10px 14px;
    border: 1px solid #d8e5f2;
    border-top: 0;
    border-radius: 0 0 16px 16px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: 0 12px 28px rgba(13, 78, 122, 0.08);
    overflow: hidden;
}

.mode-context-label {
    color: #5d7486;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.mode-context-title {
    color: #18364a;
    font-size: 13px;
    font-weight: 900;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.mode-context-card p {
    grid-column: 1 / -1;
    margin: 0;
    color: #45647a;
    font-size: 12px;
    line-height: 1.25;
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    white-space: normal;
    overflow-wrap: anywhere;
}

#settings-sheet {
    margin: 0 !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 20px rgba(13, 78, 122, 0.06) !important;
}

#settings-sheet > .label-wrap button {
    min-height: 36px !important;
    border-radius: 14px !important;
}

.tracker-shell {
    min-height: 58px !important;
    padding: 8px 16px !important;
}

@media (max-width: 768px) {
    .intro-md {
        display: block !important;
        height: auto !important;
        min-height: 0 !important;
        overflow: visible !important;
    }

    .studio-header {
        height: 48px !important;
        min-height: 48px !important;
        padding: 0 12px !important;
        border-radius: 14px !important;
    }

    .studio-mark {
        width: 30px !important;
        height: 30px !important;
        flex-basis: 30px !important;
        opacity: 1 !important;
        overflow: visible !important;
    }

    .studio-title {
        font-size: 14px !important;
    }

    .studio-subtitle {
        font-size: 9px !important;
        letter-spacing: 0.02em !important;
        text-transform: none !important;
    }

    #topbar.module-tabs {
        padding: 8px !important;
        margin-bottom: -7px !important;
        border-radius: 14px 14px 0 0 !important;
    }

    .module-card-btn,
    .module-card-btn.selected {
        height: 44px !important;
        min-height: 44px !important;
        border-radius: 12px !important;
        padding: 0 10px !important;
        font-size: 12px !important;
    }

    .mode-context-card {
        min-height: 38px;
        padding: 7px 11px 9px 11px;
        border-radius: 0 0 14px 14px;
    }

    .mode-context-label,
    .mode-context-title {
        font-size: 10px;
    }

    .mode-context-card p {
        font-size: 11px;
    }

    #settings-sheet > .label-wrap button {
        min-height: 32px !important;
    }

    .tracker-shell {
        min-height: 60px !important;
        padding: 8px 12px !important;
    }
}

/* Row alignment contract */
.intro-md,
#topbar.module-tabs,
.mode-context-md,
#settings-sheet,
.tracker-shell,
#chat-stage,
#composer-shell {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    align-self: stretch !important;
    box-sizing: border-box !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}

.studio-header,
.mode-context-card,
#topbar.module-tabs .form,
#settings-sheet > .wrap,
#settings-sheet .form,
.composer-grid {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
}

.gradio-html:has(.tracker-shell),
.html-container:has(.tracker-shell),
div:has(> .tracker-shell) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    box-sizing: border-box !important;
}

#topbar.module-tabs {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

.mode-context-card {
    margin: 0 !important;
}

.tracker-shell {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) auto !important;
    align-items: center !important;
    column-gap: 16px !important;
}

@media (max-width: 768px) {
    .intro-md,
    #topbar.module-tabs,
    .mode-context-md,
    #settings-sheet,
    .tracker-shell,
    #chat-stage,
    #composer-shell {
        width: 100% !important;
        max-width: 100% !important;
        align-self: stretch !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }

    .tracker-shell {
        grid-template-columns: minmax(0, 1fr) !important;
        column-gap: 0 !important;
    }
}

/* Header right side: today's AI allowance and the account link */
.studio-account {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 0 0 auto;
}

.studio-quota {
    font-size: 12px;
    line-height: 1.2;
    font-weight: 800;
    color: #115488;
    background: #eef5fb;
    border-radius: 999px;
    padding: 4px 10px;
    white-space: nowrap;
}

.studio-account-link {
    font-size: 13px;
    line-height: 1.2;
    font-weight: 800;
    color: #1979ba !important;
    text-decoration: none !important;
    padding: 6px 12px;
    border: 1px solid #d8e5f2;
    border-radius: 12px;
    background: #ffffff;
    white-space: nowrap;
}

.studio-account-link:focus-visible {
    outline: 3px solid rgba(25, 121, 186, 0.35);
    outline-offset: 2px;
}

@media (max-width: 768px) {
    .studio-account {
        gap: 6px;
    }

    .studio-quota {
        font-size: 11px;
        padding: 3px 8px;
    }

    .studio-account-link {
        font-size: 12px;
        padding: 5px 10px;
    }
}

@media (max-width: 480px) {
    /* Room for Help and Account on phones: the name may take two lines and the tagline steps aside */
    .studio-subtitle {
        display: none !important;
    }

    .studio-title {
        white-space: normal !important;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        line-height: 1.15 !important;
    }
}

.mode-context-title .studio-quota {
    margin-left: 6px;
    vertical-align: 1px;
}

/* First-visit welcome card: a fixed layer over the page, closed in the browser */
#welcome-host {
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
}

.welcome-layer {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: max(16px, env(safe-area-inset-top)) 16px max(16px, env(safe-area-inset-bottom));
    background: rgba(17, 73, 119, 0.28);
}

.welcome-card {
    width: min(460px, 100%);
    max-height: 100%;
    overflow-y: auto;
    background: #ffffff;
    border: 1px solid #d8e5f2;
    border-radius: 22px;
    box-shadow: 0 24px 42px rgba(17, 73, 119, 0.20);
    padding: 24px;
    color: #18364a;
    text-align: left;
}

.welcome-card h2 {
    margin: 0 0 14px !important;
    font-size: 22px !important;
    font-weight: 800 !important;
    line-height: 1.2 !important;
    letter-spacing: -0.01em;
    color: #18364a !important;
}

.welcome-card ul {
    margin: 0 0 20px !important;
    padding-left: 20px !important;
    list-style: disc;
}

.welcome-card li {
    margin: 0 0 10px !important;
    font-size: 15px !important;
    line-height: 1.5 !important;
    color: #18364a !important;
}

.welcome-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}

.welcome-start {
    flex: 1 1 160px;
    min-height: 46px;
    border: 0;
    border-radius: 16px;
    background: #1979ba;
    color: #ffffff !important;
    font-size: 16px;
    font-weight: 800;
    cursor: pointer;
}

.welcome-start:hover {
    background: #0f6aa8;
}

.welcome-guide {
    font-size: 14px;
    font-weight: 700;
    color: #1979ba !important;
}

.welcome-start:focus-visible,
.welcome-guide:focus-visible {
    outline: 3px solid rgba(25, 121, 186, 0.35);
    outline-offset: 2px;
}

/* Compact phone layout: the conversation gets most of the screen.
   Every band stays visible, but spacing, padding and stacked rows shrink.
   Gradio prefixes each selector with its container, so selectors start at #app-shell, never at body. */
@media (max-width: 767px) {
    #app-shell {
        gap: 6px !important;
    }

    /* The HTML blocks around the header, mode card and stage bar carry 20px of padding */
    #app-shell .intro-md .html-container,
    #app-shell .mode-context-md .html-container,
    #app-shell .tracker-md .html-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    #app-shell .studio-header {
        height: 44px !important;
        min-height: 44px !important;
    }

    #app-shell #topbar.module-tabs {
        padding: 5px !important;
        margin-bottom: -6px !important;
        gap: 5px !important;
    }

    #app-shell .module-card-btn,
    #app-shell .module-card-btn.selected {
        height: 40px !important;
        min-height: 40px !important;
        padding: 0 10px !important;
        font-size: 12px !important;
        line-height: 1.15 !important;
    }

    /* Mode card: one line with the mode name and today's allowance; the description is in the mode buttons */
    #app-shell .mode-context-card {
        min-height: 0 !important;
        padding: 6px 11px 6px 11px !important;
        row-gap: 0 !important;
    }

    #app-shell .mode-context-card p {
        display: none !important;
    }

    #app-shell #settings-sheet {
        padding: 6px 12px !important;
    }

    /* Stage bar: the stage name and the five dots on one row */
    #app-shell .tracker-shell {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 10px !important;
        min-height: 0 !important;
        padding: 6px 10px 6px 12px !important;
    }

    #app-shell .tracker-shell .tracker-eyebrow {
        display: none !important;
    }

    #app-shell .tracker-copy {
        width: auto !important;
        min-width: 0 !important;
        flex: 1 1 auto !important;
        text-align: left !important;
    }

    #app-shell .tracker-stage {
        font-size: 14px !important;
    }

    #app-shell .tracker-dots {
        display: flex !important;
        width: auto !important;
        flex: 0 0 auto !important;
        gap: 5px !important;
    }

    #app-shell .tracker-dot {
        width: 22px !important;
        height: 22px !important;
        min-width: 22px !important;
        font-size: 11px !important;
        border-width: 2px !important;
    }

    /* Composer: message box, microphone and Send on one row; Skip Ahead and New Session on a slim row below */
    #app-shell #composer-shell {
        padding-top: 6px !important;
        padding-bottom: max(6px, env(safe-area-inset-bottom)) !important;
    }

    #app-shell .composer-grid {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto !important;
        grid-template-areas: "input actions" "steps steps" !important;
        gap: 6px !important;
        align-items: stretch !important;
    }

    #app-shell #input-panel {
        grid-area: input !important;
        min-width: 0 !important;
        width: auto !important;
    }

    #app-shell #action-panel {
        display: contents !important;
    }

    #app-shell #top-action-row {
        grid-area: actions !important;
        display: flex !important;
        gap: 6px !important;
        width: auto !important;
        height: auto !important;
    }

    #app-shell #mic-btn-wrap {
        width: 46px !important;
        min-width: 46px !important;
        max-width: 46px !important;
        flex: 0 0 46px !important;
    }

    #app-shell .send-btn-custom {
        width: 72px !important;
        min-width: 72px !important;
        flex: 0 0 72px !important;
        height: auto !important;
        min-height: 46px !important;
    }

    #app-shell #bottom-action-row {
        grid-area: steps !important;
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        grid-template-rows: 36px !important;
        gap: 6px !important;
    }

    #app-shell #next-btn,
    #app-shell #reset-btn {
        height: 36px !important;
        min-height: 36px !important;
        font-size: 13px !important;
    }

    /* Two lines of 16px text (smaller text makes iPhones zoom the page when the box is tapped) */
    #app-shell #input-panel,
    #app-shell #chat-input-msg textarea {
        height: 58px !important;
        min-height: 58px !important;
        max-height: 58px !important;
    }

    #app-shell #chat-input-msg textarea {
        padding: 8px 12px !important;
        font-size: 16px !important;
        line-height: 1.3 !important;
    }

    #app-shell .send-btn-custom {
        min-height: 58px !important;
    }
}
"""


# Remember the chosen language for the account pages and the next visit (read by account_pages.preferred_language).
remember_lang_js = """(lang) => {
    const code = lang === "中文" ? "zh" : "en";
    document.cookie = "erickson_lang=" + code + "; path=/; max-age=31536000; samesite=lax";
}"""


global_viewport_style = """
<style>
#viewport-style-injector {
    display: none !important;
}

@media (max-width: 768px) {
    body .gradio-container {
        padding: 0 !important;
    }

    body main.contain {
        position: fixed !important;
        inset: 0 !important;
        flex: 0 0 100vw !important;
        width: 100vw !important;
        max-width: 100vw !important;
        height: 100dvh !important;
        max-height: 100dvh !important;
        padding: 8px !important;
        margin: 0 !important;
        overflow: hidden !important;
    }
}
</style>
"""


scroll_js = """
() => {
    requestAnimationFrame(() => {
        const chatbotEl = document.querySelector('[data-testid="chatbot"]');
        if (!chatbotEl) return;
        const scrollContainer = chatbotEl.querySelector('.wrap') || chatbotEl;
        scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
    });
}
"""

tts_js = """
(payload, toggle, voiceSelector, langSelector) => {
    const raw = (payload || "").toString();
    const parts = raw.split("|||");
    const text = parts.length > 1 ? parts.slice(1).join("|||") : raw;
    if (!text || !toggle || !window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const targetLang = langSelector === "English" ? "en-US" : "zh-CN";
    const targetFamily = targetLang.startsWith('zh') ? 'zh' : 'en';
    const wantsFemale = voiceSelector.includes("女") || voiceSelector.includes("Female");
    const normalize = (value) => (value || "").toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "");
    const femaleKeywords = [
        "tingting", "meijia", "xiaoxiao", "xiaoyi", "xiaorui", "sinji", "yushu",
        "samantha", "victoria", "zira", "ava", "serena", "female"
    ].map(normalize);
    const maleKeywords = [
        "limu", "liMu", "yunjian", "yunxi", "yunyang", "yunhao", "bohan",
        "daniel", "alex", "david", "arthur", "fred", "reed", "male"
    ].map(normalize);

    const scoreVoice = (voice) => {
        const name = normalize(voice.name);
        const uri = normalize(voice.voiceURI || '');
        const meta = `${name} ${uri}`;
        const lang = (voice.lang || "").toLowerCase();
        let score = 0;

        if (lang.startsWith(targetFamily)) score += 40;
        if (targetLang === "zh-CN" && lang.startsWith("zh-cn")) score += 16;
        if (targetLang === "zh-CN" && (lang.startsWith("zh-sg") || lang.startsWith("zh-hk") || lang.startsWith("zh-tw"))) score += 10;
        if (targetLang === "en-US" && lang.startsWith("en-us")) score += 16;
        if (targetLang === "en-US" && (lang.startsWith("en-gb") || lang.startsWith("en-au"))) score += 10;

        const wanted = wantsFemale ? femaleKeywords : maleKeywords;
        const unwanted = wantsFemale ? maleKeywords : femaleKeywords;

        wanted.forEach((keyword, index) => {
            if (meta.includes(keyword)) score += 140 - index;
        });
        unwanted.forEach((keyword) => {
            if (meta.includes(keyword)) score -= 80;
        });

        if (voice.default) score += 4;
        if (voice.localService) score += 2;
        return score;
    };

    const pickVoice = (voices) => {
        if (!voices.length) return null;
        const ranked = voices
            .map((voice) => ({ voice, score: scoreVoice(voice) }))
            .sort((a, b) => b.score - a.score);
        return ranked[0];
    };

    const speak = () => {
        const voices = window.speechSynthesis.getVoices();
        const sameLang = voices.filter((voice) => (voice.lang || "").toLowerCase().startsWith(targetFamily));
        const preferred = pickVoice(sameLang);
        const fallback = pickVoice(voices);
        const maleMatch = wantsFemale ? null : sameLang.find((voice) => scoreVoice(voice) >= 120);
        const femaleMatch = wantsFemale ? sameLang.find((voice) => scoreVoice(voice) >= 120) : null;

        if (maleMatch) {
            utterance.voice = maleMatch;
        } else if (femaleMatch) {
            utterance.voice = femaleMatch;
        } else if (preferred && preferred.score >= 80) {
            utterance.voice = preferred.voice;
        } else if (fallback) {
            utterance.voice = fallback.voice;
        } else if (sameLang.length > 0) {
            utterance.voice = sameLang[0];
        }

        utterance.lang = utterance.voice?.lang || targetLang;
        utterance.volume = 1;
        utterance.rate = 0.95;
        utterance.pitch = wantsFemale ? 1.0 : 0.72;
        window.speechSynthesis.resume();
        setTimeout(() => {
            window.speechSynthesis.resume();
            window.speechSynthesis.speak(utterance);
        }, 20);
    };

    let attempts = 0;
    const waitForVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0 || attempts >= 10) {
            speak();
            return;
        }
        attempts += 1;
        setTimeout(waitForVoices, 120);
    };

    waitForVoices();
}
"""

force_light_js = """() => {
    document.body.classList.remove('dark');
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const micIcon = '<svg class="mic-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3 3 0 0 0 3-3V8a3 3 0 1 0-6 0v4a3 3 0 0 0 3 3Z"></path><path d="M6.5 11.5a5.5 5.5 0 0 0 11 0"></path><path d="M12 17v3"></path><path d="M9.5 20h5"></path></svg>';

    const focusInput = () => {
        const textarea = document.querySelector('#chat-input-msg textarea');
        if (!textarea) return;
        textarea.removeAttribute('readonly');
        textarea.focus({ preventScroll: true });
        const end = textarea.value.length;
        if (typeof textarea.setSelectionRange === 'function') {
            textarea.setSelectionRange(end, end);
        }
        textarea.click();
        requestAnimationFrame(() => {
            textarea.scrollIntoView({ block: 'center', behavior: 'smooth' });
            textarea.focus({ preventScroll: true });
        });
    };

    const micLabels = () => {
        const isEnglish = document.querySelector('input[type="radio"][value="English"]')?.checked;
        return isEnglish
            ? { idle: 'Start voice input', active: 'Tap again to stop' }
            : { idle: '开始语音输入', active: '再次点击结束录音' };
    };

    const setMicState = (btn, listening) => {
        btn.innerHTML = micIcon;
        btn.classList.toggle('listening', !!listening);
        const labels = micLabels();
        btn.title = listening ? labels.active : labels.idle;
        btn.setAttribute('aria-label', listening ? labels.active : labels.idle);
    };

    const bindMic = () => {
        const btn = document.getElementById('custom-mic-btn');
        if (!btn || btn.dataset.bound === 'true') return;
        btn.dataset.bound = 'true';
        setMicState(btn, false);

        if (!SpeechRecognition) {
            btn.style.opacity = '1';
            btn.onclick = (event) => {
                event.preventDefault();
                focusInput();
            };
            return;
        }

        let recognition = null;
        let isListening = false;
        let isStarting = false;

        // Chrome sends speech to Google, which is unreachable from mainland China; say so instead of failing silently.
        const showMicHint = (errorCode) => {
            const hints = {
                network: ['Voice input can’t reach its speech service on this network. Please type, or try Safari.', '当前网络无法使用语音输入服务。请直接打字，或换用 Safari 浏览器。'],
                'service-not-allowed': ['Voice input isn’t available in this browser. Please type, or try Safari.', '此浏览器无法使用语音输入。请直接打字，或换用 Safari 浏览器。'],
                'not-allowed': ['Microphone access is blocked. Allow it in your browser settings, or type instead.', '麦克风权限被拒绝。请在浏览器设置中允许，或直接打字。'],
                'audio-capture': ['No microphone was found. Please type instead.', '没有检测到麦克风，请直接打字。'],
            };
            const hint = hints[errorCode];
            const textarea = document.querySelector('#chat-input-msg textarea');
            if (!hint || !textarea) return;
            const english = document.querySelector('input[type="radio"][value="English"]')?.checked;
            const original = textarea.placeholder;
            textarea.placeholder = english ? hint[0] : hint[1];
            setTimeout(() => { if (textarea.placeholder === (english ? hint[0] : hint[1])) textarea.placeholder = original; }, 7000);
        };

        btn.addEventListener('click', (event) => {
            event.preventDefault();

            if ((isListening || isStarting) && recognition) {
                isStarting = false;
                recognition.stop();
                return;
            }

            recognition = new SpeechRecognition();
            recognition.lang = document.querySelector('input[type="radio"][value="English"]')?.checked ? 'en-US' : 'zh-CN';
            recognition.continuous = false;
            recognition.interimResults = false;
            isStarting = true;
            setMicState(btn, true);

            recognition.onstart = () => {
                isStarting = false;
                isListening = true;
                setMicState(btn, true);
            };

            recognition.onresult = (resultEvent) => {
                const transcript = resultEvent.results[0][0].transcript;
                const textarea = document.querySelector('#chat-input-msg textarea');
                if (!textarea) return;
                textarea.value = textarea.value ? `${textarea.value} ${transcript}` : transcript;
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
            };

            recognition.onerror = (errorEvent) => {
                isStarting = false;
                isListening = false;
                setMicState(btn, false);
                showMicHint(errorEvent && errorEvent.error);
                focusInput();
            };

            recognition.onend = () => {
                isStarting = false;
                isListening = false;
                setMicState(btn, false);
                recognition = null;
            };

            try {
                recognition.start();
            } catch (error) {
                isStarting = false;
                isListening = false;
                setMicState(btn, false);
                recognition = null;
                focusInput();
            }
        });
    };

    const unlockTts = () => {
        if (!window.speechSynthesis) return;

        const prime = () => {
            try {
                const unlock = new SpeechSynthesisUtterance(' ');
                unlock.volume = 0;
                unlock.rate = 1;
                unlock.pitch = 1;
                unlock.lang = 'en-US';
                window.speechSynthesis.cancel();
                window.speechSynthesis.resume();
                window.speechSynthesis.speak(unlock);
                setTimeout(() => {
                    window.speechSynthesis.cancel();
                }, 80);
            } catch (error) {}
        };

        document.querySelectorAll('.send-btn-custom, #next-btn, #reset-btn, #custom-mic-btn, #chat-input-msg textarea, .module-card-btn').forEach((element) => {
            if (element.dataset.ttsPrimeBound === 'true') return;
            element.dataset.ttsPrimeBound = 'true';
            ['pointerdown', 'touchstart', 'click'].forEach((eventName) => {
                element.addEventListener(eventName, prime, { capture: true });
            });
        });
    };

    bindMic();
    unlockTts();
    setTimeout(() => {
        bindMic();
        unlockTts();
    }, 500);
}"""


__all__ = [
    "MODE_OPTIONS",
    "STAGE_NAMES",
    "UI",
    "css",
    "force_light_js",
    "global_viewport_style",
    "head",
    "scroll_js",
    "tts_js",
    "remember_lang_js",
]


# Closes the first-visit welcome card. Runs once when its HTML block loads; listens on the block, so it keeps working
# after the server fills the block in.
welcome_js = """
const close = () => {
    const layer = element.querySelector(".welcome-layer");
    if (layer) layer.style.display = "none";
};
element.addEventListener("click", (event) => {
    if (event.target.closest("[data-welcome-close]") || event.target.classList.contains("welcome-layer")) close();
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
});
"""
