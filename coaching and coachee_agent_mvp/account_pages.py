"""Server-rendered pages around the coaching app: sign-in, invites, password resets, the account page,
transcript review for members and their mentors, and the admin console.

Admins manage people, invites and allowances, and see when sessions happen, but never what was said.

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
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy.exc import SQLAlchemyError

import accounts
import db
import quota
from coaching_core import CoachingState, ai_failure_detail
from coachee_agent import can_retry_review
from coach_agent import ACTION_CARD_FIELDS, can_recover_action_card
from studio_config import LANG_COOKIE, LEGACY_LANG_COOKIE
from memory import MAX_INSIGHT_CHARS, MAX_PRACTICE_GOAL_CHARS, PROFILE_FIELDS, UserProfile, change_insight, profile_items, profile_version
from web_assets import STAGE_NAMES, tts_js


ROOT = Path(__file__).resolve().parent
T = {
    "en": {
        "brand": "Coaching Practice Studio",
        "independent": "An independent, free practice tool. Not affiliated with any coaching school or certification body.",
        "back_to_app": "Back to coaching",
        "account": "Account",
        "account_settings": "Account settings",
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
        "signup_failed": "We couldn't create your account. Your invite is still available. Please try again.",
        "password_too_short": "Passwords need at least {n} characters.",
        "password_mismatch": "The two passwords don't match.",
        "wrong_password": "Your current password isn't correct.",
        "consent": "I've read the privacy notice. I understand Coaching Practice Studio is coaching practice, not therapy or crisis support.",
        "consent_required": "Please confirm you've read the privacy notice.",
        "reset_title": "Set a new password",
        "reset_invalid": "This reset link has expired or was already used. Ask for a new one.",
        "reset_failed": "We couldn't save the new password. Please try this link again.",
        "save": "Save",
        "password_changed": "Password updated.",
        "my_sessions": "My sessions",
        "no_sessions": "No sessions yet.",
        "view": "View",
        "share": "Share with mentor",
        "unshare": "Stop sharing",
        "delete_session": "Delete",
        "delete_session_confirm": "Delete this conversation for good? Its action card or practice score goes with it.",
        "session_deleted": "The conversation was deleted.",
        "shared": "Shared",
        "private": "Private",
        "trainer_sees_practice": "Your mentor can review your Coachee Lab practice sessions. AI Coach sessions stay private unless you share them.",
        "trainer_changed": "Your mentor has changed. Review the current mentor before sharing.",
        "no_trainer": "You don't have a mentor. Only you can see your sessions.",
        "your_trainer": "Your mentor: {name}",
        "history_earlier": "Earlier records",
        "history_newer": "Newer records",
        "history_page": "Page {page} of {pages}",
        "history_pages": "Session history pages",
        "action_cards": "Your action cards",
        "no_action_cards": "Finish an AI Coach session to get an action card with your goal and next step.",
        "practice_scores": "Practice scores",
        "no_scores": "Finish an AI Coachee Lab session to see your scores here.",
        "score": "{n}/100",
        "card_goal": "Goal",
        "card_next_step": "Next step",
        "card_by_when": "By when",
        "card_support": "Support",
        "insights": "AI insights about you",
        "no_insights": "Finish an AI session to build insights.",
        "strengths": "Strengths",
        "growth": "Areas for challenge",
        "reset_insights": "Clear these insights",
        "insights_cleared": "Insights cleared.",
        "edit_insight": "Edit insight",
        "remove_insight": "Remove",
        "insight_saved": "Insight updated.",
        "insight_removed": "Insight removed.",
        "insight_failed": "Could not save this change. Your saved insights are unchanged. Please try again.",
        "insight_conflict": "These insights changed elsewhere. Check the current content before trying again.",
        "insight_invalid": "Use a non-empty insight of up to 2,000 characters, different from the other items in this section.",
        "insight_hint": "Your edits are kept for future practice. Removed wording won't be added back automatically; similar wording may still appear as a new observation.",
        "coaching_style_insights": "Approach",
        "client_coaching_style_insights": "Conversation observations",
        "client_strengths": "Resources you described",
        "client_growth_areas": "Questions to explore",
        "learning_patterns": "Learning patterns",
        "growth_areas": "Areas for challenge",
        "cancel_insight": "Back to insights",
        "practice_goal": "Next practice goal",
        "practice_goal_hint": "Choose one coaching skill to practise. You can edit or clear it at any time. It will be used to prepare your next AI Client case.",
        "practice_goal_choose": "Choose from practice insights (optional)",
        "practice_goal_manual": "Write your own",
        "practice_goal_clear": "Clear goal",
        "practice_goal_saved": "Practice goal saved.",
        "practice_goal_cleared": "Practice goal cleared.",
        "practice_goal_invalid": "Keep the goal within 300 characters, or leave it empty to clear it.",
        "practice_goal_failed": "Could not save. Your saved goal is unchanged; your draft is below. Please try again.",
        "practice_goal_conflict": "The saved information changed elsewhere. Check your current goal and try saving your draft again.",
        "practice_goal_current": "Saved goal",
        "practice_goal_empty": "No goal set",
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
        "retry_review": "Regenerate review",
        "retry_failed": "The AI still couldn’t write your review. You can try again.",
        "retry_busy": "A review may already be in progress. Refresh in a moment.",
        "retry_saved": "Your practice review is ready.",
        "recover_card": "Recover action card",
        "card_history": "View this conversation and recover its action card",
        "card_unknown": "No action card is saved for this conversation. You can recover it from the original dialogue.",
        "card_none": "No action card was extracted from this conversation.",
        "card_generation_failed": "The action card could not be generated. Your conversation is saved; you can try again here.",
        "card_save_failed": "The action card could not be saved. Your conversation is kept; you can try again here.",
        "card_pending": "The action card is being generated. Refresh in a moment.",
        "card_interrupted": "The last action card attempt was interrupted. You can try again.",
        "card_busy": "This record changed or recovery is already in progress. Refresh to see the latest result.",
        "card_saved": "Your action card is saved.",
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
        "invite_created": "Invite link (valid {days} days, one use). Send it to the person directly:",
        "invite_created_group": "Group invite link (valid {days} days, for up to {uses} people). Share it only with that group:",
        "invite_uses": "How many people can use it",
        "invite_days": "Valid for (days)",
        "invite_group_hint": "For a group, such as a WeChat group, raise the number of people. Anyone with the link can join until it is used up or expires, so share it only with that group.",
        "invite_uses_left": "{used} of {max} used",
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
        "recent_sessions_hint": "To protect privacy, the admin sees when sessions happen, how long they are and how useful people rated them, not what was said.",
        "ratings_summary": "How useful people found their sessions in the last 30 days: {parts}",
        "ratings_part": "{module} {average}/5 ({count} rated)",
        "ratings_none": "no ratings yet",
        "rating_pill": "Useful {rating}/5",
        "audit": "Audit log",
        "storage_warning": "Data is stored in a temporary SQLite file on this server and will be lost on restart. Set DATABASE_URL to a Postgres database before inviting people.",
        "ai_service": "AI service",
        "ai_credit_left": "Credit left on the AI account (OpenRouter): ${amount}.",
        "ai_credit_low": "AI credit is running low: ${amount} left. When it runs out, nobody can start a session. Top up at openrouter.ai under Settings → Credits.",
        "ai_errors": "AI requests failed in the last 24 hours ({count}, counted at most once a minute). Latest:",
        "ai_errors_none": "No AI errors in the last 24 hours.",
        "ai_errors_hint": "402 means the credit is used up, 401 that the API key is wrong, and 429 that the AI service was too busy.",
        "feedback_summary": "Feedback in the last 7 days: {up} helpful, {down} not helpful",
        "privacy_title": "Privacy and safety",
        "help": "Help",
        "help_eyebrow": "Getting started",
        "help_title": "How Coaching Practice Studio works",
        "help_intro": "A free place to be coached by AI, or to practise coaching an AI client. Here is everything you need for your first session.",
        "help_join_title": "Joining",
        "help_steps": [
            "Open the invite link you were sent. Invite links expire, usually after 14 days, so use yours soon.",
            "Enter your name, your email and a password of at least 10 characters. Tick the box, then tap Create account.",
            "You're in. Next time, sign in with your email and password at {address}",
            "Choose at the top of the screen: Be coached (AI Coach), or Practise coaching (AI Coachee Lab).",
        ],
        "help_modes_title": "The two modes",
        "help_coach_mode": "The AI coaches you on something real in your life: a goal, a decision or a challenge. Sessions are private by default. You can share individual sessions with your mentor from Account.",
        "help_coachee_mode": "You practise being the coach. The AI plays a client with a realistic situation, and you ask the questions. At the end you get a score and feedback. Want a different topic? Before your first question, describe the client's situation and tap \"Use my topic\".",
        "help_session_title": "During a session",
        "help_session_items": [
            "A session moves through five stages: {stages}. The numbered dots near the top show where you are; a dashed dot is a stage that was skipped.",
            "Type your reply and tap Send, or tap the microphone to speak.",
            "Skip Ahead moves to the next stage. New Session starts over in the current mode.",
            "Each mode saves its own conversation. Switch modes to pick up where you left off. When you return to the app, it opens the last mode you used.",
            "If you commit to a next step in an AI Coach session, it can appear in an action card on your Account page. If generating or saving the card fails, open that session to try again.",
            "Your AI Coachee Lab scores are kept on your Account page. If a review fails, open that practice record and choose Regenerate review.",
            "Tap 👍 or 👎 under a reply to say whether it helped.",
            "Choose your language or turn on Auto-play replies under Settings.",
        ],
        "help_limits_title": "Daily allowance",
        "help_limits": "Each day (a rolling 24 hours) you have {coach} AI Coach sessions and {coachee} AI Coachee Lab sessions with the AI. When one runs out, the app tells you roughly when you can start again, and the other mode may still have sessions left. Your Account page shows what is left. One conversation can have up to {messages} of your messages; when {warning} are left, the app counts them down, and the last one ends the conversation with its feedback.",
        "help_unlimited": "no limit",
        "help_faq_title": "Questions",
        "voices_link": "Read-aloud voices: hear the voice your device will use",
        "voices_title": "Read-aloud voices",
        "voices_intro": "Read-aloud uses the voices your browser and device already have, so there is nothing to install. The app picks a voice for the conversation language. Tap Listen to hear it.",
        "voices_iphone": "On iPhone and iPad, websites can only use Apple's basic voices (voices downloaded in the Settings app aren't available to them), so read-aloud sounds plain there.",
        "voices_online_note": "Online voice. If it can't be reached (in mainland China without a VPN, for one), the device's own voice is used.",
        "voices_choice": "The voices on this device",
        "voices_all": "Chinese and English voices in this browser ({n})",
        "voices_listen": "Listen",
        "voices_none": "This browser offers no read-aloud voices.",
        "voices_device": "on this device",
        "voices_online": "online",
        "voices_default": "the browser's default voice",
        "voices_loading": "Checking…",
        "help_faq": [
            ["I forgot my password.", "Ask the person who invited you to send you a reset link."],
            ["Who can see my conversations?", "Only you. If you have a mentor, they can see your AI Coachee Lab practice, plus any AI Coach session you choose to share. The app admin can't open your conversations. The privacy page has the details."],
            ["The microphone doesn't work.", "Voice input depends on your browser. Safari works well. In some regions Chrome's voice service is blocked. You can always type instead."],
            ["The read-aloud voice sounds robotic.", "Read-aloud uses the voices your browser offers, and the app picks the best one. On iPhone and iPad, browsers only let websites use Apple's basic voices (voices you download in the device's Settings app aren't available to websites), so read-aloud sounds plain there. On a computer, Chrome has Google's more natural voices (they don't work in mainland China without a VPN; the app then uses the computer's own voice). The Read-aloud voices page below lets you hear the voice your device will use."],
            ["The page won't load.", "The server may be waking up: wait a minute, then refresh. If it still won't open, your network may be blocking the server. Try another network or a VPN."],
            ["Is this therapy?", "No. This is a coaching practice tool. If you are in crisis, call your local emergency number. In mainland China, call 12356 (the national psychological help line), or 120 or 110 in an emergency. Elsewhere, findahelpline.com lists free helplines."],
        ],
        "help_forgot_email": "Use \"Forgot your password?\" on the sign-in page, or ask the person who invited you.",
        "help_contact_q": "Something isn't working, or I have an idea.",
        "help_contact_a": "Get in touch: {contact}. A screenshot and the time it happened help a lot.",
        "help_cta": "Go to sign in",
        "data_locations": "Where your data is processed: {where}",
        "privacy_body": [
            "Coaching Practice Studio is a coaching practice tool. It is not therapy, medical advice, or crisis support.",
            "If you might harm yourself or are in danger, contact your local emergency number now (in mainland China: 120 or 110). In mainland China you can also call 12356, the national psychological help line. Elsewhere, findahelpline.com lists free, confidential helplines in your country.",
            "What we store: your name, email, a hashed password, your coaching sessions (the full conversation), the action cards and practice scores they produce, short AI-written insights about your coaching, your feedback on replies, how useful you rated each session, and how many AI tokens you used.",
            "Who can read your sessions: you, and your assigned mentor (a person, such as a coaching instructor), who can review your Coachee Lab practice sessions and any AI Coach session you choose to share. The app admin manages accounts and daily allowances and can see when your sessions happen, how long they are and how useful you rated them, but can't open what was said. Every time someone other than you opens one of your sessions, it is recorded in an audit log.",
            "Storage and AI processing: your conversations are stored on the app's server, and your messages are sent to the configured AI model provider to generate replies. The app gives the admin no way to read them, but as with any online service, whoever runs the server and the AI provider handle this data.",
            "Your choices: you can download all your data or delete your account at any time from the Account page. Deleting removes your sessions and insights permanently.",
        ],
        "audit_actions": {
            "account_created": "Account created", "account_deleted": "Account deleted", "password_changed": "Password changed",
            "password_reset": "Password reset", "reset_link_created": "Reset link created", "reset_email_sent": "Reset email sent",
            "invite_created": "Invite created", "invite_revoked": "Invite revoked", "user_updated": "Person updated",
            "session_viewed": "Session viewed", "session_shared": "Session shared", "session_unshared": "Session unshared", "session_deleted": "Session deleted",
            "safety_flag": "Safety message shown", "limits_updated": "Allowances changed", "ai_error": "AI request failed",
        },
    },
    "zh": {
        "brand": "教练练习室",
        "independent": "独立、免费的教练练习工具，与任何教练学校或认证机构均无关联。",
        "back_to_app": "返回教练对话",
        "account": "账户",
        "account_settings": "账户设置",
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
        "signup_failed": "未能创建账户。你的邀请仍可使用，请重试。",
        "password_too_short": "密码至少需要 {n} 位。",
        "password_mismatch": "两次输入的密码不一致。",
        "wrong_password": "当前密码不正确。",
        "consent": "我已阅读隐私说明，并理解教练练习室是教练练习工具，不是心理治疗或危机援助。",
        "consent_required": "请确认你已阅读隐私说明。",
        "reset_title": "设置新密码",
        "reset_invalid": "此重置链接已过期或已被使用，请重新申请。",
        "reset_failed": "未能保存新密码，请使用此链接重试。",
        "save": "保存",
        "password_changed": "密码已更新。",
        "my_sessions": "我的会话",
        "no_sessions": "还没有会话。",
        "view": "查看",
        "share": "分享给导师",
        "unshare": "取消分享",
        "delete_session": "删除",
        "delete_session_confirm": "要永久删除这段对话吗？它的行动卡或练习得分也会一起删除。",
        "session_deleted": "这段对话已删除。",
        "shared": "已分享",
        "private": "私密",
        "trainer_sees_practice": "你的导师可以查看你的 AI学员陪练 会话。AI教练 会话默认私密，除非你主动分享。",
        "trainer_changed": "你的导师已变更。请先确认当前导师，再决定是否分享。",
        "no_trainer": "你还没有导师。只有你本人能看到你的会话。",
        "your_trainer": "你的导师：{name}",
        "history_earlier": "更早记录",
        "history_newer": "较新记录",
        "history_page": "第 {page} / {pages} 页",
        "history_pages": "会话历史翻页",
        "action_cards": "你的行动卡",
        "no_action_cards": "完成一次 AI教练 会话，就会得到一张写有目标和下一步的行动卡。",
        "practice_scores": "练习得分",
        "no_scores": "完成一次 AI学员陪练 会话后，得分会显示在这里。",
        "score": "{n}/100",
        "card_goal": "目标",
        "card_next_step": "下一步",
        "card_by_when": "时间",
        "card_support": "支持",
        "insights": "AI 对你的洞察",
        "no_insights": "完成一次 AI 会话后会生成洞察。",
        "strengths": "强项",
        "growth": "建议挑战的领域",
        "reset_insights": "清除这些洞察",
        "insights_cleared": "洞察已清除。",
        "edit_insight": "编辑洞察",
        "remove_insight": "移除",
        "insight_saved": "洞察已更新。",
        "insight_removed": "洞察已移除。",
        "insight_failed": "未能保存这次修改，已保存的洞察保持不变，请重试。",
        "insight_conflict": "洞察已在别处改动，请核对当前内容后重试。",
        "insight_invalid": "请输入不超过 2,000 字符的非空洞察，且不要与同类其他条目重复。",
        "insight_hint": "你的修改会保留供后续练习使用。已移除的原文不会自动加回，近义表述仍可能作为新观察出现。",
        "coaching_style_insights": "思考方式",
        "client_coaching_style_insights": "会话观察",
        "client_strengths": "表达过的资源",
        "client_growth_areas": "仍想探索的问题",
        "learning_patterns": "学习方式",
        "growth_areas": "挑战方向",
        "cancel_insight": "返回洞察",
        "practice_goal": "下次练习目标",
        "practice_goal_hint": "选一个想练习的教练技能，可随时编辑或清空。它会用于准备下次 AI 来访者案例。",
        "practice_goal_choose": "从练习洞察选取（可选）",
        "practice_goal_manual": "自行输入",
        "practice_goal_clear": "清空目标",
        "practice_goal_saved": "练习目标已保存。",
        "practice_goal_cleared": "练习目标已清空。",
        "practice_goal_invalid": "目标请保持在 300 字符以内，留空可清空目标。",
        "practice_goal_failed": "未能保存，已保存目标保持不变；草稿保留在下方，请重试。",
        "practice_goal_conflict": "编辑期间已保存的信息发生了变化。请核对当前目标，再保存下方草稿。",
        "practice_goal_current": "已保存目标",
        "practice_goal_empty": "尚未设置目标",
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
        "retry_review": "重新生成点评",
        "retry_failed": "AI 暂时还是没能写出点评，可以再试一次。",
        "retry_busy": "可能正在生成点评，请稍后刷新。",
        "retry_saved": "本次练习的点评已生成。",
        "recover_card": "恢复行动卡",
        "card_history": "查看本次历史记录并恢复行动卡",
        "card_unknown": "这次会话尚未保存行动卡，可以从原始对话恢复。",
        "card_none": "这次对话未提取到行动卡。",
        "card_generation_failed": "行动卡生成失败。对话已保存，可以在这里重试。",
        "card_save_failed": "行动卡保存失败。原对话已保留，可以在这里重试。",
        "card_pending": "正在生成行动卡，请稍后刷新。",
        "card_interrupted": "上次行动卡生成中断，可以重试。",
        "card_busy": "记录已更新，或正在恢复行动卡。请刷新查看最新结果。",
        "card_saved": "行动卡已保存。",
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
        "invite_created": "邀请链接（{days} 天内有效，仅限一次）。请直接发给对方：",
        "invite_created_group": "群组邀请链接（{days} 天内有效，最多 {uses} 人使用）。请只发给这个群：",
        "invite_uses": "可使用人数",
        "invite_days": "有效天数",
        "invite_group_hint": "如果要发到群里（例如微信群），请调高可使用人数。任何拿到链接的人都能加入，直到人数用完或链接过期，所以请只发给这个群。",
        "invite_uses_left": "已使用 {used}/{max}",
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
        "recent_sessions_hint": "为保护隐私，管理员只能看到会话的时间、长度和用户给出的帮助程度评分，看不到对话内容。",
        "ratings_summary": "最近 30 天用户对会话帮助程度的评分：{parts}",
        "ratings_part": "{module} {average}/5（{count} 个评分）",
        "ratings_none": "还没有评分",
        "rating_pill": "帮助 {rating}/5",
        "audit": "审计日志",
        "storage_warning": "数据目前存放在服务器上的临时 SQLite 文件中，重启后会丢失。邀请用户前请将 DATABASE_URL 设置为 Postgres 数据库。",
        "ai_service": "AI 服务",
        "ai_credit_left": "AI 账户（OpenRouter）剩余额度：${amount}。",
        "ai_credit_low": "AI 额度快用完了：还剩 ${amount}。用完后谁都无法开始新会话。请到 openrouter.ai 的 Settings → Credits 充值。",
        "ai_errors": "过去 24 小时有 AI 请求失败（{count} 次，每分钟最多记一次）。最近一次：",
        "ai_errors_none": "过去 24 小时没有 AI 错误。",
        "ai_errors_hint": "402 表示额度已用完，401 表示 API 密钥有误，429 表示 AI 服务太忙。",
        "feedback_summary": "最近 7 天的反馈：{up} 有帮助，{down} 没帮助",
        "privacy_title": "隐私与安全",
        "help": "帮助",
        "help_eyebrow": "使用指南",
        "help_title": "教练练习室怎么用",
        "help_intro": "一个免费的地方：可以让 AI 为你做教练，也可以练习给 AI 学员做教练。下面是第一次使用需要知道的全部内容。",
        "help_join_title": "加入",
        "help_steps": [
            "打开你收到的邀请链接。邀请链接有有效期（通常 14 天），请尽快使用。",
            "填写名字、邮箱和至少 10 位的密码，勾选同意，然后点击“创建账户”。",
            "完成！以后请在这里用邮箱和密码登录：{address}",
            "在页面顶部选择：被教练（AI教练），或练习做教练（AI学员陪练）。",
        ],
        "help_modes_title": "两种模式",
        "help_coach_mode": "AI 针对你生活中的真实话题为你做教练，例如一个目标、一个决定或一个挑战。会话默认仅自己可见，你也可以在账户页把单次会话分享给导师。",
        "help_coachee_mode": "你来练习做教练。AI 扮演一位有真实处境的来访者，由你来提问。结束后你会得到评分和反馈。想练别的话题？在提出第一个问题之前，写下来访者的情况，再点“用我的话题”。",
        "help_session_title": "会话过程中",
        "help_session_items": [
            "一次会话会经历五个阶段：{stages}。页面上方带数字的圆点显示你当前所在的阶段，虚线圆点表示跳过的阶段。",
            "输入回复后点击“发送”，或点击麦克风用语音输入。",
            "“跳到下一阶段”会进入下一个阶段。“新会话”会在当前模式重新开始。",
            "两种模式各自保存对话，切回去就能接着聊。重新打开练习室时，会先进入上次使用的模式。",
            "如果你在 AI 教练会话中明确了下一步，账户页可能会显示一张行动卡。生成或保存失败时，可以打开那次会话重试。",
            "AI 学员陪练的得分会保存在账户页面。如果点评生成失败，打开那次练习记录，点“重新生成点评”。",
            "在回复下方点 👍 或 👎，告诉我们这条回复是否有帮助。",
            "在“设置”里可以切换语言，也可以开启“自动朗读回复”。",
        ],
        "help_limits_title": "每日额度",
        "help_limits": "每天（滚动 24 小时）你可以与 AI 进行 AI教练 会话 {coach} 次、AI学员陪练 会话 {coachee} 次。某一项用完后，页面会告诉你大约多久之后可以再开始；另一项如果还有剩余，仍然可以使用。账户页面会显示剩余次数。每次对话最多可以发 {messages} 条消息；还剩 {warning} 条时，应用会提醒你还剩几条，发完最后一条后对话结束，并给出反馈。",
        "help_unlimited": "不限",
        "help_faq_title": "常见问题",
        "voices_link": "朗读声音：试听你的设备会用的声音",
        "voices_title": "朗读声音",
        "voices_intro": "朗读使用的是浏览器和设备自带的声音，不需要安装任何东西。应用会按对话语言自动选择声音。点“试听”可以听一听。",
        "voices_iphone": "在 iPhone 和 iPad 上，网页只能使用苹果的基础声音（在“设置”App 里下载的声音，网页用不了），所以朗读听起来比较平淡。",
        "voices_online_note": "在线声音。连不上时（例如在中国大陆不用 VPN），会改用设备自带的声音。",
        "voices_choice": "这台设备会用的声音",
        "voices_all": "这个浏览器里的中文和英文声音（{n} 个）",
        "voices_listen": "试听",
        "voices_none": "这个浏览器没有提供朗读声音。",
        "voices_device": "设备上",
        "voices_online": "在线",
        "voices_default": "浏览器默认声音",
        "voices_loading": "检查中…",
        "help_faq": [
            ["忘记密码怎么办？", "请联系邀请你的人，让对方给你发送重置链接。"],
            ["谁能看到我的对话？", "只有你本人。如果你有导师，导师可以看到你的 AI学员陪练 练习，以及你主动分享的 AI教练 会话。应用管理员无法打开你的对话。详情见隐私页面。"],
            ["麦克风用不了。", "语音输入取决于你的浏览器。Safari 效果很好；在部分地区，Chrome 的语音服务无法使用。你随时可以改为打字。"],
            ["朗读的声音很机械。", "朗读使用的是浏览器提供的声音，应用会自动选出其中最好的一个。在 iPhone 和 iPad 上，浏览器只允许网页使用苹果的基础声音（在手机“设置”App 里下载的声音，网页用不了），所以朗读听起来比较平淡。电脑上的 Chrome 带有 Google 的声音，听起来更自然（在中国大陆不用 VPN 时无法使用，应用会自动改用电脑自带的声音）。下面的“朗读声音”页面可以试听你的设备会用的声音。"],
            ["页面打不开。", "服务器可能正在唤醒：请等一分钟后刷新。如果仍然打不开，可能是你的网络无法访问服务器，请换一个网络或使用 VPN。"],
            ["这是心理治疗吗？", "不是。这是一个教练练习工具。如果你正处于危机中，请拨打当地紧急电话。在中国大陆，可拨打全国统一心理援助热线 12356，紧急情况请拨打 120 或 110。其他国家和地区可在 findahelpline.com 找到免费求助热线。"],
        ],
        "help_forgot_email": "可以在登录页点击“忘记密码？”，或联系邀请你的人。",
        "help_contact_q": "遇到问题，或者有建议？",
        "help_contact_a": "请联系：{contact}。附上截图和发生的时间会很有帮助。",
        "help_cta": "前往登录",
        "data_locations": "你的数据处理地点：{where}",
        "privacy_body": [
            "教练练习室是教练练习工具，不是心理治疗、医疗建议或危机援助。",
            "如果你可能伤害自己或正处于危险中，请立即拨打当地紧急电话（中国大陆：120 或 110）。在中国大陆，你也可以拨打全国统一心理援助热线 12356。其他国家和地区可在 findahelpline.com 找到当地免费、保密的求助热线。",
            "我们保存的内容：你的名字、邮箱、加密后的密码、你的教练会话（完整对话）、会话产生的行动卡和练习得分、AI 生成的简短洞察、你对回复的反馈、你对每次会话的帮助程度评分，以及你使用的 AI token 数。",
            "谁能看到你的会话：你本人，以及你的导师（真实的人，例如教练课程讲师）——导师可以查看你的 AI学员陪练 会话，以及你主动分享的 AI教练 会话。应用管理员负责管理账户和每日额度，能看到你的会话时间、长度和你给出的帮助程度评分，但无法打开对话内容。除你之外的任何人打开你的会话都会记录在审计日志中。",
            "存储与 AI 处理：你的对话保存在应用的服务器上，你的消息会发送给配置的 AI 模型服务商以生成回复。应用不为管理员提供任何查看对话内容的途径；但和所有在线服务一样，服务器的运营者和 AI 服务商会经手这些数据。",
            "你的选择：你可以随时在账户页面下载全部数据或删除账户。删除后，会话和洞察将被永久移除。",
        ],
        "audit_actions": {
            "account_created": "创建账户", "account_deleted": "删除账户", "password_changed": "修改密码",
            "password_reset": "重置密码", "reset_link_created": "生成重置链接", "reset_email_sent": "发送重置邮件",
            "invite_created": "创建邀请", "invite_revoked": "撤销邀请", "user_updated": "更新成员信息",
            "session_viewed": "查看会话", "session_shared": "分享会话", "session_unshared": "取消分享会话", "session_deleted": "删除会话",
            "safety_flag": "显示安全提示", "limits_updated": "修改每日额度", "ai_error": "AI 请求失败",
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
.card.disclosure { padding:0; }
.disclosure > summary { padding:18px 20px; min-height:56px; cursor:pointer; color:var(--deep); border-radius:20px; }
.disclosure > summary::marker { color:var(--muted); font-size:14px; }
.disclosure > summary h2 { display:inline; margin:0; color:var(--ink); }
.disclosure > summary:hover { background:var(--mist); }
.disclosure > summary:focus-visible { outline:3px solid rgba(25,121,186,0.35); outline-offset:2px; }
.disclosure-body { padding:0 20px 20px; }
.disclosure-body > :last-child { margin-bottom:0; }
.grid2:has(> .disclosure) { align-items:start; }
.narrow { max-width:460px; margin:4vh auto 0; }
h1 { font-size:24px; font-weight:800; letter-spacing:-0.01em; line-height:1.2; margin:0 0 6px; }
h2 { font-size:18px; font-weight:800; line-height:1.25; margin:0 0 12px; }
.eyebrow { font-size:12px; font-weight:800; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); margin-bottom:4px; }
.muted, .hint { color:var(--muted); font-size:14px; }
label { display:block; font-weight:700; font-size:14px; margin:12px 0 6px; }
input[type=text], input[type=email], input[type=password], input[type=number], select, textarea {
  width:100%; min-height:44px; padding:10px 14px; border:1px solid var(--border); border-radius:14px; font:inherit;
  background:var(--paper); color:var(--ink); }
textarea { resize:vertical; min-height:130px; }
input:focus-visible, select:focus-visible, textarea:focus-visible, button:focus-visible, a:focus-visible { outline:3px solid rgba(25,121,186,0.35); outline-offset:2px; }
.check { display:flex; gap:10px; align-items:flex-start; font-weight:500; }
.check input { margin-top:4px; width:18px; height:18px; flex:0 0 auto; }
button, .button { display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:10px 18px;
  border-radius:14px; border:0; background:var(--blue); color:#fff; font:inherit; font-weight:800; cursor:pointer; text-decoration:none; }
button:hover, .button:hover { background:var(--blue-hover); }
button.secondary, .button.secondary { background:var(--mist); color:var(--deep); border:1px solid var(--border); }
button.quiet { min-height:36px; padding:6px 12px; font-size:14px; background:var(--mist); color:var(--deep); border:1px solid var(--border); }
button.quiet.danger { background:var(--paper); color:var(--warn); border-color:#e8c9bf; }
button.danger { background:var(--paper); color:var(--warn); border:1px solid #e8c9bf; }
.full { width:100%; margin-top:18px; }
.flash { padding:12px 16px; border-radius:14px; margin-bottom:16px; font-weight:600; font-size:15px; }
.flash.ok, .flash.info { background:var(--tint); color:var(--deep); }
.flash.error { background:#fbefeb; color:var(--warn); }
.list { display:flex; flex-direction:column; gap:10px; }
.row { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:8px 14px; padding:12px 14px;
  border:1px solid var(--border); border-radius:16px; background:var(--mist); }
.row .main { min-width:0; flex:1 1 240px; }
.row.compact { flex-wrap:nowrap; padding:8px 14px; }
.row.compact .main { flex:1 1 auto; }
.row .title { font-weight:700; overflow-wrap:anywhere; }
.row .meta { color:var(--muted); font-size:14px; overflow-wrap:anywhere; }
.pill { display:inline-block; font-size:12px; font-weight:800; padding:2px 10px; border-radius:999px; background:var(--tint); color:var(--deep); white-space:nowrap; }
.pill.gold { background:rgba(240,185,90,0.24); color:#7a5414; }
.actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.history-pagination { display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; justify-content:space-between; margin:16px 0; }
form.inline { display:inline; margin:0; }
.grid2 { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:16px; margin-bottom:16px; }
.grid2 > .card { margin-bottom:0; }
.fields { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:8px 12px; width:100%; }
.fields label { margin:0 0 4px; font-size:12px; color:var(--muted); }
.fields.three { grid-template-columns:repeat(3, minmax(0, 1fr)); }
.pair { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:0 12px; }
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
  .disclosure > summary { padding:16px; border-radius:18px; }
  .disclosure-body { padding:0 16px 16px; }
  .grid2 { grid-template-columns:minmax(0, 1fr); }
  .fields { grid-template-columns:repeat(2, minmax(0, 1fr)); }
  .fields.three { grid-template-columns:minmax(0, 1fr); }
  .transcript .msg { max-width:92%; }
}
"""


DISCLOSURE_JS = """<script>
(() => {
  const reveal = () => {
    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;
    for (let node = target; node; node = node.parentElement) {
      if (node.tagName === "DETAILS") node.open = true;
    }
    target.scrollIntoView({block: "start"});
  };
  window.addEventListener("hashchange", reveal);
  reveal();
})();
</script>"""


def disclosure(title: str, body: str, *, element_id: str, opened: bool = False) -> str:
    return (f'<details class="card disclosure" id="{_e(element_id)}"{" open" if opened else ""}>'
            f'<summary><h2 id="{_e(element_id)}-label">{_e(title)}</h2></summary>'
            f'<div class="disclosure-body">{body}</div></details>')


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
    # Dollars left on the AI account, or None when unknown; shown on the Admin page.
    ai_credit: Callable[[], float | None] | None = None
    # Who to tell about a problem or an idea, e.g. "Fan, WeChat ID fan-coach" (STUDIO_CONTACT); shown on the Help page.
    contact: str = ""


# Failed sign-ins allowed per email address in 15 minutes, from all addresses together (see build_router).
EMAIL_MAX_FAILURES = 20

# Invite links: one person by default; a group link (e.g. for a WeChat group) can let in up to MAX_INVITE_USES people.
DEFAULT_INVITE_DAYS = 14
MAX_INVITE_DAYS = 60
MAX_INVITE_USES = 200


def invite_limits(uses: str, days: str, locked: bool = False) -> tuple[int, int]:
    """(people, days) for a new invite from the form, within bounds. A link locked to one email address is for one use."""
    def number(value: str, default: int, top: int) -> int:
        value = (value or "").strip()
        return min(max(int(value), 1), top) if value.isdigit() else default

    return (1 if locked else number(uses, 1, MAX_INVITE_USES)), number(days, DEFAULT_INVITE_DAYS, MAX_INVITE_DAYS)


# Below this balance the Admin page warns that the AI credit is running low (a busy day costs about a dollar).
LOW_CREDIT_DOLLARS = 2.0


def preferred_language(cookies, headers, fallback: str | None = "en") -> str | None:
    """The language a person last picked (shared by the app and these pages), else their browser's first language."""
    cookies = cookies or {}
    chosen = cookies.get(LANG_COOKIE, cookies.get(LEGACY_LANG_COOKIE))
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
    return accounts.read_session_cookie(accounts.session_cookie_value(request.cookies), secret, store.get_user)


def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


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
        logging.getLogger("coaching_studio").exception("Sending email failed")


def _safe_next(target: str | None) -> str:
    return target if target and target.startswith("/") and not target.startswith("//") else "/"


def build_router(get_store: Callable[[], db.Store], settings: PageSettings, *,
                 retry_review: Callable[[dict, dict, dict], str] | None = None,
                 retry_action_card: Callable[[dict, dict, dict], str] | None = None) -> APIRouter:
    router = APIRouter()
    throttle = accounts.LoginThrottle()
    # The address in the first throttle comes from X-Forwarded-For, which a caller can change on every try, so failed
    # sign-ins are also counted per email address alone. Generous, so a forgetful person isn't locked out.
    email_throttle = accounts.LoginThrottle(max_failures=EMAIL_MAX_FAILURES, window_seconds=900)

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
        switch_query = {"lang": other}
        if request.url.path in ("/account", "/mentor") and "page" in request.query_params:
            switch_query["page"] = request.query_params["page"]
        switch = (f'<p class="lang"><a href="?{_e(urlencode(switch_query))}">{"English" if other == "en" else "中文"}</a> · '
                  f'<a href="/help">{_e(T[lang]["help"])}</a> · <a href="/privacy">{_e(T[lang]["privacy"])}</a></p>')
        page = f"""<!doctype html><html lang="{'zh-CN' if lang == 'zh' else 'en'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f3f8fd"><title>{_e(title)} · {_e(T[lang]['brand'])}</title>
<link rel="icon" type="image/png" href="/icons/studio-icon-192.png"><link rel="apple-touch-icon" href="/icons/studio-icon-180.png">
<style>{CSS}</style></head><body><main class="shell">
<header class="bar"><a class="brand" href="/"><img src="/icons/studio-icon-192.png" alt="">{_e(T[lang]['brand'])}</a>{nav}</header>
{flash_html}{body}{switch}</main>{LOCAL_TIME_JS}{DISCLOSURE_JS}</body></html>"""
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
        response.delete_cookie(accounts.LEGACY_SESSION_COOKIE, secure=settings.secure_cookies, httponly=True)
        return response

    def clear_login(response: Response) -> None:
        response.delete_cookie(accounts.SESSION_COOKIE, secure=settings.secure_cookies, httponly=True)
        response.delete_cookie(accounts.LEGACY_SESSION_COOKIE, secure=settings.secure_cookies, httponly=True)

    def csrf_field(request: Request) -> str:
        token = accounts.csrf_token(accounts.session_cookie_value(request.cookies), settings.secret)
        return f'<input type="hidden" name="csrf" value="{token}">'

    def checked_user(request: Request, csrf: str | None = None, roles: tuple[str, ...] = ()) -> dict | None:
        user = current_user(request, get_store(), settings.secret)
        if not user or (roles and user["role"] not in roles):
            return None
        if csrf is not None and not accounts.csrf_ok(accounts.session_cookie_value(request.cookies), settings.secret, csrf):
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
        """The app and its database are up. Not for an uptime monitor: see /ping."""
        get_store().has_users()
        return {"ok": True}

    @router.get("/ping")
    def ping():
        """The app is up, without touching the database. For uptime monitors and container health checks: checking
        /healthz every few minutes would keep a free Neon database awake around the clock and use up its 100
        compute-hours a month, and Neon then stops the database until the next month."""
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
        email_key = email.strip().lower()
        key = f"{email_key}|{request.client.host if request.client else ''}"
        if throttle.blocked(key) or email_throttle.blocked(email_key):
            return login_form(request, lang, email, ("error", T[lang]["throttled"]), 429)
        user = store.get_user_by_email(email)
        if not user or user["status"] != "active" or not accounts.verify_password(password, user["password_hash"]):
            throttle.failed(key)
            email_throttle.failed(email_key)
            return login_form(request, lang, email, ("error", T[lang]["bad_login"]), 401)
        # Only the per-address count resets: a guesser elsewhere shouldn't get a fresh start when the owner signs in.
        throttle.succeeded(key)
        return set_login(RedirectResponse(_safe_next(request.query_params.get("next")), status_code=303), user)

    @router.post("/logout")
    def logout(request: Request, csrf: str = Form("")):
        response = RedirectResponse("/login", status_code=303)
        if checked_user(request, csrf):
            clear_login(response)
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
        try:
            user_id = store.register_from_invite(code, email, name or email.split("@")[0], accounts.hash_password(password))
        except SQLAlchemyError as error:
            logging.getLogger("coaching_studio").error("Account signup failed: %s", type(error).__name__)
            return signup_form(request, lang, invite, ("error", T[lang]["signup_failed"]), values)
        if user_id is None:
            return invalid_invite(request, lang)
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
        if store.reset_user_id(token) is None:
            return reset_page(request, token)
        try:
            user_id = store.reset_password(token, accounts.hash_password(password))
        except SQLAlchemyError as error:
            logging.getLogger("coaching_studio").error("Password reset failed: %s", type(error).__name__)
            return reset_form(request, lang, token, ("error", T[lang]["reset_failed"]))
        if user_id is None:
            return reset_page(request, token)
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
        if settings.contact:
            faq_items.append([T[lang]["help_contact_q"], text(lang, "help_contact_a", contact=settings.contact)])
        faq = "".join(f'<div class="faq"><b>{_e(question)}</b><p>{_e(answer)}</p></div>' for question, answer in faq_items)
        body = f"""<div class="card"><div class="eyebrow">{_e(T[lang]['help_eyebrow'])}</div><h1>{_e(T[lang]['help_title'])}</h1>
<p class="hint">{_e(T[lang]['help_intro'])}</p><p class="hint">{_e(T[lang]['independent'])}</p></div>
<div class="card"><h2>{_e(T[lang]['help_join_title'])}</h2><ol class="steps">{steps}</ol></div>
<div class="grid2"><div class="card"><h2>{_e(T[lang]['module_coach'])}</h2><p>{_e(T[lang]['help_coach_mode'])}</p></div>
<div class="card"><h2>{_e(T[lang]['module_coachee'])}</h2><p>{_e(T[lang]['help_coachee_mode'])}</p></div></div>
<div class="card"><h2>{_e(T[lang]['help_session_title'])}</h2><ul class="steps">{session_items}</ul></div>
<div class="card"><h2>{_e(T[lang]['help_limits_title'])}</h2><p>{_e(text(lang, 'help_limits', coach=allowance(limits['coach']), coachee=allowance(limits['coachee']), messages=quota.MESSAGES_PER_CONVERSATION, warning=quota.MESSAGES_LEFT_WARNING))}</p></div>
<div class="card"><h2>{_e(T[lang]['help_faq_title'])}</h2>{faq}<p class="hint"><a href="/voices">{_e(T[lang]['voices_link'])}</a></p></div>
{'' if user else f'<p><a class="button full" href="/login">{_e(T[lang]["help_cta"])}</a></p>'}"""
        return render(request, lang, T[lang]["help"], body, user=user)

    # Privacy --------------------------------------------------------------------

    @router.get("/voices")
    def voices_page(request: Request):
        """The voice the app uses on this device for each language, with a Listen button, and why it sounds as it does.
        Public, like Help: it shows only the visitor's own browser. ?details=1 also lists every voice the browser offers,
        for troubleshooting (built when Fan heard no change on an iPhone; too technical to show everyone)."""
        lang = page_lang(request)
        user = current_user(request, get_store(), settings.secret)
        details = request.query_params.get("details") == "1"
        words = {key: T[lang][key] for key in ("voices_listen", "voices_none", "voices_device", "voices_online",
                                                "voices_default", "voices_all", "voices_online_note")}
        body = f"""<div class="card"><h1>{_e(T[lang]['voices_title'])}</h1><p class="hint">{_e(T[lang]['voices_intro'])}</p>
<p class="hint" id="voice-iphone" hidden>{_e(T[lang]['voices_iphone'])}</p>
<h2>{_e(T[lang]['voices_choice'])}</h2><div id="voice-choice" class="list"><p class="muted">{_e(T[lang]['voices_loading'])}</p></div></div>
{'<div class="card"><h2 id="voice-count"></h2><div id="voice-list" class="list"></div><p class="hint" id="voice-agent"></p></div>' if details else ''}
<script>
(function () {{
  const words = {json.dumps(words, ensure_ascii=False)};
  const tts = ({tts_js});
  const synth = window.speechSynthesis;
  const languages = ["中文", "English"];
  const samples = {{"中文": "你好。今天这次谈话，你最希望有什么收获？", "English": "Hi. What would you like to get from our conversation today?"}};
  const escape = (text) => String(text).replace(/[&<>"]/g, (c) => ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}})[c]);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const where = (voice) => voice.localService ? words.voices_device : words.voices_online;
  // iPadOS reports itself as a Mac, but with a touch screen.
  const apple = /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
  document.getElementById("voice-iphone").hidden = !apple;
  const details = document.getElementById("voice-list");
  if (details) document.getElementById("voice-agent").textContent = navigator.userAgent;
  const choice = document.getElementById("voice-choice");
  if (!synth) {{ choice.innerHTML = '<p class="muted">' + escape(words.voices_none) + "</p>"; return; }}

  // Which voice the app's own read-aloud code would use: run it with speaking switched off.
  const pick = async (langLabel) => {{
    const speak = synth.speak, cancel = synth.cancel;
    let chosen;
    synth.speak = (utterance) => {{ if (chosen === undefined) chosen = utterance.voice || null; }};
    synth.cancel = () => {{}};
    window.__ttsFallbackMs = 600000;
    tts("check" + Math.random() + "|||" + samples[langLabel], true, langLabel);
    await sleep(250);
    window.__ttsRun = null;
    delete window.__ttsFallbackMs;
    synth.speak = speak;
    synth.cancel = cancel;
    return chosen;
  }};

  (async () => {{
    let voices = synth.getVoices();
    for (let i = 0; i < 20 && !voices.length; i++) {{ await sleep(150); voices = synth.getVoices(); }}
    const rows = [];
    for (const langLabel of languages) {{
      const voice = await pick(langLabel);
      let name = voice ? escape(voice.name) : escape(words.voices_default);
      if (details && voice) name += ' <span class="pill">' + escape(voice.lang) + " · " + escape(where(voice)) + "</span>";
      if (voice && !voice.localService) name += '<br><span class="hint">' + escape(words.voices_online_note) + "</span>";
      rows.push('<div class="row"><div class="main"><div class="title">' + escape(langLabel) + '</div><div class="meta">' + name +
                '</div></div><div class="actions"><button class="quiet" type="button" data-lang="' + escape(langLabel) +
                '">' + escape(words.voices_listen) + "</button></div></div>");
    }}
    choice.innerHTML = rows.join("");
    choice.querySelectorAll("button[data-lang]").forEach((button) => button.addEventListener("click", () => {{
      tts(Date.now() + "|||" + samples[button.dataset.lang], true, button.dataset.lang);
    }}));
    if (!details) return;
    const ours = voices.filter((voice) => /^(zh|en|yue)/i.test(voice.lang || ""))
      .sort((a, b) => (a.lang + a.name).localeCompare(b.lang + b.name));
    document.getElementById("voice-count").textContent = words.voices_all.replace("{{n}}", ours.length);
    details.innerHTML = ours.map((voice) =>
      '<div class="row"><div class="main"><div class="title">' + escape(voice.name) + '</div><div class="meta">' +
      escape(voice.lang) + " · " + escape(where(voice)) + " · " + escape(voice.voiceURI || "") + "</div></div></div>").join("")
      || '<p class="muted">' + escape(words.voices_none) + "</p>";
  }})();
}})();
</script>"""
        return render(request, lang, T[lang]["voices_title"], body, user=user)

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

    def history_page(request: Request, total: int, size: int) -> tuple[int, int]:
        pages = max(1, (total + size - 1) // size)
        try:
            page = int(request.query_params.get("page", "1"))
        except ValueError:
            page = 1
        return max(1, min(page, pages)), pages

    def history_pagination(lang: str, path: str, section: str, page: int, pages: int) -> str:
        if pages == 1:
            return ""
        links = []
        for number, key in ((page - 1, "history_newer"), (page + 1, "history_earlier")):
            if 1 <= number <= pages:
                href = f"{path}?{urlencode({'lang': lang, 'page': number})}#{section}"
                links.append(f'<a class="button secondary" href="{_e(href)}">{_e(T[lang][key])}</a>')
        return (f'<nav class="history-pagination" aria-label="{_e(T[lang]["history_pages"])}">'
                f'<span class="muted">{_e(text(lang, "history_page", page=page, pages=pages))}</span>'
                f'<div class="actions">{"".join(links)}</div></nav>')

    def session_row(lang: str, row: dict, *, owner_name: str | None = None, share_form: str = "", link: bool = True,
                    results: bool = False) -> str:
        """One session in a list. results=True adds its score or next step; the admin's list leaves them out."""
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
        score, next_step, rating = "", "", ""
        if row.get("rating"):  # only the admin's list carries ratings
            rating = f' <span class="pill">{_e(text(lang, "rating_pill", rating=row["rating"]))}</span>'
        if results and row.get("score") is not None:
            score = f' <span class="pill gold">{_e(text(lang, "score", n=row["score"]))}</span>'
        if results and (row.get("card") or {}).get("next_step"):
            next_step = f'<div class="meta">{_e(T[lang]["card_next_step"])}: {_e(_clip(row["card"]["next_step"], 120))}</div>'
        return f"""<div class="row"><div class="main"><div class="title">{title} <span class="pill">{_e(status)}</span> {shared}{score}{rating}</div>
<div class="meta">{_e(stage)} · {_time(row["created_at"])} · {_e(' · '.join(bits))}</div>{next_step}</div>
<div class="actions">{share_form}{f'<a class="button secondary" href="/sessions/{_e(row["id"])}">{_e(T[lang]["view"])}</a>' if link else ''}</div></div>"""

    def profile_block(lang: str, module: str, data: dict | None, request: Request) -> str:
        heading = T[lang]["module_coachee" if module == "coachee" else "module_coach"]
        profile = UserProfile.from_dict(data)
        sections = []
        for name in PROFILE_FIELDS[module]:
            rows = []
            for item in profile_items(profile, name):
                key = profile_version(item)
                hidden = profile_form_fields(request, module, name, key)
                rows.append(f'''<div class="row"><div class="main title">{_e(item)}</div><div class="actions">
<a class="button secondary" href="/account/profile/{module}/{name}/{key}">{_e(T[lang]['edit_insight'])}</a>
<form method="post" action="/account/profile/item" class="inline">{hidden}
<button class="quiet danger" name="action" value="remove" type="submit">{_e(T[lang]['remove_insight'])}</button></form></div></div>''')
            if rows:
                label = T[lang][f"client_{name}" if module == "coach" else name]
                sections.append(f'<h3>{_e(label)}</h3><div class="list">{"".join(rows)}</div>')
        if not sections:
            return f'<div><div class="eyebrow">{_e(heading)}</div><p class="muted">{_e(T[lang]["no_insights"])}</p></div>'
        return f"""<div><div class="eyebrow">{_e(heading)}</div>
{''.join(sections)}
<form method="post" action="/account/profile/reset" class="inline">{csrf_field(request)}<input type="hidden" name="module" value="{module}">
<input type="hidden" name="version" value="{profile_version(data)}">
<button class="quiet" type="submit">{_e(T[lang]['reset_insights'])}</button></form></div>"""

    def profile_form_fields(request, module, name, key):
        return f'''{csrf_field(request)}<input type="hidden" name="module" value="{module}">
<input type="hidden" name="field" value="{name}"><input type="hidden" name="key" value="{key}">'''

    def profile_editor(request, user, module, name, key, value, flash=None):
        lang = page_lang(request)
        heading = T[lang]["module_coachee" if module == "coachee" else "module_coach"]
        label = T[lang][f"client_{name}" if module == "coach" else name]
        field = f'''<label for="insight-value">{_e(label)}</label>
<textarea id="insight-value" name="value" maxlength="{MAX_INSIGHT_CHARS}" {"required" if key else "readonly"}>{_e(value)}</textarea>'''
        back = f'<a class="button secondary" href="/account#insights">{_e(T[lang]["cancel_insight"])}</a>'
        if key:
            field = f'''<form method="post" action="/account/profile/item">{profile_form_fields(request, module, name, key)}
{field}<div class="actions"><button name="action" value="save" type="submit">{_e(T[lang]['save'])}</button>
<button class="quiet danger" name="action" value="remove" type="submit" formnovalidate>{_e(T[lang]['remove_insight'])}</button>
{back}</div></form>'''
        else:
            field += back
        body = f'''<div class="card narrow"><div class="eyebrow">{_e(heading)}</div><h1>{_e(T[lang]['edit_insight'])}</h1>{field}</div>'''
        return render(request, lang, T[lang]["edit_insight"], body, user=user, flash=flash, current="account")

    def progress_cards(lang: str, user_id: int) -> str:
        """Recent action cards and practice scores: what someone takes away from their sessions."""
        store = get_store()
        cards = []
        for result in store.session_results(user_id, "coach", limit=3):
            card = result.get("card") or {}
            fields = "".join(f'<div><b>{_e(T[lang]["card_" + key])}</b>: {_e(card[key])}</div>'
                             for key in ("goal", "next_step", "by_when", "support") if card.get(key))
            cards.append(f'<div class="row"><div class="main"><div class="meta">{_time(result["created_at"])}</div>{fields}</div></div>')
        cards_html = "".join(cards) or f'<p class="muted">{_e(T[lang]["no_action_cards"])}</p>'
        scores = [r for r in store.session_results(user_id, "coachee", limit=6) if r["score"] is not None]
        if scores:
            score_rows = "".join(f'<div class="row compact"><div class="main"><div class="meta">{_time(r["created_at"])}</div></div>'
                                 f'<span class="pill gold">{_e(text(lang, "score", n=r["score"]))}</span></div>' for r in scores)
            scores_html = f'<div class="list">{score_rows}</div>'
        else:
            scores_html = f'<p class="muted">{_e(T[lang]["no_scores"])}</p>'
        return ('<div class="grid2">'
                + disclosure(T[lang]['action_cards'], f'<div class="list">{cards_html}</div>', element_id="action-cards")
                + disclosure(T[lang]['practice_scores'], scores_html, element_id="practice-scores") + '</div>')

    def practice_goal_block(request, data, draft=None, error=None):
        lang = page_lang(request)
        profile = UserProfile.from_dict(data)
        candidates = [item for item in profile.growth_areas if len(item) <= MAX_PRACTICE_GOAL_CHARS]
        choose = ""
        if candidates:
            options = ''.join(f'<option value="{_e(item)}">{_e(item)}</option>' for item in candidates)
            choose = f'''<label for="practice-goal-choice">{_e(T[lang]['practice_goal_choose'])}</label>
<select id="practice-goal-choice" onchange="if(this.value) document.getElementById('practice-goal-value').value=this.value;">
<option value="">{_e(T[lang]['practice_goal_manual'])}</option>{options}</select>'''
        feedback = f'<div class="flash error" role="status">{_e(error)}</div>' if error else ""
        value = profile.next_practice_goal if draft is None else draft
        body = f'''<p class="hint">{_e(T[lang]['practice_goal_hint'])}</p>{feedback}
<div class="row"><div class="main"><div class="meta">{_e(T[lang]['practice_goal_current'])}</div>
<div class="title">{_e(profile.next_practice_goal or T[lang]['practice_goal_empty'])}</div></div></div>
<form method="post" action="/account/practice-goal#practice-goal">{csrf_field(request)}
<input type="hidden" name="version" value="{profile_version(profile.next_practice_goal)}">{choose}
<textarea id="practice-goal-value" name="value" maxlength="{MAX_PRACTICE_GOAL_CHARS}" aria-labelledby="practice-goal-label">{_e(value)}</textarea>
<div class="actions"><button name="action" value="save" type="submit">{_e(T[lang]['save'])}</button>
<button class="secondary" name="action" value="clear" type="submit" formnovalidate>{_e(T[lang]['practice_goal_clear'])}</button></div></form>'''
        return disclosure(T[lang]['practice_goal'], body, element_id="practice-goal", opened=bool(error))

    def practice_goal_error(request, user, data, draft, key):
        # A failed write may also mean further reads fail. Keep the known saved content and draft available.
        lang = page_lang(request)
        return render(request, lang, T[lang]["practice_goal"],
                      practice_goal_block(request, data, draft, T[lang][key]), user=user, current="account")

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
        trainer_line = (f'{_e(text(lang, "your_trainer", name=trainer["display_name"]))}<br>{_e(T[lang]["trainer_sees_practice"])}'
                        if trainer else _e(T[lang]["no_trainer"]))
        rows = []
        page, pages = history_page(request, store.count_sessions(user["id"]), 100)
        pagination = history_pagination(lang, "/account", "my-sessions", page, pages)
        for row in store.list_sessions(user["id"], limit=100, offset=(page - 1) * 100):
            share_form = ""
            if row["module"] == "coach" and trainer:
                label = T[lang]["unshare" if row["shared_with_trainer"] else "share"]
                share_form = (f'<form method="post" action="/account/sessions/{_e(row["id"])}/share" class="inline">{csrf_field(request)}'
                              f'<input type="hidden" name="trainer_id" value="{trainer["id"]}">'
                              f'<input type="hidden" name="shared" value="{"no" if row["shared_with_trainer"] else "yes"}">'
                              f'<button class="quiet" type="submit">{_e(label)}</button></form>')
            # Someone who said more than they meant to can remove one conversation without closing their account.
            share_form += (f'<form method="post" action="/account/sessions/{_e(row["id"])}/delete" class="inline" '
                           f'data-confirm="{_e(T[lang]["delete_session_confirm"])}">{csrf_field(request)}'
                           f'<button class="quiet danger" type="submit">{_e(T[lang]["delete_session"])}</button></form>')
            rows.append(session_row(lang, row, share_form=share_form, results=True))
        sessions_html = "".join(rows) or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'
        insights_html = f'''<p class="hint">{_e(T[lang]['insight_hint'])}</p><div class="grid2">
{profile_block(lang, 'coach', store.get_profile(user['id'], 'coach'), request)}
{profile_block(lang, 'coachee', store.get_profile(user['id'], 'coachee'), request)}</div>'''
        settings_html = f'''<div class="grid2"><section><h2>{_e(T[lang]['change_password'])}</h2>
<form method="post" action="/account/password">{csrf_field(request)}
<label for="current">{_e(T[lang]['current_password'])}</label><input id="current" name="current" type="password" autocomplete="current-password" required>
<label for="password">{_e(T[lang]['new_password'])}</label><input id="password" name="password" type="password" autocomplete="new-password" required>
<label for="confirm">{_e(T[lang]['confirm_password'])}</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" required>
<button class="full" type="submit">{_e(T[lang]['save'])}</button></form></section>
<section><h2>{_e(T[lang]['your_data'])}</h2><p><a class="button secondary" href="/account/export">{_e(T[lang]['export'])}</a></p>
<form method="post" action="/account/delete">{csrf_field(request)}<p class="hint">{_e(T[lang]['delete_hint'])}</p>
<input name="confirm" type="text" autocomplete="off" aria-label="DELETE">
<button class="danger full" type="submit">{_e(T[lang]['delete_account'])}</button></form></section></div>'''
        body = f"""<div class="card"><div class="eyebrow">{_e(ROLE_LABELS[lang][user['role']])}</div><h1>{_e(user['display_name'])}</h1>
<p class="muted">{_e(user['email'])}<br>{'<br>'.join(_e(line) for line in quota_lines)}</p><p class="hint">{trainer_line}</p>
<form method="post" action="/logout" class="inline">{csrf_field(request)}<button class="secondary" type="submit">{_e(T[lang]['sign_out'])}</button></form></div>
{progress_cards(lang, user["id"])}
{practice_goal_block(request, store.get_profile(user['id'], 'coachee'))}
{disclosure(T[lang]['my_sessions'], f'{pagination}<div class="list">{sessions_html}</div>{pagination}', element_id="my-sessions", opened=True)}
{disclosure(T[lang]['insights'], insights_html, element_id="insights")}
{disclosure(T[lang]['account_settings'], settings_html, element_id="account-settings", opened=request.url.path in ('/account/password', '/account/delete'))}
<script>document.querySelectorAll('form[data-confirm]').forEach(function (form) {{
  form.addEventListener('submit', function (event) {{ if (!window.confirm(form.dataset.confirm)) event.preventDefault(); }});
}});</script>"""
        return render(request, lang, T[lang]["account"], body, user=user, flash=flash, current="account")

    @router.get("/account")
    def account(request: Request):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        flash_key = request.query_params.get("done")
        flash = ("ok", T[page_lang(request)][flash_key]) if flash_key in ("password_changed", "insights_cleared", "session_deleted", "insight_saved", "insight_removed", "practice_goal_saved", "practice_goal_cleared") else None
        return account_page(request, user, flash)

    @router.post("/account/practice-goal")
    def save_practice_goal(request: Request, csrf: str = Form(""), version: str = Form(""),
                           value: str = Form(""), action: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        if action not in ("save", "clear"):
            return forbidden(request, lang, user)
        store = get_store()
        data = store.get_profile(user["id"], "coachee")
        if action == "save" and len(value.strip()) > MAX_PRACTICE_GOAL_CHARS:
            return practice_goal_error(request, user, data, value, "practice_goal_invalid")
        profile = UserProfile.from_dict(data)
        if version != profile_version(profile.next_practice_goal):
            return practice_goal_error(request, user, data, value, "practice_goal_conflict")
        profile.next_practice_goal = value.strip() if action == "save" else ""
        try:
            saved = store.save_profile(user["id"], "coachee", profile.to_dict(), expected_version=profile_version(data))
        except SQLAlchemyError:
            logging.getLogger("coaching_studio").exception("Saving an owner practice goal failed")
            return practice_goal_error(request, user, data, value, "practice_goal_failed")
        if not saved:
            return practice_goal_error(request, user, store.get_profile(user["id"], "coachee"), value, "practice_goal_conflict")
        done = "practice_goal_saved" if profile.next_practice_goal else "practice_goal_cleared"
        return RedirectResponse(f"/account?done={done}#practice-goal", status_code=303)

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

    @router.get("/account/profile/{module}/{field}/{key}")
    def edit_profile_item(request: Request, module: str, field: str, key: str):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        if field not in PROFILE_FIELDS.get(module, ()):
            return forbidden(request, page_lang(request), user)
        data = get_store().get_profile(user["id"], module)
        if not data:
            return forbidden(request, page_lang(request), user)
        items = profile_items(UserProfile.from_dict(data), field)
        item = next((item for item in items if profile_version(item) == key), None)
        if item is None:
            return account_page(request, user, ("error", T[page_lang(request)]["insight_conflict"]))
        return profile_editor(request, user, module, field, key, item)

    @router.post("/account/profile/item")
    def save_profile_item(request: Request, csrf: str = Form(""), module: str = Form(""), field: str = Form(""),
                          key: str = Form(""), value: str = Form(""), action: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        if field not in PROFILE_FIELDS.get(module, ()) or action not in ("save", "remove"):
            return forbidden(request, lang, user)
        store = get_store()
        data = store.get_profile(user["id"], module)
        profile = UserProfile.from_dict(data)
        items = profile_items(profile, field)
        index = next((i for i, item in enumerate(items) if profile_version(item) == key), None)
        conflict = ("error", T[lang]["insight_conflict"])
        if index is None:
            if action == "save" and value:
                return profile_editor(request, user, module, field, None, value, conflict)
            return account_page(request, user, conflict)
        replacement = value.strip() if action == "save" else ""
        if action == "save" and (not replacement or len(replacement) > MAX_INSIGHT_CHARS or any(
                other.casefold() == replacement.casefold() for i, other in enumerate(items) if i != index)):
            return profile_editor(request, user, module, field, key, value, ("error", T[lang]["insight_invalid"]))
        updated = change_insight(profile, field, index, replacement)
        try:
            saved = store.save_profile(user["id"], module, updated.to_dict(), expected_version=profile_version(data))
        except SQLAlchemyError:
            logging.getLogger("coaching_studio").exception("Saving an owner insight change failed")
            return profile_editor(request, user, module, field, key, value if action == "save" else items[index],
                                  ("error", T[lang]["insight_failed"]))
        if not saved:
            if action == "save" and value:
                return profile_editor(request, user, module, field, None, value, conflict)
            return account_page(request, user, conflict)
        done = "insight_saved" if action == "save" else "insight_removed"
        return RedirectResponse(f"/account?done={done}#insights", status_code=303)

    @router.post("/account/profile/reset")
    def reset_profile(request: Request, csrf: str = Form(""), module: str = Form(""), version: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        if module not in PROFILE_FIELDS:
            return forbidden(request, lang, user)
        store = get_store()
        data = store.get_profile(user["id"], module)
        if version != profile_version(data):
            return account_page(request, user, ("error", T[lang]["insight_conflict"]))
        profile = UserProfile(next_practice_goal=UserProfile.from_dict(data).next_practice_goal)
        try:
            saved = store.save_profile(user["id"], module, profile.to_dict(), expected_version=version)
        except SQLAlchemyError:
            logging.getLogger("coaching_studio").exception("Clearing owner insights failed")
            return account_page(request, user, ("error", T[lang]["insight_failed"]))
        if not saved:
            return account_page(request, user, ("error", T[lang]["insight_conflict"]))
        return RedirectResponse("/account?done=insights_cleared#insights", status_code=303)

    @router.post("/account/sessions/{session_id}/share")
    def share_session(request: Request, session_id: str, csrf: str = Form(""), shared: str = Form(""),
                      trainer_id: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        store = get_store()
        row = store.get_session(session_id)
        if not row or row["user_id"] != user["id"] or row["module"] != "coach":
            return forbidden(request, page_lang(request), user)
        expected_trainer = user["trainer_id"]
        if (not expected_trainer or trainer_id != str(expected_trainer)
                or not store.set_session_shared(session_id, shared == "yes", expected_trainer_id=expected_trainer)):
            user = store.get_user(user["id"])
            if not user:
                return login_redirect(request)
            return account_page(request, user, ("error", T[page_lang(request)]["trainer_changed"]))
        store.log(user["id"], "session_shared" if shared == "yes" else "session_unshared", target_session_id=session_id)
        return RedirectResponse("/account", status_code=303)

    @router.post("/account/sessions/{session_id}/delete")
    def delete_session(request: Request, session_id: str, csrf: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        store = get_store()
        row = store.get_session(session_id)
        lang = page_lang(request)
        if not row or row["user_id"] != user["id"]:
            return forbidden(request, lang, user)
        # Its action card or score and its rating go too (foreign keys). Its token usage stays, so the daily token
        # allowance still counts it (the session count no longer does); the audit entry keeps no content.
        store.delete_session(session_id)
        store.log(user["id"], "session_deleted", target_user_id=user["id"], target_session_id=session_id)
        return RedirectResponse("/account?done=session_deleted", status_code=303)

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
        clear_login(response)
        return response

    # Transcript review ----------------------------------------------------------

    @router.post("/sessions/{session_id}/retry-action-card")
    def recover_action_card(request: Request, session_id: str, csrf: str = Form(""), version: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        row = get_store().get_session(session_id)
        if not retry_action_card or not row or row["user_id"] != user["id"]:
            return forbidden(request, page_lang(request), user)
        state = json.loads(row["state"])
        if version != row["updated_at"].isoformat() or not can_recover_action_card(row, state):
            result = "card_busy"
        else:
            result = retry_action_card(row, state, user)
        return RedirectResponse(f"/sessions/{quote(session_id, safe='')}?card={result}", status_code=303)

    @router.post("/sessions/{session_id}/retry-review")
    def regenerate_review(request: Request, session_id: str, csrf: str = Form("")):
        user = checked_user(request, csrf)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        row = get_store().get_session(session_id)
        if not retry_review or not row or row["user_id"] != user["id"]:
            return forbidden(request, lang, user)
        state = json.loads(row["state"])
        if not can_retry_review(row, state):
            return forbidden(request, lang, user)
        result = retry_review(row, state, user)
        return RedirectResponse(f"/sessions/{quote(session_id, safe='')}?review={result}", status_code=303)

    @router.get("/sessions/{session_id}")
    def transcript(request: Request, session_id: str):
        user = checked_user(request)
        if not user:
            return login_redirect(request)
        lang = page_lang(request)
        store = get_store()
        row = store.get_session(session_id, with_owner=True)
        owner = {"id": row["user_id"], "trainer_id": row["owner_trainer_id"], "display_name": row["owner_name"]} if row else None
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
        retry_form = ""
        card_panel = ""
        flash = None
        if row["module"] == "coach" and row["status"] == "completed" and row["mode"] == "llm":
            card = row.get("card")
            if card:
                fields = "".join(f'<div><b>{_e(T[lang]["card_" + key])}</b>: {_e(card[key])}</div>'
                                 for key in ACTION_CARD_FIELDS if card.get(key))
                card_panel = f'<div class="card"><h2>{_e(T[lang]["action_cards"])}</h2>{fields}</div>'
            else:
                result = state.get("action_card_result", {})
                pending = result.get("status") == "pending" and result.get("retry_until", "") > db.utcnow().isoformat()
                key = "card_" + result.get("status", "unknown")
                if result.get("status") == "pending" and not pending:
                    key = "card_interrupted"
                notice = T[lang].get(key, T[lang]["card_unknown"])
                form = ""
                if user["id"] == row["user_id"] and retry_action_card and can_recover_action_card(row, state) and not pending:
                    form = f'''<form method="post" action="/sessions/{_e(session_id)}/retry-action-card">
{csrf_field(request)}<input type="hidden" name="version" value="{_e(row['updated_at'].isoformat())}">
<button type="submit">{_e(T[lang]['recover_card'])}</button></form>'''
                card_panel = f'<div class="card"><h2>{_e(T[lang]["action_cards"])}</h2><p>{_e(notice)}</p>{form}</div>'
        if user["id"] == row["user_id"]:
            if retry_review and can_retry_review(row, state):
                retry_form = f"""<form method="post" action="/sessions/{_e(session_id)}/retry-review">
{csrf_field(request)}<button class="button primary" type="submit">{_e(T[lang]["retry_review"])}</button></form>"""
            outcome = request.query_params.get("review")
            if outcome in ("retry_failed", "retry_busy", "retry_saved"):
                flash = ("error" if outcome == "retry_failed" else "info", T[lang][outcome])
            card_outcome = request.query_params.get("card")
            if card_outcome in ("card_saved", "card_none", "card_generation_failed", "card_save_failed", "card_busy"):
                flash = ("error" if card_outcome.endswith("failed") else "info", T[lang][card_outcome])
        body = f"""<div class="card"><div class="eyebrow">{_e(T[lang]['transcript'])}</div>
{session_row(lang, row, link=False, results=is_practice)}<p class="muted">{owner_line}{_time(row['updated_at'])}</p>
{card_panel}{retry_form}<div class="transcript">{''.join(bubbles) or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'}</div></div>"""
        return render(request, lang, T[lang]["transcript"], body, user=user, flash=flash)

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
<div class="pair"><div><label for="invite_uses">{_e(T[lang]['invite_uses'])}</label><input id="invite_uses" name="uses" type="number" inputmode="numeric" min="1" max="{MAX_INVITE_USES}" value="1"></div>
<div><label for="invite_days">{_e(T[lang]['invite_days'])}</label><input id="invite_days" name="days" type="number" inputmode="numeric" min="1" max="{MAX_INVITE_DAYS}" value="{DEFAULT_INVITE_DAYS}"></div></div>
<p class="hint">{_e(T[lang]['invite_group_hint'])}</p>
{role_select}{trainer_select}<button class="full" type="submit">{_e(T[lang]['create_invite'])}</button></form>"""

    def created_link(lang: str, key: str, link: str, **values) -> str:
        return f'<div class="flash ok">{_e(text(lang, key, **values))}<code class="link">{_e(link)}</code></div>'

    def new_invite(request: Request, user: dict, *, role: str, trainer_id: int | None, email: str, uses: str,
                   days: str) -> str:
        """Create an invite from the form and return the message with its link. A link locked to one email address is
        for that one person; otherwise it can be shared with a group (up to MAX_INVITE_USES people)."""
        uses_n, days_n = invite_limits(uses, days, locked=bool(email.strip()))
        store = get_store()
        code = store.create_invite(user["id"], role=role, trainer_id=trainer_id, email=email or None, days_valid=days_n,
                                   max_uses=uses_n)
        store.log(user["id"], "invite_created", detail=f"{role} invite {code[:6]}… for {uses_n}, {days_n} days")
        lang = page_lang(request)
        key = "invite_created_group" if uses_n > 1 else "invite_created"
        return created_link(lang, key, f"{base_url(request)}/invite/{code}", uses=uses_n, days=days_n)

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
        page, pages = history_page(request, store.count_trainer_visible_sessions(user["id"]), 200)
        pagination = history_pagination(lang, "/mentor", "trainee-sessions", page, pages)
        sessions = "".join(session_row(lang, row, owner_name=row["owner_name"], results=True)
                           for row in store.trainer_visible_sessions(user["id"], limit=200, offset=(page - 1) * 200))
        sessions = sessions or f'<p class="muted">{_e(T[lang]["no_sessions"])}</p>'
        body = f"""{extra}<p class="flash info">{_e(T[lang]['mentor_hint'])}</p>
{disclosure(T[lang]['trainees'], f'<div class="list">{trainee_rows}</div>', element_id="trainees", opened=True)}
{disclosure(T[lang]['invite_trainee'], invite_form(request, lang, '/mentor/invites', roles=('user',), trainers=[]), element_id="invite-trainee")}
{disclosure(T[lang]['trainee_sessions'], f'{pagination}<div class="list">{sessions}</div>{pagination}', element_id="trainee-sessions", opened=True)}"""
        return render(request, lang, T[lang]["trainer"], body, user=user, current="trainer")

    @router.get("/mentor")
    def trainer(request: Request):
        user = checked_user(request, roles=("trainer", "admin"))
        return trainer_page(request, user) if user else login_redirect(request)

    @router.post("/mentor/invites")
    def trainer_invite(request: Request, csrf: str = Form(""), email: str = Form(""), uses: str = Form("1"),
                       days: str = Form("")):
        user = checked_user(request, csrf, roles=("trainer", "admin"))
        if not user:
            return login_redirect(request)
        return trainer_page(request, user, new_invite(request, user, role="user", trainer_id=user["id"], email=email,
                                                      uses=uses, days=days))

    # Admin --------------------------------------------------------------------------

    def ai_service_card(lang: str, now: dt.datetime) -> str:
        """Whether the AI is working: the credit left and any failed requests, so the owner hears before members do."""
        lines = []
        credit = settings.ai_credit() if settings.ai_credit else None
        if credit is not None and credit < LOW_CREDIT_DOLLARS:
            lines.append(f'<div class="flash error">{_e(text(lang, "ai_credit_low", amount=f"{credit:.2f}"))}</div>')
        elif credit is not None:
            lines.append(f'<p>{_e(text(lang, "ai_credit_left", amount=f"{credit:.2f}"))}</p>')
        failures = get_store().audit_since("ai_error", now - dt.timedelta(hours=24))
        if failures:
            latest = failures[0]
            lines.append(f'<div class="flash error">{_e(text(lang, "ai_errors", count=len(failures)))} {_time(latest["created_at"])} · '
                         f'{_e(ai_failure_detail(latest["detail"]))}<br>{_e(T[lang]["ai_errors_hint"])}</div>')
        else:
            lines.append(f'<p class="muted">{_e(T[lang]["ai_errors_none"])}</p>')
        return f'<div class="card"><h2>{_e(T[lang]["ai_service"])}</h2>{"".join(lines)}</div>'

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
<div class="meta">{_e(invite['code'][:6])}… · {_time(invite['created_at'])}{(' · ' + _e(text(lang, 'invite_uses_left', used=invite['uses'], max=invite['max_uses']))) if invite['max_uses'] > 1 else ''}{(' · ' + _e(T[lang]['assign_trainer']) + ': ' + _e(names.get(invite['trainer_id'], '?'))) if invite['trainer_id'] else ''}</div></div>
<div class="actions">{revoke}</div></div>""")

        def audit_detail(entry: dict) -> str:
            detail = entry["detail"]
            return ai_failure_detail(detail) if entry["action"] == "ai_error" else detail

        audit_rows = "".join(
            f'<div class="row"><div class="main"><div class="title">{_e(T[lang]["audit_actions"].get(entry["action"], entry["action"]))}</div><div class="meta">{_time(entry["created_at"])} · '
            f'{_e(names.get(entry["actor_id"], entry["actor_id"] or "system"))}'
            f'{(" → " + _e(names.get(entry["target_user_id"], entry["target_user_id"]))) if entry["target_user_id"] else ""}'
            f'{(" · " + _e(entry["target_session_id"][:8])) if entry["target_session_id"] else ""}'
            f'{(" · " + _e(audit_detail(entry))) if entry["detail"] else ""}</div></div></div>'
            for entry in store.audit_entries(60))
        limits = quota.role_limits(store)
        allowance_forms = "".join(f"""<form method="post" action="/admin/allowances" class="row">{csrf}<input type="hidden" name="role" value="{role}">
<div class="main"><div class="title">{_e(ROLE_LABELS[lang][role])}</div><div class="fields three">
<div><label>{_e(T[lang]['coach_sessions'])}</label><input type="number" min="0" name="coach" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['coach'] is None else limits[role]['coach'])}"></div>
<div><label>{_e(T[lang]['coachee_sessions'])}</label><input type="number" min="0" name="coachee" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['coachee'] is None else limits[role]['coachee'])}"></div>
<div><label>{_e(T[lang]['tokens_per_day'])}</label><input type="number" min="0" step="1000" name="tokens" placeholder="{_e(T[lang]['unlimited'])}" value="{_e('' if limits[role]['tokens'] is None else limits[role]['tokens'])}"></div>
</div></div><div class="actions"><button class="quiet" type="submit">{_e(T[lang]['update'])}</button></div></form>""" for role in ("user", "trainer"))
        votes = store.feedback_totals_since(now - dt.timedelta(days=7))
        ratings = store.ratings_since(now - dt.timedelta(days=30))
        rating_parts = "; ".join(
            text(lang, "ratings_part", module=T[lang]["module_coachee" if module == "coachee" else "module_coach"],
                 average=f"{average:.1f}", count=count)
            for module, (count, average) in sorted(ratings.items())) or T[lang]["ratings_none"]
        warning = f'<div class="flash error">{_e(T[lang]["storage_warning"])}</div>' if settings.storage_warning else ""
        invite_list = "".join(invite_rows) or '<p class="muted">—</p>'
        recent_sessions = "".join(session_row(lang, row, owner_name=row["owner_name"], link=False)
                                  for row in store.recent_sessions(60)) or '<p class="muted">—</p>'
        recent_body = (f'<p class="hint">{_e(T[lang]["recent_sessions_hint"])}</p>'
                       f'<p class="muted">{_e(text(lang, "ratings_summary", parts=rating_parts))}</p>'
                       f'<div class="list">{recent_sessions}</div>')
        members_body = (f'<p class="muted">{_e(text(lang, "feedback_summary", up=votes.get("like", 0), down=votes.get("dislike", 0)))}</p>'
                        f'<div class="list">{"".join(user_rows)}</div>')
        allowance_body = f'<p class="hint">{_e(T[lang]["allowances_hint"])}</p><div class="list">{allowance_forms}</div>'
        audit_body = '<div class="list">' + (audit_rows or '<p class="muted">—</p>') + '</div>'
        body = f"""{warning}{extra}{ai_service_card(lang, now)}
{disclosure(T[lang]['invite_someone'], invite_form(request, lang, '/admin/invites', roles=accounts.ROLES, trainers=trainers), element_id="create-invite")}
{disclosure(T[lang]['invites'], f'<div class="list">{invite_list}</div>', element_id="invites")}
{disclosure(T[lang]['allowances'], allowance_body, element_id="allowances")}
{disclosure(T[lang]['users'], members_body, element_id="users")}
{disclosure(T[lang]['recent_sessions'], recent_body, element_id="recent-sessions")}
{disclosure(T[lang]['audit'], audit_body, element_id="audit-log")}"""
        return render(request, lang, T[lang]["admin"], body, user=user, current="admin")

    @router.get("/admin")
    def admin(request: Request):
        user = checked_user(request, roles=("admin",))
        return admin_page(request, user) if user else login_redirect(request)

    @router.post("/admin/invites")
    def admin_invite(request: Request, csrf: str = Form(""), email: str = Form(""), role: str = Form("user"), trainer_id: str = Form(""),
                     uses: str = Form("1"), days: str = Form("")):
        user = checked_user(request, csrf, roles=("admin",))
        if not user:
            return login_redirect(request)
        role = role if role in accounts.ROLES else "user"
        return admin_page(request, user, new_invite(request, user, role=role, email=email, uses=uses, days=days,
                                                    trainer_id=int(trainer_id) if trainer_id.isdigit() else None))

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
