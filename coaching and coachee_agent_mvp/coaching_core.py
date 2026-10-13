import enum
import functools
import json
import os
import re

import openai


# A hung model call holds one of the shared concurrency slots, so fail fast instead of
# waiting on the SDK default (10 minutes, 2 retries).
LLM_TIMEOUT_SECONDS = 45
LLM_MAX_RETRIES = 1


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
    resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "").strip()
    if not resolved_base_url and api_key.startswith("sk" + "-or-"):
        resolved_base_url = "https://openrouter.ai/api/v1"
    return _shared_client(api_key, resolved_base_url or None)


@functools.lru_cache(maxsize=4)
def _shared_client(api_key: str, base_url: str | None):
    # One client per key/endpoint so concurrent sessions reuse its connection pool.
    kwargs = {"api_key": api_key, "timeout": LLM_TIMEOUT_SECONDS, "max_retries": LLM_MAX_RETRIES}
    if base_url:
        kwargs["base_url"] = base_url
    return openai.Client(**kwargs)


def _stream_text(client, **create_kwargs):
    """Yield the accumulated reply text while a chat completion streams in."""
    text = ""
    stream = client.chat.completions.create(stream=True, **create_kwargs)
    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = getattr(chunk.choices[0].delta, "content", None)
            if delta:
                text += delta
                yield text
    finally:
        stream.close()
    if not text.strip():
        raise ValueError("Model returned no text content.")


# Replies that also decide the stage flow start with one of these markers.
_STAGE_SIGNAL_RE = re.compile(r"\[\[\s*(STAY|NEXT|END)\s*\]\]", re.IGNORECASE)


def _split_stage_signal(raw: str) -> tuple[str | None, str]:
    """Return (signal, visible text). While streaming, text after an unfinished '[[' is held back."""
    match = _STAGE_SIGNAL_RE.search(raw)
    signal = match.group(1).upper() if match else None
    visible = _STAGE_SIGNAL_RE.sub("", raw).split("[[", 1)[0]
    return signal, visible.strip()


def _strip_json_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _translate_texts(api_key: str, texts: list[str], target_lang: str) -> list[str]:
    """Translate several messages in one model call instead of one call per message."""
    target = "Simplified Chinese" if target_lang == "zh" else "English"
    resp = _build_client(api_key).chat.completions.create(
        model=_chat_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    f"Translate each string in the JSON array to {target}. {_language_output_rule(target_lang)} "
                    "Return only a JSON array of the translated strings, in the same order and with the same length."
                ),
            },
            {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
        ],
        max_tokens=min(4000, 300 * len(texts)),
        temperature=0.1,
    )
    translated = json.loads(_strip_json_fence(_response_text(resp)))
    if not isinstance(translated, list) or len(translated) != len(texts):
        raise ValueError("Translation did not return one string per message.")
    return [_clean_response_language(str(text), target_lang) for text in translated]


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
