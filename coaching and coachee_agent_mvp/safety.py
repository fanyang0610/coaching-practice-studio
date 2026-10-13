"""Crisis-language check for the AI Coach module, where users talk about their own lives.

When a message suggests the person may harm themselves, the app answers with a fixed, supportive
message pointing to emergency help instead of continuing the coaching exercise.
"""

import re


_CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b",
    r"\bsuicid(e|al)\b",
    r"\bend(ing)? (my|it all|my own) li(fe|ves)\b",
    r"\bend it all\b",
    r"\b(want|wanted|wish) to die\b",
    r"\bself[- ]?harm",
    r"\b(hurt|hurting|harm|harming|cut|cutting) myself\b",
    r"\bno reason to live\b",
    r"\bbetter off dead\b",
    r"\bdon'?t want to (live|be alive)\b",
    "自杀", "轻生", "不想活", "活不下去", "结束生命", "结束自己的生命", "伤害自己", "自残", "想死", "去死",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)

CRISIS_REPLY = {
    "en": (
        "I'm really sorry you're carrying this. I'm an AI coaching tool, so I can't give you the support you deserve right now. "
        "If you might act on these thoughts or you're in danger, please call your local emergency number now. "
        "You can also reach a free, confidential helpline in your country through findahelpline.com, "
        "or tell someone you trust how you're feeling. You don't have to handle this alone."
    ),
    "zh": (
        "很抱歉你正在承受这些。我只是一个 AI 教练工具，现在无法给你应得的支持。"
        "如果你可能会伤害自己，或正处于危险中，请立即拨打当地紧急电话。"
        "你也可以通过 findahelpline.com 找到你所在国家的免费保密求助热线，或告诉一位你信任的人你现在的感受。你不必独自面对。"
    ),
}


def looks_like_crisis(text: str) -> bool:
    return bool(_CRISIS_RE.search(text or ""))
