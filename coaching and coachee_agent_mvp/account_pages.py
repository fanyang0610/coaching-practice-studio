"""Server-rendered pages around the coaching app: sign-in, invites, password resets, the account page,
transcript review for mentors and admins, and the admin console.

Mentors are people (role key "trainer"), such as coaching instructors, who review the practice of the members
assigned to them. Both coaching modules are always a member talking with the AI.

Pages are plain HTML forms so they work on any phone browser without JavaScript.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import html
import json
import logging
from pathlib import Path
import threading
from typing import Callable
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

import accounts
import db
import quota
from coaching_core import CoachingState
from web_assets import STAGE_NAMES


ROOT = Path(__file__).resolve().parent
LANG_COOKIE = "erickson_lang"

T = {
    "en": {
        "brand": "Coaching Practice Studio",
        "independent": "An independent, free practice tool. Not affiliated with any coaching school or certification body.",
        "back_to_app": "Back to coaching",
        "account": "Account",
        "trainer": "Mentor",
        "admin": "Admin",
        "privacy": "Privacy",
        "sign_in": "Sign in",
        "sign_out": "Sign out",
        "email": "Email",
        "password": "Password",
        "new_password": "New password",
        "confirm_password": "Confirm password",
        "current_password": "Current password",
        "your_name": "Your name",
        "invite_only": "Coaching Practice Studio is invite-only. Sign in with your email, or open the invite link you were sent.",
        "forgot": "Forgot your password? Ask your mentor or the admin for a reset link.",
        "forgot_link": "Forgot your password?",
        "forgot_title": "Reset your password",
        "forgot_hint": "Enter your account email. If it belongs to an account, we'll email a reset link that works for 2 hours.",
        "forgot_sent": "If that email belongs to an account, a reset link is on its way. Check your inbox and spam folder.",
        "send_link": "Email me a reset link",
        "reset_email_subject": "Reset your Coaching Practice Studio password",
        "reset_email_body": "Someone asked to reset the password for your Coaching Practice Studio account.\n\nTo choose a new password, open this link within 2 hours:\n{link}\n\nIf this wasn't you, ignore this email and your password stays the same.",
        "open_new_tab": "Signing in doesn't work inside an embedded page. Open Coaching Practice Studio in its own tab.",
        "bad_login": "That email and password don't match an active account.",
        "throttled": "Too many attempts. Please wait 15 minutes and try again.",
        "setup_title": "Create the first admin account",
        "setup_hint": "No accounts exist yet. This page is only available on this computer.",
        "create_account": "Create account",
        "signup_title": "Join Coaching Practice Studio",
        "signup_hint": "You were invited as {role}. Choose a password with at least {n} characters.",
        "invite_invalid": "This invite link has expired, was already used, or was revoked. Ask for a new one.",
        "email_taken": "An account with this email already exists. Sign in instead.",
        "email_mismatch": "This invite is for a different email address.",
        "password_too_short": "Passwords need at least {n} characters.",
        "password_mismatch": "The two passwords don't match.",
        "wrong_password": "Your current password isn't correct.",
        "consent": "I've read the privacy notice. I understand Coaching Practice Studio is coaching practice, not therapy or crisis support.",
        "consent_required": "Please confirm you've read the privacy notice.",
        "reset_title": "Set a new password",
        "reset_invalid": "This reset link has expired or was already used. Ask for a new one.",
        "save": "Save",
        "password_changed": "Password updated.",
        "my_sessions": "My sessions",
        "no_sessions": "No sessions yet.",
        "view": "View",
        "share": "Share with mentor",
        "unshare": "Stop sharing",
        "shared": "Shared",
        "private": "Private",
        "trainer_sees_practice": "Your mentor can review your Coachee Lab practice sessions. AI Coach sessions stay private unless you share them.",
        "no_trainer": "You don't have a mentor. Only you and the app admin can see your sessions.",
        "your_trainer": "Your mentor: {name}",
        "insights": "AI insights about you",
        "no_insights": "Finish an AI session to build insights.",
        "strengths": "Strengths",
        "growth": "Areas for challenge",
        "reset_insights": "Clear these insights",
        "insights_cleared": "Insights cleared.",
        "change_password": "Change password",
        "your_data": "Your data",
        "export": "Download my data (JSON)",
        "delete_account": "Delete my account",
        "delete_hint": "This permanently deletes your account, sessions and insights. Type DELETE to confirm.",
        "delete_confirm_wrong": "Type DELETE (in capitals) to confirm.",
        "last_admin": "You're the only admin. Make someone else an admin first.",
        "ai_left": "{module}: {left} of {limit} AI sessions left today",
        "ai_unlimited": "{module}: no daily AI limit",
        "module_coach": "AI Coach",
        "module_coachee": "AI Coachee Lab",
        "status_active": "In progress",
        "status_completed": "Completed",
        "status_abandoned": "Left early",
        "mode_template": "template",
        "turns": "{n} messages",
        "turns_one": "1 message",
        "transcript": "Transcript",
        "owner": "Participant",
        "not_allowed": "You don't have access to this session.",
        "not_found": "That page doesn't exist.",
        "client": "Client",
        "coach": "Coach",
        "ai_coach": "AI coach",
        "ai_coachee": "AI coachee",
        "trainees": "Members you mentor",
        "no_trainees": "No members are assigned to you yet. Create an invite to add one.",
        "trainee_sessions": "Sessions you can review",
        "invite_trainee": "Invite a member",
        "mentor_hint": "Mentors are people, such as coaching instructors, who review the practice of the members assigned to them: their Coachee Lab sessions, plus any AI Coach session a member chooses to share. The coaching itself is always between the member and the AI.",
        "invite_someone": "Create an invite",
        "invite_email_optional": "Email (optional: locks the invite to this address)",
        "role": "Role",
        "assign_trainer": "Mentor",
        "none": "None",
        "create_invite": "Create invite link",
        "invite_created": "Invite link (valid 14 days, one use). Send it to the person directly:",
        "invites": "Invites",
        "revoke": "Revoke",
        "used": "used",
        "expired": "expired",
        "revoked": "revoked",
        "open": "open",
        "users": "People",
        "status": "Status",
        "active": "active",
        "disabled": "disabled",
        "daily_sessions": "AI sessions per day (each module)",
        "allowances": "Daily AI allowances",
        "allowances_hint": "Per person, over a rolling 24 hours. Finished AI sessions count per module, and started ones are capped at twice that. Tokens are shared by both modules. Leave a field empty for no limit. Admins are never limited.",
        "coach_sessions": "AI Coach sessions",
        "coachee_sessions": "AI Coachee Lab sessions",
        "tokens_per_day": "Tokens",
        "allowances_saved": "Allowances saved.",
        "unlimited": "no limit",
        "daily_tokens": "Tokens per day",
        "default": "default",
        "update": "Update",
        "user_updated": "Saved.",
        "reset_link": "Create password reset link",
        "reset_created": "Password reset link for {name} (valid 48 hours, one use):",
        "tokens_24h": "{n} tokens in 24h",
        "recent_sessions": "Recent sessions",
        "audit": "Audit log",
        "storage_warning": "Data is stored in a temporary SQLite file on this server and will be lost on restart. Set DATABASE_URL to a Postgres database before inviting people.",
        "feedback_summary": "Feedback in the last 7 days: {up} helpful, {down} not helpful",
        "privacy_title": "Privacy and safety",
        "help": "Help",
        "help_eyebrow": "Getting started",
        "help_title": "How Coaching Practice Studio works",
        "help_intro": "A free place to be coached by AI, or to practise coaching an AI client. Here is everything you need for your first session.",
        "help_join_title": "Joining",
        "help_steps": [
            "Open the invite link you were sent. Each link works once and lasts 14 days.",
            "Enter your name, your email and a password of at least 10 characters. Tick the box, then tap Create account.",
            "You're in. Next time, sign in with your email and password at {address}",
            "Choose a mode at the top of the screen: AI Coach or AI Coachee Lab.",
        ],
        "help_modes_title": "The two modes",
        "help_coach_mode": "The AI coaches you on something real in your life: a goal, a decision or a challenge. These sessions are private to you.",
        "help_coachee_mode": "You practise being the coach. The AI plays a client with a realistic situation, and you ask the questions. At the end you get a score and feedback.",
        "help_session_title": "During a session",
        "help_session_items": [
            "A session moves through five stages: {stages}. The numbered dots near the top show where you are.",
            "Type your reply and tap Send, or tap the microphone to speak.",
            "Skip Ahead moves to the next stage. New Session starts over.",
            "A session takes about 15 to 20 minutes. If you leave halfway, it is saved and reopens the next time you sign in.",
            "Tap 👍 or 👎 under a reply to say whether it helped.",
            "Change the language or the reading voice under Settings.",
        ],
        "help_limits_title": "Daily allowance",
        "help_limits": "Each day (a rolling 24 hours) you have {coach} AI Coach sessions and {coachee} AI Coachee Lab sessions with the AI. If you use them up, you can keep practising with built-in questions until the AI is available again. Your Account page shows what is left.",
        "help_unlimited": "no limit",
        "help_faq_title": "Questions",
        "help_faq": [
            ["I forgot my password.", "Ask the person who invited you to send you a reset link."],
            ["Who can see my conversations?", "You and the app admin. If you have a mentor, they can see your AI Coachee Lab practice, plus any AI Coach session you choose to share. The privacy page has the details."],
            ["The microphone doesn't work.", "Voice input depends on your browser. Safari works well. In some regions Chrome's voice service is blocked. You can always type instead."],
            ["The page won't load.", "The server may be waking up: wait a minute, then refresh. If it still won't open, your network may be blocking the server. Try another network or a VPN."],
            ["Is this therapy?", "No. This is a coaching practice tool. If you are in crisis, contact your local emergency number, or find a free helpline at findahelpline.com."],
        ],
        "help_forgot_email": "Use \"Forgot your password?\" on the sign-in page, or ask the person who invited you.",
        "help_cta": "Go to sign in",
        "data_locations": "Where your data is processed: {where}",
        "privacy_body": [
            "Coaching Practice Studio is a coaching practice tool. It is not therapy, medical advice, or crisis support.",
            "If you might harm yourself or are in danger, contact your local emergency number now. You can find a free, confidential helpline in your country at findahelpline.com.",
            "What we store: your name, email, a hashed password, your coaching sessions (the full conversation), short AI-written insights about your coaching, your feedback on replies, and how many AI tokens you used.",
            "Who can read your sessions: you; the app admin; and your assigned mentor (a person, such as a coaching instructor), who can review your Coachee Lab practice sessions and any AI Coach session you choose to share. Every time someone other than you opens one of your sessions, it is recorded in an audit log.",
            "AI processing: your messages are sent to the configured AI model provider to generate replies.",
            "Your choices: you can download all your data or delete your account at any time from the Account page. Deleting removes your sessions and insights permanently.",
        ],
        "audit_actions": {
            "account_created": "Account created", "account_deleted": "Account deleted", "password_changed": "Password changed",
            "password_reset": "Password reset", "reset_link_created": "Reset link created", "reset_email_sent": "Reset email sent",
            "invite_created": "Invite created", "invite_revoked": "Invite revoked", "user_updated": "Person updated",
            "session_viewed": "Session viewed", "session_shared": "Session shared", "session_unshared": "Session unshared",
            "safety_flag": "Safety message shown", "limits_updated": "Allowances changed",
        },
    },
    "zh": {
        "brand": "教练练习室",
        "independent": "独立、免费的教练练习工具，与任何教练学校或认证机构均无关联。",
        "back_to_app": "返回教练对话",
        "account": "账户",
        "trainer": "导师",
        "admin": "管理",
        "privacy": "隐私",
        "sign_in": "登录",
        "sign_out": "退出登录",
        "email": "邮箱",
        "password": "密码",
        "new_password": "新密码",
        "confirm_password": "确认密码",
        "current_password": "当前密码",
        "your_name": "你的名字",
        "invite_only": "教练练习室仅限受邀用户。请用邮箱登录，或打开你收到的邀请链接。",
        "forgot": "忘记密码？请联系你的导师或管理员获取重置链接。",
        "forgot_link": "忘记密码？",
        "forgot_title": "重置密码",
        "forgot_hint": "请输入账户邮箱。如果该邮箱有账户，我们会发送一个 2 小时内有效的重置链接。",
        "forgot_sent": "如果该邮箱有账户，重置链接已经发出。请查看收件箱和垃圾邮件。",
        "send_link": "发送重置链接",
        "reset_email_subject": "重置你的教练练习室密码",
        "reset_email_body": "有人请求重置你的教练练习室账户密码。\n\n如需设置新密码，请在 2 小时内打开此链接：\n{link}\n\n如果不是你本人操作，请忽略此邮件，你的密码不会改变。",
        "open_new_tab": "嵌入页面中无法登录，请在新标签页中打开教练练习室。",
        "bad_login": "邮箱和密码与有效账户不匹配。",
        "throttled": "尝试次数过多，请 15 分钟后再试。",
        "setup_title": "创建第一个管理员账户",
        "setup_hint": "目前还没有任何账户。此页面只能在本机访问。",
        "create_account": "创建账户",
        "signup_title": "加入教练练习室",
        "signup_hint": "你受邀的身份是 {role}。请设置至少 {n} 位的密码。",
        "invite_invalid": "此邀请链接已过期、已被使用或已撤销，请重新申请。",
        "email_taken": "该邮箱已有账户，请直接登录。",
        "email_mismatch": "此邀请属于另一个邮箱地址。",
        "password_too_short": "密码至少需要 {n} 位。",
        "password_mismatch": "两次输入的密码不一致。",
        "wrong_password": "当前密码不正确。",
        "consent": "我已阅读隐私说明，并理解教练练习室是教练练习工具，不是心理治疗或危机援助。",
        "consent_required": "请确认你已阅读隐私说明。",
        "reset_title": "设置新密码",
        "reset_invalid": "此重置链接已过期或已被使用，请重新申请。",
        "save": "保存",
        "password_changed": "密码已更新。",
        "my_sessions": "我的会话",
        "no_sessions": "还没有会话。",
        "view": "查看",
        "share": "分享给导师",
        "unshare": "取消分享",
        "shared": "已分享",
        "private": "私密",
        "trainer_sees_practice": "你的导师可以查看你的 AI学员陪练 会话。AI教练 会话默认私密，除非你主动分享。",
        "no_trainer": "你还没有导师。只有你本人和应用管理员能看到你的会话。",
        "your_trainer": "你的导师：{name}",
        "insights": "AI 对你的洞察",
        "no_insights": "完成一次 AI 会话后会生成洞察。",
        "strengths": "强项",
        "growth": "建议挑战的领域",
        "reset_insights": "清除这些洞察",
        "insights_cleared": "洞察已清除。",
        "change_password": "修改密码",
        "your_data": "你的数据",
        "export": "下载我的数据（JSON）",
        "delete_account": "删除我的账户",
        "delete_hint": "这将永久删除你的账户、会话和洞察。请输入 DELETE 确认。",
        "delete_confirm_wrong": "请输入大写的 DELETE 确认。",
        "last_admin": "你是唯一的管理员，请先将其他人设为管理员。",
        "ai_left": "{module}：今日剩余 {left} / {limit} 次 AI 会话",
        "ai_unlimited": "{module}：AI 会话不限次数",
        "module_coach": "AI教练",
        "module_coachee": "AI学员陪练",
        "status_active": "进行中",
        "status_completed": "已完成",
        "status_abandoned": "中途离开",
        "mode_template": "模板",
        "turns": "{n} 条消息",
        "turns_one": "1 条消息",
        "transcript": "对话记录",
        "owner": "参与者",
        "not_allowed": "你没有权限查看此会话。",
        "not_found": "页面不存在。",
        "client": "来访者",
        "coach": "教练",
        "ai_coach": "AI教练",
        "ai_coachee": "AI学员",
        "trainees": "我指导的成员",
        "no_trainees": "还没有分配给你的成员，创建邀请来添加。",
        "trainee_sessions": "你可以查看的会话",
        "invite_trainee": "邀请成员",
        "mentor_hint": "导师是真实的人（例如教练课程讲师），负责查看分配给自己的成员的练习：他们的 AI学员陪练 会话，以及成员主动分享的 AI教练 会话。教练对话本身始终是成员与 AI 之间进行。",
        "invite_someone": "创建邀请",
        "invite_email_optional": "邮箱（可选：限定此邀请只能由该邮箱使用）",
        "role": "身份",
        "assign_trainer": "导师",
        "none": "无",
        "create_invite": "生成邀请链接",
        "invite_created": "邀请链接（14 天内有效，仅限一次）。请直接发给对方：",
        "invites": "邀请",
        "revoke": "撤销",
        "used": "已使用",
        "expired": "已过期",
        "revoked": "已撤销",
        "open": "可用",
        "users": "成员",
        "status": "状态",
        "active": "正常",
        "disabled": "已停用",
        "daily_sessions": "每日 AI 会话数（每个模块）",
        "allowances": "每日 AI 额度",
        "allowances_hint": "按每人、滚动 24 小时计算。已完成的 AI 会话按模块分别计数，开启的会话上限为其两倍。Token 由两个模块共用。留空表示不限。管理员不受限制。",
        "coach_sessions": "AI教练 会话",
        "coachee_sessions": "AI学员陪练 会话",
        "tokens_per_day": "Tokens",
        "allowances_saved": "额度已保存。",
        "unlimited": "不限",
        "daily_tokens": "每日 Token 数",
        "default": "默认",
        "update": "更新",
        "user_updated": "已保存。",
        "reset_link": "生成密码重置链接",
        "reset_created": "{name} 的密码重置链接（48 小时内有效，仅限一次）：",
        "tokens_24h": "24 小时内 {n} tokens",
        "recent_sessions": "最近的会话",
        "audit": "审计日志",
        "storage_warning": "数据目前存放在服务器上的临时 SQLite 文件中，重启后会丢失。邀请用户前请将 DATABASE_URL 设置为 Postgres 数据库。",
        "feedback_summary": "最近 7 天的反馈：{up} 有帮助，{down} 没帮助",
        "privacy_title": "隐私与安全",
        "help": "帮助",
        "help_eyebrow": "使用指南",
        "help_title": "教练练习室怎么用",
        "help_intro": "一个免费的地方：可以让 AI 为你做教练，也可以练习给 AI 学员做教练。下面是第一次使用需要知道的全部内容。",
        "help_join_title": "加入",
        "help_steps": [
            "打开你收到的邀请链接。每个链接只能使用一次，14 天内有效。",
            "填写名字、邮箱和至少 10 位的密码，勾选同意，然后点击“创建账户”。",
            "完成！以后请在这里用邮箱和密码登录：{address}",
            "在页面顶部选择模式：AI教练 或 AI学员陪练。",
        ],
        "help_modes_title": "两种模式",
        "help_coach_mode": "AI 针对你生活中的真实话题为你做教练：一个目标、一个决定或一个挑战。这些会话只有你自己能看到。",
        "help_coachee_mode": "你来练习做教练。AI 扮演一位有真实处境的来访者，由你来提问。结束后你会得到评分和反馈。",
        "help_session_title": "会话过程中",
        "help_session_items": [
            "一次会话会经历五个阶段：{stages}。页面上方带数字的圆点显示你当前所在的阶段。",
            "输入回复后点击“发送”，或点击麦克风用语音输入。",
            "“跳到下一阶段”会进入下一个阶段；“新会话”会重新开始。",
            "一次会话大约 15 到 20 分钟。中途离开也没关系，会话会被保存，下次登录时自动打开。",
            "在回复下方点 👍 或 👎，告诉我们这条回复是否有帮助。",
            "在“设置”里可以切换语言和朗读声音。",
        ],
        "help_limits_title": "每日额度",
        "help_limits": "每天（滚动 24 小时）你可以与 AI 进行 AI教练 会话 {coach} 次、AI学员陪练 会话 {coachee} 次。用完后仍可以用内置问题继续练习，直到 AI 恢复可用。账户页面会显示剩余次数。",
        "help_unlimited": "不限",
        "help_faq_title": "常见问题",
        "help_faq": [
            ["忘记密码怎么办？", "请联系邀请你的人，让他给你发送重置链接。"],
            ["谁能看到我的对话？", "你本人和应用管理员。如果你有导师，导师可以看到你的 AI学员陪练 练习，以及你主动分享的 AI教练 会话。详情见隐私页面。"],
            ["麦克风用不了。", "语音输入取决于你的浏览器。Safari 效果很好；在部分地区，Chrome 的语音服务无法使用。你随时可以改为打字。"],
            ["页面打不开。", "服务器可能正在唤醒：请等一分钟后刷新。如果仍然打不开，可能是你的网络无法访问服务器，请换一个网络或使用 VPN。"],
            ["这是心理治疗吗？", "不是。这是一个教练练习工具。如果你正处于危机中，请拨打当地紧急电话，或在 findahelpline.com 找到免费求助热线。"],
        ],
        "help_forgot_email": "可以在登录页点击“忘记密码？”，或联系邀请你的人。",
        "help_cta": "前往登录",
        "data_locations": "你的数据处理地点：{where}",
        "privacy_body": [
            "教练练习室是教练练习工具，不是心理治疗、医疗建议或危机援助。",
            "如果你可能伤害自己或正处于危险中，请立即拨打当地紧急电话。你可以在 findahelpline.com 找到你所在国家的免费保密求助热线。",
            "我们保存的内容：你的名字、邮箱、加密后的密码、你的教练会话（完整对话）、AI 生成的简短洞察、你对回复的反馈，以及你使用的 AI token 数。",
            "谁能看到你的会话：你本人；应用管理员；以及你的导师（真实的人，例如教练课程讲师）——导师可以查看你的 AI学员陪练 会话，以及你主动分享的 AI教练 会话。除你之外的任何人打开你的会话都会记录在审计日志中。",
            "AI 处理：你的消息会发送给配置的 AI 模型服务商以生成回复。",
            "你的选择：你可以随时在账户页面下载全部数据或删除账户。删除后，会话和洞察将被永久移除。",
        ],
        "audit_actions": {
            "account_created": "创建账户", "account_deleted": "删除账户", "password_changed": "修改密码",
            "password_reset": "重置密码", "reset_link_created": "生成重置链接", "reset_email_sent": "发送重置邮件",
            "invite_created": "创建邀请", "invite_revoked": "撤销邀请", "user_updated": "更新成员信息",
            "session_viewed": "查看会话", "session_shared": "分享会话", "session_unshared": "取消分享会话",
            "safety_flag": "显示安全提示", "limits_updated": "修改每日额度",
        },
    },
}

ROLE_LABELS = {
    "en": {"user": "member", "trainer": "mentor", "admin": "admin"},
    "zh": {"user": "成员", "trainer": "导师", "admin": "管理员"},
}

CSS = """
:root { --bg:#f3f8fd; --paper:#ffffff; --mist:#f8fbff; --tint:#eef5fb; --ink:#18364a; --muted:#62809a;
  --border:#d8e5f2; --blue:#1979ba; --blue-hover:#0f6aa8; --deep:#115488; --gold:#f0b95a; --warn:#8a3a26; }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:Manrope,system-ui,-apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
  font-size:16px; line-height:1.5; }
a { color:var(--blue); }
.shell { max-width:980px; margin:0 auto; padding:16px 16px max(24px, env(safe-area-inset-bottom)); }
.bar { display:flex; align-items:center; justify-content:space-between; gap:10px 16px; flex-wrap:wrap; background:var(--paper);
  border-radius:20px; padding:12px 16px; box-shadow:0 16px 36px rgba(17,73,119,0.10); margin-bottom:16px; }
.brand { display:flex; align-items:center; gap:10px; font-weight:800; color:var(--ink); text-decoration:none; }
.brand img { width:32px; height:32px; border-radius:10px; }
nav { display:flex; gap:6px; flex-wrap:wrap; }
nav a { color:var(--deep); text-decoration:none; font-weight:700; font-size:14px; padding:7px 12px; border-radius:12px;
  background:var(--mist); border:1px solid var(--border); }
nav a.current { background:var(--tint); border-color:#b9d3ea; }
.card { background:var(--paper); border-radius:20px; padding:20px; box-shadow:0 16px 36px rgba(17,73,119,0.10); margin-bottom:16px; }
.narrow { max-width:460px; margin:4vh auto 0; }
h1 { font-size:24px; font-weight:800; letter-spacing:-0.01em; line-height:1.2; margin:0 0 6px; }
h2 { font-size:18px; font-weight:800; line-height:1.25; margin:0 0 12px; }
.eyebrow { font-size:12px; font-weight:800; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); margin-bottom:4px; }
.muted, .hint { color:var(--muted); font-size:14px; }
label { display:block; font-weight:700; font-size:14px; margin:12px 0 6px; }
input[type=text], input[type=email], input[type=password], input[type=number], select {
  width:100%; min-height:44px; padding:10px 14px; border:1px solid var(--border); border-radius:14px; font:inherit;
  background:var(--paper); color:var(--ink); }
input:focus-visible, select:focus-visible, button:focus-visible, a:focus-visible { outline:3px solid rgba(25,121,186,0.35); outline-offset:2px; }
.check { display:flex; gap:10px; align-items:flex-start; font-weight:500; }
.check input { margin-top:4px; width:18px; height:18px; flex:0 0 auto; }
button, .button { display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:10px 18px;
  border-radius:14px; border:0; background:var(--blue); color:#fff; font:inherit; font-weight:800; cursor:pointer; text-decoration:none; }
button:hover, .button:hover { background:var(--blue-hover); }
button.secondary, .button.secondary { background:var(--mist); color:var(--deep); border:1px solid var(--border); }
button.quiet { min-height:36px; padding:6px 12px; font-size:14px; background:var(--mist); color:var(--deep); border:1px solid var(--border); }
button.danger { background:var(--paper); color:var(--warn); border:1px solid #e8c9bf; }
.full { width:100%; margin-top:18px; }
.flash { padding:12px 16px; border-radius:14px; margin-bottom:16px; font-weight:600; font-size:15px; }
.flash.ok, .flash.info { background:var(--tint); color:var(--deep); }
.flash.error { background:#fbefeb; color:var(--warn); }
.list { display:flex; flex-direction:column; gap:10px; }
.row { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px 14px; padding:12px 14px;
  border:1px solid var(--border); border-radius:16px; background:var(--mist); }
.row .main { min-width:0; flex:1 1 240px; }
.row .title { font-weight:700; overflow-wrap:anywhere; }
.row .meta { color:var(--muted); font-size:14px; overflow-wrap:anywhere; }
.pill { display:inline-block; font-size:12px; font-weight:800; padding:2px 10px; border-radius:999px; background:var(--tint); color:var(--deep); white-space:nowrap; }
.pill.gold { background:rgba(240,185,90,0.24); color:#7a5414; }
.actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
form.inline { display:inline; margin:0; }
.grid2 { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:16px; margin-bottom:16px; }
.grid2 > .card { margin-bottom:0; }
.fields { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:8px 12px; width:100%; }
.fields label { margin:0 0 4px; font-size:12px; color:var(--muted); }
.fields.three { grid-template-columns:repeat(3, minmax(0, 1fr)); }
code.link { display:block; word-break:break-all; background:var(--mist); border:1px solid var(--border); padding:10px 12px; border-radius:12px; font-size:13px; }
ul.tight { margin:6px 0 0; padding-left:1.2em; }
.steps { margin:0; padding-left:1.4em; }
.steps li { margin:8px 0; overflow-wrap:anywhere; }
.faq { padding:12px 0; border-top:1px solid var(--border); }
.faq:first-of-type { border-top:0; padding-top:0; }
.faq p { margin:4px 0 0; color:var(--muted); }
.transcript .msg { max-width:85%; padding:10px 14px; border-radius:16px; margin:10px 0; white-space:pre-wrap; overflow-wrap:anywhere; }
.msg.ai { background:var(--paper); border:1px solid var(--border); }
.msg.human { background:var(--tint); margin-left:auto; }
.msg .who { display:block; font-size:12px; font-weight:800; color:var(--muted); margin-bottom:2px; }
.lang { font-size:13px; color:var(--muted); text-align:center; margin-top:14px; }
.lang a { color:var(--muted); }
#frame-note { display:none; }
@media (max-width: 767px) {
  .shell { padding:12px 12px max(20px, env(safe-area-inset-bottom)); }
  .card { padding:16px; border-radius:18px; }
  .grid2 { grid-template-columns:minmax(0, 1fr); }
  .fields { grid-template-columns:repeat(2, minmax(0, 1fr)); }
  .fields.three { grid-template-columns:minmax(0, 1fr); }
  .transcript .msg { max-width:92%; }
}
"""


@dataclass
class PageSettings:
    secret: str
    secure_cookies: bool
    allow_local_setup: bool
    public_url: str = ""
    storage_warning: bool = False
    # send(to, subject, body); set when SMTP is configured, enabling self-service password resets.
    mailer: Callable[[str, str, str], None] | None = None
    # Plain-language note on where the server and AI provider process data, shown on the privacy page.
    data_locations: str = ""


def preferred_language(cookies, headers, fallback: str | None = "en") -> str | None:
    """The language a person last picked (shared by the app and these pages), else their browser's first language."""
    chosen = (cookies or {}).get(LANG_COOKIE)
    if chosen in ("en", "zh"):
        return chosen
    accept = ((headers or {}).get("accept-language") or "").strip().lower()
    if not accept:
        return fallback
    return "zh" if accept.startswith("zh") else "en"


def page_lang(request: Request) -> str:
    chosen = request.query_params.get("lang")
    return chosen if chosen in ("en", "zh") else preferred_language(request.cookies, request.headers)


def current_user(request: Request, store: db.Store, secret: str) -> dict | None:
    return accounts.read_session_cookie(request.cookies.get(accounts.SESSION_COOKIE), secret, store.get_user)


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def _time(value: dt.datetime | None) -> str:
    """A UTC timestamp as HTML; a small script on each page shows it in the reader's own time zone."""
    if not value:
        return ""
    return f'<time datetime="{value.isoformat()}Z">{value.strftime("%Y-%m-%d %H:%M")} UTC</time>'


LOCAL_TIME_JS = """<script>
document.querySelectorAll('time[datetime]').forEach(function (el) {
  var when = new Date(el.getAttribute('datetime'));
  if (!isNaN(when)) el.textContent = when.toLocaleString(document.documentElement.lang, {dateStyle: 'medium', timeStyle: 'short'});
});
</script>"""


def _send_quietly(mailer, to: str, subject: str, body: str) -> None:
    try:
        mailer(to, subject, body)
    except Exception:
        logging.getLogger("erickson_coach").exception("Sending email failed")


def _safe_next(target: str | None) -> str:
    return target if target and target.startswith("/") and not target.startswith("//") else "/"


def build_router(get_store: Callable[[], db.Store], settings: PageSettings) -> APIRouter:
    router = APIRouter()
    throttle = accounts.LoginThrottle()

    def text(lang: str, key: str, **values) -> str:
        values.setdefault("n", accounts.MIN_PASSWORD_LENGTH)
        return T[lang][key].format(**values)

    def base_url(request: Request) -> str:
        return (settings.public_url or str(request.base_url)).rstrip("/")

    def render(request: Request, lang: str, title: str, body: str, user: dict | None = None,
               flash: tuple[str, str] | None = None, status_code: int = 200, current: str = "") -> HTMLResponse:
        nav = ""
        if user:
            links = [("/", T[lang]["back_to_app"], "app"), ("/account", T[lang]["account"], "account")]
            if user["role"] in ("trainer", "admin"):
                links.append(("/mentor", T[lang]["trainer"], "trainer"))
            if user["role"] == "admin":
                links.append(("/admin", T[lang]["admin"], "admin"))
            nav = "<nav>" + "".join(
                f'<a href="{href}" class="{"current" if key == current else ""}">{_e(label)}</a>' for href, label, key in links
            ) + "</nav>"
        flash_html = f'<div class="flash {flash[0]}" role="status">{_e(flash[1])}</div>' if flash else ""
        other = "en" if lang == "zh" else "zh"
        switch = (f'<p class="lang"><a href="?lang={other}">{"English" if other == "en" else "中文"}</a> · '
                  f'<a href="/help">{_e(T[lang]["help"])}</a> · <a href="/privacy">{_e(T[lang]["privacy"])}</a></p>')
        page = f"""<!doctype html><html lang="{'zh-CN' if lang == 'zh' else 'en'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f3f8fd"><title>{_e(title)} · {_e(T[lang]['brand'])}</title>
<link rel="icon" type="image/png" href="/icons/studio-icon-192.png"><link rel="apple-touch-icon" href="/icons/studio-icon-180.png">
<style>{CSS}</style></head><body><main class="shell">
<header class="bar"><a class="brand" href="/"><img src="/icons/studio-icon-192.png" alt="">{_e(T[lang]['brand'])}</a>{nav}</header>
{flash_html}{body}{switch}</main>{LOCAL_TIME_JS}</body></html>"""
        response = HTMLResponse(page, status_code=status_code)
        if request.query_params.get("lang") in ("en", "zh"):
            response.set_cookie(LANG_COOKIE, lang, max_age=365 * 86400, samesite="lax", secure=settings.secure_cookies)
        return response

    def login_redirect(request: Request) -> RedirectResponse:
        return RedirectResponse("/login?next=" + quote(request.url.path), status_code=303)

    def set_login(response: Response, user: dict) -> Response:
        response.set_cookie(accounts.SESSION_COOKIE, accounts.make_session_cookie(user, settings.secret),
                            max_age=accounts.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                            secure=settings.secure_cookies)
        return response

    def csrf_field(request: Request) -> str:
        token = accounts.csrf_token(request.cookies.get(accounts.SESSION_COOKIE, ""), settings.secret)
        return f'<input type="hidden" name="csrf" value="{token}">'

    def checked_user(request: Request, csrf: str | None = None, roles: tuple[str, ...] = ()) -> dict | None:
        user = current_user(request, get_store(), settings.secret)
        if not user or (roles and user["role"] not in roles):
            return None
        if csrf is not None and not accounts.csrf_ok(request.cookies.get(accounts.SESSION_COOKIE), settings.secret, csrf):
            return None
        return user

    def forbidden(request: Request, lang: str, user: dict | None) -> HTMLResponse:
        return render(request, lang, T[lang]["not_allowed"], f'<div class="card"><h1>{_e(T[lang]["not_allowed"])}</h1></div>',
                      user=user, status_code=403)

    # Public assets -----------------------------------------------------------

    @router.get("/icons/{name}")
    def icon(name: str):
        path = ROOT / "assets" / "icons" / name
        if path.parent != ROOT / "assets" / "icons" or not path.is_file():
            return Response(status_code=404)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})

    @router.get("/site.webmanifest")
    def manifest():
        return FileResponse(ROOT / "site.webmanifest", media_type="application/manifest+json")

    @router.get("/healthz")
    def healthz():
        get_store().has_users()
        return {"ok": True}

    # Sign in and out ------------------------------------------------------------

    def login_form(request: Request, lang: str, email: str = "", flash=None, status_code: int = 200) -> HTMLResponse:
        next_path = _safe_next(request.query_params.get("next"))
        forgot = (f'<a href="/forgot">{_e(T[lang]["forgot_link"])}</a>' if settings.mailer else _e(T[lang]["forgot"]))
        body = f"""<div class="card narrow"><h1>{_e(T[lang]['sign_in'])}</h1><p class="hint">{_e(T[lang]['invite_only'])}</p>
<p id="frame-note" class="flash info"><a href="/login" target="_top">{_e(T[lang]['open_new_tab'])}</a></p>
<form method="post" action="/login?next={quote(next_path)}">
<label for="email">{_e(T[lang]['email'])}</label><input id="email" name="email" type="email" autocomplete="email" required value="{_e(email)}">
<label for="password">{_e(T[lang]['password'])}</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button class="full" type="submit">{_e(T[lang]['sign_in'])}</button></form>
<p class="hint">{forgot}</p><p class="hint">{_e(T[lang]['independent'])}</p></div>
<script>if (window.top !== window.self) document.getElementById('frame-note').style.display = 'block';</script>"""
        return render(request, lang, T[lang]["sign_in"], body, flash=flash, status_code=status_code)

    @router.get("/login")
    def login_page(request: Request):
        store = get_store()
        if settings.allow_local_setup and not store.has_users():
            return RedirectResponse("/setup", status_code=303)
        if current_user(request, store, settings.secret):
            return RedirectResponse(_safe_next(request.query_params.get("next")), status_code=303)
        return login_form(request, page_lang(request))

    @router.post("/login")
    def login_submit(request: Request, email: str = Form(""), password: str = Form("")):
        lang = page_lang(request)
        store = get_store()
        key = f"{email.strip().lower()}|{request.client.host if request.client else ''}"
        if throttle.blocked(key):
            return login_form(request, lang, email, ("error", T[lang]["throttled"]), 429)
        user = store.get_user_by_email(email)
        if not user or user["status"] != "active" or not accounts.verify_password(password, user["password_hash"]):
            throttle.failed(key)
            return login_form(request, lang, email, ("error", T[lang]["bad_login"]), 401)
        throttle.succeeded(key)
        return set_login(RedirectResponse(_safe_next(request.query_params.get("next")), status_code=303), user)

    @router.post("/logout")
    def logout(request: Request, csrf: str = Form("")):
        response = RedirectResponse("/login", status_code=303)
        if checked_user(request, csrf):
            response.delete_cookie(accounts.SESSION_COOKIE)
        return response

    # First admin (local only) -------------------------------------------------

    def setup_form(request, lang, flash=None, values=None) -> HTMLResponse:
        values = values or {}
        body = f"""<div class="card narrow"><h1>{_e(T[lang]['setup_title'])}</h1><p class="hint">{_e(T[lang]['setup_hint'])}</p>
<form method="post" action="/setup">
<label for="name">{_e(T[lang]['your_name'])}</label><input id="name" name="name" type="text" required value="{_e(values.get('name'))}">
<label for="email">{_e(T[lang]['email'])}</label><input id="email" name="email" type="email" required value="{_e(values.get('email'))}">
<label for="password">{_e(T[lang]['password'])}</label><input id="password" name="password" type="password" autocomplete="new-password" required>
<label for="confirm">{_e(T[lang]['confirm_password'])}</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required>
<button class="full" type="submit">{_e(T[lang]['create_account'])}</button></form></div>"""
        return render(request, lang, T[lang]["setup_title"], body, flash=flash)

    def setup_allowed() -> bool:
        return settings.allow_local_setup and not get_store().has_users()

    @router.get("/setup")
    def setup_page(request: Request):
        if not setup_allowed():
            return RedirectResponse("/login", status_code=303)
        return setup_form(request, page_lang(request))

    @router.post("/setup")
    def setup_submit(request: Request, name: str = Form(""), email: str = Form(""), password: str = Form(""), confirm: str = Form("")):
        lang = page_lang(request)
        if not setup_allowed():
            return RedirectResponse("/login", status_code=303)
        problem = accounts.password_problem(password, confirm)
        if problem:
            return setup_form(request, lang, ("error", text(lang, problem)), {"name": name, "email": email})
        store = get_store()
        user_id = store.create_user(email, name or email, accounts.hash_password(password), role="admin", consented=True)
        store.log(user_id, "account_created", target_user_id=user_id, detail="first admin (local setup)")
        return set_login(RedirectResponse("/", status_code=303), store.get_user(user_id))

    # Invite signup --------------------------------------------------------------

    def signup_form(request, lang, invite, flash=None, values=None) -> HTMLResponse:
        values = values or {}
        email = invite["email"] or values.get("email", "")
        email_attrs = "readonly" if invite["email"] else ""
        role = ROLE_LABELS[lang][invite["role"]]
        body = f"""<div class="card narrow"><h1>{_e(T[lang]['signup_title'])}</h1><p class="hint">{_e(text(lang, 'signup_hint', role=role))}</p>
<form method="post" action="/invite/{_e(invite['code'])}">
<label for="name">{_e(T[lang]['your_name'])}</label><input id="name" name="name" type="text" autocomplete="name" required value="{_e(values.get('name'))}">
<label for="email">{_e(T[lang]['email'])}</label><input id="email" name="email" type="email" autocomplete="email" required {email_attrs} value="{_e(email)}">
<label for="password">{_e(T[lang]['password'])}</label><input id="password" name="password" type="password" autocomplete="new-password" required>
<label for="confirm">{_e(T[lang]['confirm_password'])}</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required>
<label class="check"><input type="checkbox" name="consent" value="yes"><span>{_e(T[lang]['consent'])} <a href="/privacy" target="_blank">{_e(T[lang]['privacy'])}</a></span></label>
<button class="full" type="submit">{_e(T[lang]['create_account'])}</button></form>
<p class="hint">{_e(T[lang]['independent'])}</p></div>"""
        return render(request, lang, T[lang]["signup_title"], body, flash=flash)

    def invalid_invite(request, lang) -> HTMLResponse:
        body = f'<div class="card narrow"><h1>{_e(T[lang]["signup_title"])}</h1><p>{_e(T[lang]["invite_invalid"])}</p></div>'
        return render(request, lang, T[lang]["signup_title"], body, status_code=410)

    @router.get("/invite/{code}")
    def invite_page(request: Request, code: str):
        lang = page_lang(request)
        invite = get_store().usable_invite(code)
        return signup_form(request, lang, invite) if invite else invalid_invite(request, lang)

    @router.post("/invite/{code}")
    def invite_submit(request: Request, code: str, name: str = Form(""), email: str = Form(""), password: str = Form(""),
                      confirm: str = Form(""), consent: str = Form("")):
        lang = page_lang(request)
        store = get_store()
        invite = store.usable_invite(code)
        if not invite:
            return invalid_invite(request, lang)
        values = {"name": name, "email": email}
        email = (invite["email"] or email).strip().lower()
        if invite["email"] and email != invite["email"]:
            return signup_form(request, lang, invite, ("error", T[lang]["email_mismatch"]), values)
        problem = accounts.password_problem(password, confirm)
        if problem:
            return signup_form(request, lang, invite, ("error", text(lang, problem)), values)
        if consent != "yes":
            return signup_form(request, lang, invite, ("error", T[lang]["consent_required"]), values)
        if store.get_user_by_email(email):
            return signup_form(request, lang, invite, ("error", T[lang]["email_taken"]), values)
        if not store.consume_invite(code):
            return invalid_invite(request, lang)
        user_id = store.create_user(email, name or email.split("@")[0], accounts.hash_password(password),
                                    role=invite["role"], trainer_id=invite["trainer_id"], consented=True)
        store.log(invite["created_by"], "account_created", target_user_id=user_id, detail=f"invite {code[:6]}… as {invite['role']}")
        return set_login(RedirectResponse("/", status_code=303), store.get_user(user_id))

    # Forgot password (needs SMTP) ------------------------------------------------

    forgot_throttle = accounts.LoginThrottle(max_failures=5, window_seconds=900)

    def forgot_form(request: Request, lang: str, flash=None) -> HTMLResponse:
        body = f"""<div class="card narrow"><h1>{_e(T[lang]['forgot_title'])}</h1><p class="hint">{_e(T[lang]['forgot_hint'])}</p>
<form method="post" action="/forgot">
<label for="email">{_e(T[lang]['email'])}</label><input id="email" name="email" type="email" autocomplete="email" required>
<button class="full" type="submit">{_e(T[lang]['send_link'])}</button></form>
<p class="hint"><a href="/login">{_e(T[lang]['sign_in'])}</a></p></div>"""
        return render(request, lang, T[lang]["forgot_title"], body, flash=flash)

    @router.get("/forgot")
    def forgot_page(request: Request):
        if not settings.mailer:
            return RedirectResponse("/login", status_code=303)
        return forgot_form(request, page_lang(request))

    @router.post("/forgot")
    def forgot_submit(request: Request, email: str = Form("")):
        if not settings.mailer:
            return RedirectResponse("/login", status_code=303)
        lang = page_lang(request)
        key = f"{email.strip().lower()}|{request.client.host if request.client else ''}"
        if forgot_throttle.blocked(key):
            return forgot_form(request, lang, ("error", T[lang]["throttled"]))
        forgot_throttle.failed(key)
        store = get_store()
        user = store.get_user_by_email(email)
        if user and user["status"] == "active":
            link = f"{base_url(request)}/reset/{store.create_password_reset(user['id'], hours_valid=2)}"
            store.log(user["id"], "reset_email_sent", target_user_id=user["id"])
            # Send in the background so the reply time doesn't reveal whether the account exists.
            threading.Thread(target=_send_quietly, args=(settings.mailer, user["email"], T[lang]["reset_email_subject"],
                                                          T[lang]["reset_email_body"].format(link=link)), daemon=True).start()
        return forgot_form(request, lang, ("ok", T[lang]["forgot_sent"]))

    # Password reset -------------------------------------------------------------

    def reset_form(request, lang, token, flash=None) -> HTMLResponse:
        body = f"""<div class="card narrow"><h1>{_e(T[lang]['reset_title'])}</h1>
<form method="post" action="/reset/{_e(token)}">
<label for="password">{_e(T[lang]['new_password'])}</label><input id="password" name="password" type="password" autocomplete="new-password" required>
<label for="confirm">{_e(T[lang]['confirm_password'])}</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required>
<button class="full" type="submit">{_e(T[lang]['save'])}</button></form></div>"""
        return render(request, lang, T[lang]["reset_title"], body, flash=flash)

    @router.get("/reset/{token}")
    def reset_page(request: Request, token: str):
        lang = page_lang(request)
        if get_store().reset_user_id(token) is None:
            return render(request, lang, T[lang]["reset_title"],
                          f'<div class="card narrow"><h1>{_e(T[lang]["reset_title"])}</h1><p>{_e(T[lang]["reset_invalid"])}</p></div>',
                          status_code=410)
        return reset_form(request, lang, token)

    @router.post("/reset/{token}")
    def reset_submit(request: Request, token: str, password: str = Form(""), confirm: str = Form("")):
        lang = page_lang(request)
        store = get_store()
        problem = accounts.password_problem(password, confirm)
        if problem:
            return reset_form(request, lang, token, ("error", text(lang, problem)))
        user_id = store.consume_password_reset(token)
        if user_id is None:
            return reset_page(request, token)
        store.update_user(user_id, password_hash=accounts.hash_password(password))
        store.log(user_id, "password_reset", target_user_id=user_id)
        return set_login(RedirectResponse("/", status_code=303), store.get_user(user_id))

    # Help (public, so it can be sent along with an invite) --------------------

    @router.get("/help")
    def help_page(request: Request):
        lang = page_lang(request)
        store = get_store()
        user = current_user(request, store, settings.secret)
        limits = quota.role_limits(store)["user"]
        address = base_url(request)
        stages = " → ".join(STAGE_NAMES[lang][state] for state in CoachingState)

        def allowance(value):
            return T[lang]["help_unlimited"] if value is None else value

        steps = "".join(f"<li>{_e(step.format(address=address))}</li>" for step in T[lang]["help_steps"])
        session_items = "".join(f"<li>{_e(item.format(stages=stages))}</li>" for item in T[lang]["help_session_items"])
        faq_items = [list(item) for item in T[lang]["help_faq"]]
        if settings.mailer:
            faq_items[0][1] = T[lang]["help_forgot_email"]
        faq = "".join(f'<div class="faq"><b>{_e(question)}</b><p>{_e(answer)}</p></div>' for question, answer in faq_items)
        body = f"""<div class="card"><div class="eyebrow">{_e(T[lang]['help_eyebrow'])}</div><h1>{_e(T[lang]['help_title'])}</h1>
<p class="hint">{_e(T[lang]['help_intro'])}</p><p class="hint">{_e(T[lang]['independent'])}</p></div>
<div class="card"><h2>{_e(T[lang]['help_join_title'])}</h2><ol class="steps">{steps}</ol></div>
<div class="grid2"><div class="card"><h2>{_e(T[lang]['module_coach'])}</h2><p>{_e(T[lang]['help_coach_mode'])}</p></div>
<div class="card"><h2>{_e(T[lang]['module_coachee'])}</h2><p>{_e(T[lang]['help_coachee_mode'])}</p></div></div>
<div class="card"><h2>{_e(T[lang]['help_session_title'])}</h2><ul class="steps">{session_items}</ul></div>
<div class="card"><h2>{_e(T[lang]['help_limits_title'])}</h2><p>{_e(text(lang, 'help_limits', coach=allowance(limits['coach']), coachee=allowance(limits['coachee'])))}</p></div>
<div class="card"><h2>{_e(T[lang]['help_faq_title'])}</h2>{faq}</div>
{'' if user else f'<p><a class="button full" href="/login">{_e(T[lang]["help_cta"])}</a></p>'}"""
        return render(request, lang, T[lang]["help"], body, user=user)

    # Privacy --------------------------------------------------------------------

    @router.get("/privacy")
    def privacy(request: Request):
        lang = page_lang(request)
        user = current_user(request, get_store(), settings.secret)
        paragraphs = f"<p>{_e(T[lang]['independent'])}</p>" + "".join(f"<p>{_e(line)}</p>" for line in T[lang]["privacy_body"])
        if settings.data_locations:
            paragraphs += f'<p><b>{_e(text(lang, "data_locations", where=settings.data_locations))}</b></p>'
        body = f'<div class="card"><h1>{_e(T[lang]["privacy_title"])}</h1>{paragraphs}</div>'
        return render(request, lang, T[lang]["privacy_title"], body, user=user)

    # Account --------------------------------------------------------------------

    def session_row(lang: str, row: dict, *, owner_name: str | None = None, share_form: str = "", link: bool = True) -> str:
        module = T[lang]["module_coachee" if row["module"] == "coachee" else "module_coach"]
        status = T[lang].get(f"status_{row['status']}", row["status"])
        stage = STAGE_NAMES[lang].get(CoachingState[row["stage"]], row["stage"]) if row["stage"] in CoachingState.__members__ else ""
        bits = [text(lang, "turns_one" if row["user_turns"] == 1 else "turns", n=row["user_turns"])]
        if row["mode"] == "template":
            bits.append(T[lang]["mode_template"])
        title = f"{_e(owner_name)} · {_e(module)}" if owner_name else _e(module)
        shared = ""
        if row["module"] == "coach":
            shared = f'<span class="pill{" gold" if row["shared_with_trainer"] else ""}">{_e(T[lang]["shared" if row["shared_with_trainer"] else "private"])}</span>'
        return f"""<div class="row"><div class="main"><div class="title">{title} <span class="pill">{_e(status)}</span> {shared}</div>
<div class="meta">{_e(stage)} · {_time(row["created_at"])} · {_e(' · '.join(bits))}</div></div>
<div class="actions">{share_form}{f'<a class="button secondary" href="/sessions/{_e(row["id"])}">{_e(T[lang]["view"])}</a>' if link else ''}</div></div>"""

    def profile_block(lang: str, module: str, data: dict | None, request: Request) -> str:
        heading = T[lang]["module_coachee" if module == "coachee" else "module_coach"]
        if not data or not (data.get("strengths") or data.get("growth_areas")):
            return f'<div><div class="eyebrow">{_e(heading)}</div><p class="muted">{_e(T[lang]["no_insights"])}</p></div>'
        strengths = "".join(f"<li>{_e(item)}</li>" for item in data.get("strengths", []))
        growth = "".join(f"<li>{_e(item)}</li>" for item in data.get("growth_areas", []))
        return f"""<div><div class="eyebrow">{_e(heading)}</div>
<b>{_e(T[lang]['strengths'])}</b><ul class="tight">{strengths}</ul>
<b>{_e(T[lang]['growth'])}</b><ul class="tight">{growth}</ul>
<form method="post" action="/account/profile/reset" class="inline">{csrf_field(request)}<input type="hidden" name="module" value="{module}">
<button class="quiet" type="submit">{_e(T[lang]['reset_insights'])}</button></form></div>"""

    def account_page(request: Request, user: dict, flash=None) -> HTMLResponse:
        lang = page_lang(request)
        store = get_store()
        quota_lines = []
        for module in quota.MODULES:
            allowance = quota.allowance(store, user, module)
            name = T[lang]["module_coachee" if module == "coachee" else "module_coach"]
            if allowance.session_limit is None:
                quota_lines.append(text(lang, "ai_unlimited", module=name))
            else:
                quota_lines.append(text(lang, "ai_left", module=name, left=allowance.sessions_left, limit=allowance.session_limit))
        trainer = store.get_user(user["trainer_id"]) if user["trainer_id"] else None
        trainer_line = text(lang, "your_trainer", name=trainer["display_name"]) if trainer else T[lang]["no_trainer"]
        rows = []
        for row in store.list_sessions(user["id"]):
            share_form = ""
            if row["module"] == "coach" and trainer:
                label = T[lang]["unshare" if row["shared_with_trainer"] else "share"]
                share_form = (f'<form method="post" action="/account/sessions/{_e(row["id"])}/share" class="inline">{csrf_field(request)}'
                              f'<input type="hidden" name="shared" value="{"no" if row["shared_with_trainer"] else "yes"}">'
                              f'<button class="quiet" type="submit">{_e(label)}</button></form>')
            rows.append(session_row(lang, row, share_form=share_form))
        sessions_html = "".join(rows) or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'
        body = f"""<div class="card"><div class="eyebrow">{_e(ROLE_LABELS[lang][user['role']])}</div><h1>{_e(user['display_name'])}</h1>
<p class="muted">{_e(user['email'])}<br>{'<br>'.join(_e(line) for line in quota_lines)}</p><p class="hint">{_e(trainer_line)}<br>{_e(T[lang]['trainer_sees_practice'])}</p>
<form method="post" action="/logout" class="inline">{csrf_field(request)}<button class="secondary" type="submit">{_e(T[lang]['sign_out'])}</button></form></div>
<div class="card"><h2>{_e(T[lang]['my_sessions'])}</h2><div class="list">{sessions_html}</div></div>
<div class="card"><h2>{_e(T[lang]['insights'])}</h2><div class="grid2">
{profile_block(lang, 'coach', store.get_profile(user['id'], 'coach'), request)}
{profile_block(lang, 'coachee', store.get_profile(user['id'], 'coachee'), request)}</div></div>
<div class="grid2"><div class="card"><h2>{_e(T[lang]['change_password'])}</h2>
<form method="post" action="/account/password">{csrf_field(request)}
<label for="current">{_e(T[lang]['current_password'])}</label><input id="current" name="current" type="password" autocomplete="current-password" required>
<label for="password">{_e(T[lang]['new_password'])}</label><input id="password" name="password" type="password" autocomplete="new-password" required>
<label for="confirm">{_e(T[lang]['confirm_password'])}</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required>
<button class="full" type="submit">{_e(T[lang]['save'])}</button></form></div>
<div class="card"><h2>{_e(T[lang]['your_data'])}</h2><p><a class="button secondary" href="/account/export">{_e(T[lang]['export'])}</a></p>
<form method="post" action="/account/delete">{csrf_field(request)}<p class="hint">{_e(T[lang]['delete_hint'])}</p>
<input name="confirm" type="text" autocomplete="off" aria-label="DELETE">
<button class="danger full" type="submit">{_e(T[lang]['delete_account'])}</button></form></div></div>"""
        return render(request, lang, T[lang]["account"], body, user=user, flash=flash, current="account")

    @router.get("/account")
    def account(request: Request):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        flash_key = request.query_params.get("done")
        flash = ("ok", T[page_lang(request)][flash_key]) if flash_key in ("password_changed", "insights_cleared") else None
        return account_page(request, user, flash)

    @router.post("/account/password")
    def change_password(request: Request, csrf: str = Form(""), current: str = Form(""), password: str = Form(""), confirm: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        if not accounts.verify_password(current, user["password_hash"]):
            return account_page(request, user, ("error", T[lang]["wrong_password"]))
        problem = accounts.password_problem(password, confirm)
        if problem:
            return account_page(request, user, ("error", text(lang, problem)))
        store = get_store()
        store.update_user(user["id"], password_hash=accounts.hash_password(password))
        store.log(user["id"], "password_changed", target_user_id=user["id"])
        return set_login(RedirectResponse("/account?done=password_changed", status_code=303), store.get_user(user["id"]))

    @router.post("/account/profile/reset")
    def reset_profile(request: Request, csrf: str = Form(""), module: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        if module in ("coach", "coachee"):
            get_store().save_profile(user["id"], module, {})
        return RedirectResponse("/account?done=insights_cleared", status_code=303)

    @router.post("/account/sessions/{session_id}/share")
    def share_session(request: Request, session_id: str, csrf: str = Form(""), shared: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        store = get_store()
        row = store.get_session(session_id)
        if not row or row["user_id"] != user["id"] or row["module"] != "coach":
            return forbidden(request, page_lang(request), user)
        store.set_session_shared(session_id, shared == "yes")
        store.log(user["id"], "session_shared" if shared == "yes" else "session_unshared", target_session_id=session_id)
        return RedirectResponse("/account", status_code=303)

    @router.get("/account/export")
    def export(request: Request):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        data = json.dumps(get_store().export_user(user["id"]), ensure_ascii=False, indent=2, default=str)
        return Response(data, media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="coaching-practice-studio-data.json"'})

    @router.post("/account/delete")
    def delete_account(request: Request, csrf: str = Form(""), confirm: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        store = get_store()
        if confirm.strip() != "DELETE":
            return account_page(request, user, ("error", T[lang]["delete_confirm_wrong"]))
        if user["role"] == "admin" and store.count_admins() <= 1:
            return account_page(request, user, ("error", T[lang]["last_admin"]))
        store.delete_user(user["id"])
        store.log(user["id"], "account_deleted", target_user_id=user["id"])
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(accounts.SESSION_COOKIE)
        return response

    # Transcript review ----------------------------------------------------------

    @router.get("/sessions/{session_id}")
    def transcript(request: Request, session_id: str):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        store = get_store()
        row = store.get_session(session_id)
        owner = store.get_user(row["user_id"]) if row else None
        if not row or not accounts.can_view_session(user, row, owner):
            return forbidden(request, lang, user)
        if user["id"] != row["user_id"]:
            store.log(user["id"], "session_viewed", target_user_id=row["user_id"], target_session_id=session_id)
        state = json.loads(row["state"])
        is_practice = row["module"] == "coachee"
        ai_role = "coachee" if is_practice else "coach"
        human_label = T[lang]["coach" if is_practice else "client"]
        ai_label = T[lang]["ai_coachee" if is_practice else "ai_coach"]
        verdicts = store.feedback_for_session(session_id)
        bubbles = []
        for index, message in enumerate(state.get("context", [])):
            is_ai = message.get("role") == ai_role
            verdict = verdicts.get(index)
            mark = f' <span class="pill{" gold" if verdict == "dislike" else ""}">{"👍" if verdict == "like" else "👎"}</span>' if verdict else ""
            bubbles.append(f'<div class="msg {"ai" if is_ai else "human"}"><span class="who">{_e(ai_label if is_ai else human_label)}{mark}</span>{_e(message.get("content"))}</div>')
        owner_line = f'{_e(T[lang]["owner"])}: {_e(owner["display_name"])} · ' if owner and owner["id"] != user["id"] else ""
        body = f"""<div class="card"><div class="eyebrow">{_e(T[lang]['transcript'])}</div>
{session_row(lang, row, link=False)}<p class="muted">{owner_line}{_time(row['updated_at'])}</p>
<div class="transcript">{''.join(bubbles) or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'}</div></div>"""
        return render(request, lang, T[lang]["transcript"], body, user=user)

    # Mentor (role key "trainer") -----------------------------------------------------

    def invite_form(request: Request, lang: str, action: str, *, roles: tuple[str, ...], trainers: list[dict]) -> str:
        role_options = "".join(f'<option value="{role}">{_e(ROLE_LABELS[lang][role])}</option>' for role in roles)
        trainer_select = ""
        if trainers:
            options = f'<option value="">{_e(T[lang]["none"])}</option>' + "".join(
                f'<option value="{t["id"]}">{_e(t["display_name"])}</option>' for t in trainers)
            trainer_select = f'<label for="trainer_id">{_e(T[lang]["assign_trainer"])}</label><select id="trainer_id" name="trainer_id">{options}</select>'
        role_select = (f'<label for="role">{_e(T[lang]["role"])}</label><select id="role" name="role">{role_options}</select>'
                       if len(roles) > 1 else f'<input type="hidden" name="role" value="{roles[0]}">')
        return f"""<form method="post" action="{action}">{csrf_field(request)}
<label for="invite_email">{_e(T[lang]['invite_email_optional'])}</label><input id="invite_email" name="email" type="email">
{role_select}{trainer_select}<button class="full" type="submit">{_e(T[lang]['create_invite'])}</button></form>"""

    def created_link(lang: str, key: str, link: str, **values) -> str:
        return f'<div class="flash ok">{_e(text(lang, key, **values))}<code class="link">{_e(link)}</code></div>'

    def trainer_page(request: Request, user: dict, extra: str = "") -> HTMLResponse:
        lang = page_lang(request)
        store = get_store()
        trainees = store.trainees(user["id"])
        since = db.utcnow() - dt.timedelta(hours=24)
        usage = store.usage_by_user_since(since)
        trainee_rows = "".join(
            f'<div class="row"><div class="main"><div class="title">{_e(t["display_name"])}</div>'
            f'<div class="meta">{_e(t["email"])} · {_e(text(lang, "tokens_24h", n=usage.get(t["id"], 0)))}</div></div></div>'
            for t in trainees) or f'<p class="muted">{_e(T[lang]["no_trainees"])}</p>'
        sessions = "".join(session_row(lang, row, owner_name=row["owner_name"]) for row in store.trainer_visible_sessions(user["id"]))
        body = f"""{extra}<p class="flash info">{_e(T[lang]['mentor_hint'])}</p>
<div class="grid2"><div class="card"><h2>{_e(T[lang]['trainees'])}</h2><div class="list">{trainee_rows}</div></div>
<div class="card"><h2>{_e(T[lang]['invite_trainee'])}</h2>{invite_form(request, lang, '/mentor/invites', roles=('user',), trainers=[])}</div></div>
<div class="card"><h2>{_e(T[lang]['trainee_sessions'])}</h2><div class="list">{sessions or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'}</div></div>"""
        return render(request, lang, T[lang]["trainer"], body, user=user, current="trainer")

    @router.get("/mentor")
    def trainer(request: Request):
        user = checked_user(request, roles=("trainer", "admin"))
        return trainer_page(request, user) if user else login_redirect(request)

    @router.post("/mentor/invites")
    def trainer_invite(request: Request, csrf: str = Form(""), email: str = Form("")):
        user = checked_user(request, csrf, roles=("trainer", "admin"))
        if not user:
            return login_redirect(request)
        store = get_store()
        code = store.create_invite(user["id"], role="user", trainer_id=user["id"], email=email or None)
        store.log(user["id"], "invite_created", detail=f"user invite {code[:6]}…")
        lang = page_lang(request)
        return trainer_page(request, user, created_link(lang, "invite_created", f"{base_url(request)}/invite/{code}"))

    # Admin --------------------------------------------------------------------------

    def admin_page(request: Request, user: dict, extra: str = "") -> HTMLResponse:
        lang = page_lang(request)
        store = get_store()
        now = db.utcnow()
        people = store.list_users()
        trainers = [p for p in people if p["role"] in ("trainer", "admin")]
        usage = store.usage_by_user_since(now - dt.timedelta(hours=24))
        names = {p["id"]: p["display_name"] for p in people}
        csrf = csrf_field(request)

        def option_list(options, selected) -> str:
            return "".join(f'<option value="{_e(value)}"{" selected" if str(value) == str(selected) else ""}>{_e(label)}</option>'
                           for value, label in options)

        user_rows = []
        for person in people:
            roles = option_list([(r, ROLE_LABELS[lang][r]) for r in accounts.ROLES], person["role"])
            trainer_opts = option_list([("", T[lang]["none"])] + [(t["id"], t["display_name"]) for t in trainers if t["id"] != person["id"]],
                                       person["trainer_id"] or "")
            statuses = option_list([("active", T[lang]["active"]), ("disabled", T[lang]["disabled"])], person["status"])
            meta = f'{person["email"]} · {text(lang, "tokens_24h", n=usage.get(person["id"], 0))}'
            if person["trainer_id"]:
                meta += f' · {T[lang]["assign_trainer"]}: {names.get(person["trainer_id"], "?")}'
            user_rows.append(f"""<div class="row"><div class="main"><div class="title">{_e(person['display_name'])}
<span class="pill">{_e(ROLE_LABELS[lang][person['role']])}</span>{'' if person['status'] == 'active' else f' <span class="pill gold">{_e(T[lang]["disabled"])}</span>'}</div>
<div class="meta">{_e(meta)}</div>
<form method="post" action="/admin/users/{person['id']}">{csrf}<div class="fields">
<div><label>{_e(T[lang]['role'])}</label><select name="role">{roles}</select></div>
<div><label>{_e(T[lang]['assign_trainer'])}</label><select name="trainer_id">{trainer_opts}</select></div>
<div><label>{_e(T[lang]['status'])}</label><select name="status">{statuses}</select></div>
<div><label>{_e(T[lang]['daily_sessions'])}</label><input type="number" min="0" name="daily_session_limit" placeholder="{_e(T[lang]['default'])}" value="{_e(person['daily_session_limit'] if person['daily_session_limit'] is not None else '')}"></div>
<div><label>{_e(T[lang]['daily_tokens'])}</label><input type="number" min="0" step="1000" name="daily_token_limit" placeholder="{_e(T[lang]['default'])}" value="{_e(person['daily_token_limit'] if person['daily_token_limit'] is not None else '')}"></div>
</div><div class="actions" style="margin-top:10px"><button class="quiet" type="submit">{_e(T[lang]['update'])}</button></form>
<form method="post" action="/admin/users/{person['id']}/reset-link" class="inline">{csrf}<button class="quiet" type="submit">{_e(T[lang]['reset_link'])}</button></form></div></div></div>""")

        invite_rows = []
        for invite in store.list_invites()[:50]:
            if invite["revoked"]:
                state = T[lang]["revoked"]
            elif invite["uses"] >= invite["max_uses"]:
                state = T[lang]["used"]
            elif invite["expires_at"] < now:
                state = T[lang]["expired"]
            else:
                state = T[lang]["open"]
            revoke = ""
            if state == T[lang]["open"]:
                revoke = (f'<form method="post" action="/admin/invites/{_e(invite["code"])}/revoke" class="inline">{csrf}'
                          f'<button class="quiet" type="submit">{_e(T[lang]["revoke"])}</button></form>')
            invite_rows.append(f"""<div class="row"><div class="main"><div class="title">{_e(invite['email'] or '—')} <span class="pill">{_e(ROLE_LABELS[lang][invite['role']])}</span> <span class="pill">{_e(state)}</span></div>
<div class="meta">{_e(invite['code'][:6])}… · {_time(invite['created_at'])}{(' · ' + _e(T[lang]['assign_trainer']) + ': ' + _e(names.get(invite['trainer_id'], '?'))) if invite['trainer_id'] else ''}</div></div>
<div class="actions">{revoke}</div></div>""")

        audit_rows = "".join(
            f'<div class="row"><div class="main"><div class="title">{_e(T[lang]["audit_actions"].get(entry["action"], entry["action"]))}</div><div class="meta">{_time(entry["created_at"])} · '
            f'{_e(names.get(entry["actor_id"], entry["actor_id"] or "system"))}'
            f'{(" → " + _e(names.get(entry["target_user_id"], entry["target_user_id"]))) if entry["target_user_id"] else ""}'
            f'{(" · " + _e(entry["target_session_id"][:8])) if entry["target_session_id"] else ""}'
            f'{(" · " + _e(entry["detail"])) if entry["detail"] else ""}</div></div></div>'
            for entry in store.audit_entries(60))
        limits = quota.role_limits(store)
        allowance_forms = "".join(f"""<form method="post" action="/admin/allowances" class="row">{csrf}<input type="hidden" name="role" value="{role}">
<div class="main"><div class="title">{_e(ROLE_LABELS[lang][role])}</div><div class="fields three">
<div><label>{_e(T[lang]['coach_sessions'])}</label><input type="number" min="0" name="coach" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['coach'] is None else limits[role]['coach'])}"></div>
<div><label>{_e(T[lang]['coachee_sessions'])}</label><input type="number" min="0" name="coachee" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['coachee'] is None else limits[role]['coachee'])}"></div>
<div><label>{_e(T[lang]['tokens_per_day'])}</label><input type="number" min="0" step="1000" name="tokens" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['tokens'] is None else limits[role]['tokens'])}"></div>
</div></div><div class="actions"><button class="quiet" type="submit">{_e(T[lang]['update'])}</button></div></form>""" for role in ("user", "trainer"))
        votes = store.feedback_totals_since(now - dt.timedelta(days=7))
        warning = f'<div class="flash error">{_e(T[lang]["storage_warning"])}</div>' if settings.storage_warning else ""
        body = f"""{warning}{extra}<div class="grid2"><div class="card"><h2>{_e(T[lang]['invite_someone'])}</h2>
{invite_form(request, lang, '/admin/invites', roles=accounts.ROLES, trainers=trainers)}</div>
<div class="card"><h2>{_e(T[lang]['invites'])}</h2><div class="list">{''.join(invite_rows) or '<p class="muted">—</p>'}</div></div></div>
<div class="card"><h2>{_e(T[lang]['allowances'])}</h2><p class="hint">{_e(T[lang]['allowances_hint'])}</p><div class="list">{allowance_forms}</div></div>
<div class="card"><h2>{_e(T[lang]['users'])}</h2><p class="muted">{_e(text(lang, 'feedback_summary', up=votes.get('like', 0), down=votes.get('dislike', 0)))}</p><div class="list">{''.join(user_rows)}</div></div>
<div class="card"><h2>{_e(T[lang]['recent_sessions'])}</h2><div class="list">{''.join(session_row(lang, row, owner_name=row['owner_name']) for row in store.recent_sessions(60)) or '<p class="muted">—</p>'}</div></div>
<div class="card"><h2>{_e(T[lang]['audit'])}</h2><div class="list">{audit_rows or '<p class="muted">—</p>'}</div></div>"""
        return render(request, lang, T[lang]["admin"], body, user=user, current="admin")

    @router.get("/admin")
    def admin(request: Request):
        user = checked_user(request, roles=("admin",))
        return admin_page(request, user) if user else login_redirect(request)

    @router.post("/admin/invites")
    def admin_invite(request: Request, csrf: str = Form(""), email: str = Form(""), role: str = Form("user"), trainer_id: str = Form("")):
        user = checked_user(request, csrf, roles=("admin",))
        if not user:
            return login_redirect(request)
        role = role if role in accounts.ROLES else "user"
        store = get_store()
        code = store.create_invite(user["id"], role=role, trainer_id=int(trainer_id) if trainer_id.isdigit() else None, email=email or None)
        store.log(user["id"], "invite_created", detail=f"{role} invite {code[:6]}…")
        lang = page_lang(request)
        return admin_page(request, user, created_link(lang, "invite_created", f"{base_url(request)}/invite/{code}"))

    @router.post("/admin/allowances")
    def admin_allowances(request: Request, csrf: str = Form(""), role: str = Form(""), coach: str = Form(""),
                         coachee: str = Form(""), tokens: str = Form("")):
        admin_user = checked_user(request, csrf, roles=("admin",))
        if not admin_user:
            return login_redirect(request)
        lang = page_lang(request)
        if role in ("user", "trainer"):
            values = [int(v) if v.strip().isdigit() else None for v in (coach, coachee, tokens)]
            store = get_store()
            quota.save_role_limits(store, role, *values)
            store.log(admin_user["id"], "limits_updated", detail=f"{role}: coach={values[0]} coachee={values[1]} tokens={values[2]}")
        return admin_page(request, admin_user, f'<div class="flash ok">{_e(T[lang]["allowances_saved"])}</div>')

    @router.post("/admin/invites/{code}/revoke")
    def admin_revoke(request: Request, code: str, csrf: str = Form("")):
        user = checked_user(request, csrf, roles=("admin",))
        if not user:
            return login_redirect(request)
        store = get_store()
        store.revoke_invite(code)
        store.log(user["id"], "invite_revoked", detail=f"{code[:6]}…")
        return RedirectResponse("/admin", status_code=303)

    @router.post("/admin/users/{user_id}")
    def admin_update_user(request: Request, user_id: int, csrf: str = Form(""), role: str = Form(""), trainer_id: str = Form(""),
                          status: str = Form(""), daily_session_limit: str = Form(""), daily_token_limit: str = Form("")):
        admin_user = checked_user(request, csrf, roles=("admin",))
        if not admin_user:
            return login_redirect(request)
        lang = page_lang(request)
        store = get_store()
        target = store.get_user(user_id)
        if not target:
            return forbidden(request, lang, admin_user)
        fields = {
            "role": role if role in accounts.ROLES else target["role"],
            "trainer_id": int(trainer_id) if trainer_id.isdigit() and int(trainer_id) != user_id else None,
            "status": status if status in ("active", "disabled") else target["status"],
            "daily_session_limit": int(daily_session_limit) if daily_session_limit.strip().isdigit() else None,
            "daily_token_limit": int(daily_token_limit) if daily_token_limit.strip().isdigit() else None,
        }
        losing_admin = target["role"] == "admin" and target["status"] == "active" and (fields["role"] != "admin" or fields["status"] != "active")
        if losing_admin and store.count_admins() <= 1:
            return admin_page(request, admin_user, f'<div class="flash error">{_e(T[lang]["last_admin"])}</div>')
        store.update_user(user_id, **fields)
        changes = ", ".join(f"{key}={value}" for key, value in fields.items() if target[key] != value)
        store.log(admin_user["id"], "user_updated", target_user_id=user_id, detail=changes)
        return admin_page(request, admin_user, f'<div class="flash ok">{_e(T[lang]["user_updated"])}</div>')

    @router.post("/admin/users/{user_id}/reset-link")
    def admin_reset_link(request: Request, user_id: int, csrf: str = Form("")):
        admin_user = checked_user(request, csrf, roles=("admin",))
        if not admin_user:
            return login_redirect(request)
        lang = page_lang(request)
        store = get_store()
        target = store.get_user(user_id)
        if not target:
            return forbidden(request, lang, admin_user)
        token = store.create_password_reset(user_id)
        store.log(admin_user["id"], "reset_link_created", target_user_id=user_id)
        return admin_page(request, admin_user, created_link(lang, "reset_created", f"{base_url(request)}/reset/{token}", name=target["display_name"]))

    return router
