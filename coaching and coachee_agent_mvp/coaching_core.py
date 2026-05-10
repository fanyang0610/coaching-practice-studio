import enum
import os
import re

import openai


class CoachingState(enum.Enum):
    CONTRACT = 1
    EXPERIENCE = 2
    ACTION = 3
    VALUE = 4
    CLOSING = 5


class CoachingSubPhase(enum.Enum):
    OPEN = 1
    DEEPEN = 2
    BRIDGE = 3


STAGE_DESCRIPTIONS = {
    CoachingState.CONTRACT: "Establish a clear, measurable coaching goal for this session.",
    CoachingState.EXPERIENCE: "Explore the client's current reality, strengths, and resources.",
    CoachingState.ACTION: "Brainstorm creative options and possible next steps.",
    CoachingState.VALUE: "Commit to a specific plan with accountability and timeline.",
    CoachingState.CLOSING: "Acknowledge progress, summarise insights, and close the session.",
}


def _chat_model() -> str:
    return os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"


def _build_client(api_key: str, base_url: str | None = None):
    kwargs = {"api_key": api_key}
    resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "").strip()
    if resolved_base_url:
        kwargs["base_url"] = resolved_base_url
    elif api_key.startswith("sk" + "-or-"):
        kwargs["base_url"] = "https://openrouter.ai/api/v1"
    return openai.Client(**kwargs)


def _content_text(content) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
            else:
                text = getattr(item, "text", None) or getattr(item, "content", None) or ""

            if isinstance(text, list):
                text = _content_text(text)

            text = str(text).strip()
            if text:
                parts.append(text)

        return "\n".join(parts).strip()

    return ""


def _response_text(resp) -> str:
    message = resp.choices[0].message
    text = _content_text(getattr(message, "content", None))
    if text:
        return text

    refusal = _content_text(getattr(message, "refusal", None))
    if refusal:
        raise ValueError(refusal)

    raise ValueError("Model returned no text content.")


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_ZH_LATIN_PAREN_RE = re.compile(r"\s*[\(（]([^()（）\u4e00-\u9fff]*[A-Za-z][^()（）\u4e00-\u9fff]*)[\)）]")


def _language_output_rule(language: str) -> str:
    if language == "zh":
        return (
            "Respond only in Simplified Chinese. Do not include pinyin, romanization, "
            "English translations, bilingual parentheses, language labels, or explanations."
        )
    return "Respond only in English. Do not include Chinese translations, pinyin, or bilingual parentheses."


def _clean_response_language(text: str, language: str) -> str:
    cleaned = (text or "").strip()
    if language != "zh" or not cleaned:
        return cleaned

    def strip_parenthetical(match: re.Match) -> str:
        inner = match.group(1).strip()
        if re.fullmatch(r"[A-Z0-9+\-]{2,8}", inner):
            return match.group(0)
        return ""

    cleaned = _ZH_LATIN_PAREN_RE.sub(strip_parenthetical, cleaned)
    lines: list[str] = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        has_cjk = bool(_CJK_RE.search(stripped))
        has_latin = bool(_LATIN_RE.search(stripped))
        if has_latin and not has_cjk:
            continue
        lines.append(stripped)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
