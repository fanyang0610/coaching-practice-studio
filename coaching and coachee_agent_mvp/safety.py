"""Crisis-language check for the AI Coach module, where users talk about their own lives.

When a message suggests the person may harm themselves, the app answers with a fixed, supportive
message pointing to emergency help instead of continuing the coaching exercise. Many people use the app
from mainland China, where findahelpline.com is less useful, so the reply names the national numbers too.
"""

import re


_CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b",
    r"\bsuicid(e|al)\b",
    r"\bend(ing)? (my|it all|my own) li(fe|ves)\b",
    r"\bend it all\b",
    r"\btake my (own )?life\b",
    r"\b(want|wanted|wish) to die\b",
    r"\bself[- ]?harm",
    r"\b(hurt|hurting|harm|harming|cut|cutting) myself\b",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
    r"\bdon'?t want to (live|be alive|wake up)\b",
    r"\b(don'?t|do not) want to be here any ?more\b",
    r"\bjump(ing)? off (a|the|this) (bridge|building|roof)\b",
    "自杀", "轻生", "寻死", "不想活", "不想再活", "活不下去", "结束生命", "结束自己的生命", "了结自己", "伤害自己", "自残",
    "活着没意思", "活着没有意思", "活着没意义", "活着没有意义", "活着有什么意义", "一了百了", "割腕", "不想醒来",
    "离开这个世界",
    # Not "想死你了" / "可想死我了" (I miss you so much).
    r"想死(?![你您他她它我]|大家)",
    # Not "你去死" / "让他去死", anger at someone else.
    r"(?<![你他她它])去死",
    # Not "跳楼价" / "跳楼大甩卖", shop talk for a price cut.
    r"跳楼(?!价|大甩卖|甩卖)",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)

CRISIS_REPLY = {
    "en": (
        "I'm really sorry you're carrying this. I'm an AI coaching tool, so I can't give you the support you deserve right now. "
        "If you might act on these thoughts or you're in danger, please call your local emergency number now "
        "(in mainland China: 120 for an ambulance, 110 for the police). "
        "In mainland China you can also call 12356, the national psychological help line. "
        "Elsewhere, findahelpline.com lists free, confidential helplines in your country. "
        "Or tell someone you trust how you're feeling. You don't have to handle this alone."
    ),
    "zh": (
        "很抱歉你正在承受这些。我只是一个 AI 教练工具，现在无法给你应得的支持。"
        "如果你可能会伤害自己，或正处于危险中，请立即拨打当地紧急电话（中国大陆：急救 120，报警 110）。"
        "在中国大陆，你也可以拨打全国统一心理援助热线 12356。"
        "在其他国家和地区，可以通过 findahelpline.com 找到当地免费、保密的求助热线。"
        "也可以告诉一位你信任的人你现在的感受。你不必独自面对。"
    ),
}


def looks_like_crisis(text: str) -> bool:
    return bool(_CRISIS_RE.search(text or ""))
