import enum
import functools
import json
import logging
import os
import re
import time
import types
import urllib.request

import openai


# A hung model call holds one of the shared concurrency slots, so fail fast instead of
# waiting on the SDK default (10 minutes, 2 retries).
LLM_TIMEOUT_SECONDS = 45
LLM_MAX_RETRIES = 1
# The service sometimes answers "too busy" (429) or has a brief outage, and the OpenAI client's own retry comes within
# half a second. Two more tries a few seconds apart, but never after a timeout, so nobody waits minutes.
BUSY_RETRY_DELAYS = (1.5, 3.0)

# Called with the exception when a model request has finally failed (after the retries), e.g. when the AI account has
# run out of credit. The web app sets it, so the Admin page can say the AI is failing before anyone has to complain.
on_request_failure = None


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


def _build_client(api_key: str, base_url: str | None = None, on_usage=None):
    """The shared client; with on_usage, every completion also reports (model, prompt_tokens, completion_tokens)."""
    resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL", "").strip()
    if not resolved_base_url and api_key.startswith("sk" + "-or-"):
        resolved_base_url = "https://openrouter.ai/api/v1"
    client = _shared_client(api_key, resolved_base_url or None)
    extra_body = _provider_extra_body(resolved_base_url)
    return _MeteredClient(client, on_usage, extra_body)


# On OpenRouter, send requests only to hosts that don't collect what they're sent: people bring their real lives to the
# AI Coach. Tested October 2026 with deepseek/deepseek-chat: both of its hosts (DeepInfra, USA, and StreamLake, China)
# qualify, so this costs no availability. {"provider": {"zdr": true}} (zero retention) is stricter: only DeepInfra.
OPENROUTER_PRIVACY = {"provider": {"data_collection": "deny"}}


def _provider_extra_body(base_url: str | None) -> dict:
    """Provider-specific request fields: known defaults, with OPENAI_EXTRA_BODY (JSON) on top, winning on any field it sets.

    DeepSeek turns "thinking" on by default, which spends the short reply budgets on hidden
    reasoning and returns empty replies, so it is switched off. OpenRouter gets OPENROUTER_PRIVACY.
    """
    defaults: dict = {}
    if "deepseek.com" in (base_url or ""):
        defaults = {"thinking": {"type": "disabled"}}
    elif "openrouter.ai" in (base_url or ""):
        defaults = json.loads(json.dumps(OPENROUTER_PRIVACY))
    raw = os.environ.get("OPENAI_EXTRA_BODY", "").strip()
    return {**defaults, **json.loads(raw)} if raw else defaults


def _estimate_tokens(text: str) -> int:
    # Fallback when a provider omits usage: roughly 3 characters per token across English and Chinese.
    return max(1, len(text) // 3)


def _report_usage(on_usage, create_kwargs: dict, usage, output_text: str) -> None:
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None:
        prompt_tokens = _estimate_tokens(json.dumps(create_kwargs.get("messages", []), ensure_ascii=False))
    if completion_tokens is None:
        completion_tokens = _estimate_tokens(output_text)
    try:
        on_usage(create_kwargs.get("model", ""), prompt_tokens, completion_tokens)
    except Exception:
        logging.getLogger("coaching_studio").exception("Recording model usage failed")


class _MeteredClient:
    """Adds provider request fields to every completion, reports failed requests and, with on_usage, token usage."""

    def __init__(self, client, on_usage=None, extra_body: dict | None = None):
        self.client = client  # the shared OpenAI client underneath (see _shared_client)
        self.chat = types.SimpleNamespace(completions=_MeteredCompletions(client.chat.completions, on_usage, extra_body))


def _is_brief_outage(exc: Exception) -> bool:
    if isinstance(exc, openai.APITimeoutError):
        return False
    return isinstance(exc, (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError))


def _create_with_busy_retry(create, **create_kwargs):
    for delay in (*BUSY_RETRY_DELAYS, None):
        try:
            return create(**create_kwargs)
        except Exception as exc:
            if delay is None or not _is_brief_outage(exc):
                _report_failure(exc)
                raise
            logging.getLogger("coaching_studio").warning("AI service busy (%s); trying again in %.1f s", type(exc).__name__, delay)
            time.sleep(delay)


def _report_failure(exc: Exception) -> None:
    if on_request_failure is None:
        return
    try:
        on_request_failure(exc)
    except Exception:
        logging.getLogger("coaching_studio").exception("Recording a failed AI request failed")


def failure_summary(exc: Exception) -> str:
    """A short description of a failed request for the admin, e.g. "402: Insufficient credits". Error messages come
    from the provider and never contain the conversation."""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    message = ""
    if isinstance(body, dict):
        error = body.get("error", body)
        message = error.get("message", "") if isinstance(error, dict) else str(error)
    message = message or getattr(exc, "message", "") or str(exc) or type(exc).__name__
    return f"{status}: {message}" if status else f"{type(exc).__name__}: {message}"


def openrouter_credit_left(api_key: str, base_url: str | None = None, timeout: float = 5) -> float | None:
    """Dollars left on the OpenRouter account behind a key, or None when the model isn't on OpenRouter or the balance
    can't be read right now."""
    resolved = base_url or ("https://openrouter.ai/api/v1" if api_key.startswith("sk" + "-or-") else "")
    if not api_key or "openrouter.ai" not in resolved:
        return None
    request = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response).get("data", {})
        return float(data["total_credits"]) - float(data["total_usage"])
    except Exception:
        logging.getLogger("coaching_studio").warning("Reading the OpenRouter balance failed", exc_info=True)
        return None


class _MeteredCompletions:
    def __init__(self, completions, on_usage=None, extra_body: dict | None = None):
        self._completions = completions
        self._on_usage = on_usage
        self._extra_body = extra_body or {}

    def create(self, **create_kwargs):
        if self._extra_body:
            create_kwargs["extra_body"] = {**self._extra_body, **create_kwargs.get("extra_body", {})}
        create = self._completions.create
        if not self._on_usage:
            return _create_with_busy_retry(create, **create_kwargs)
        if create_kwargs.get("stream"):
            create_kwargs.setdefault("stream_options", {"include_usage": True})
            return _MeteredStream(_create_with_busy_retry(create, **create_kwargs), create_kwargs, self._on_usage)
        response = _create_with_busy_retry(create, **create_kwargs)
        message = response.choices[0].message if response.choices else None
        _report_usage(self._on_usage, create_kwargs, getattr(response, "usage", None),
                      _content_text(getattr(message, "content", None)))
        return response


class _MeteredStream:
    """Passes chunks through and reports usage once, when the stream ends or is closed early."""

    def __init__(self, stream, create_kwargs: dict, on_usage):
        self._stream = stream
        self._create_kwargs = create_kwargs
        self._on_usage = on_usage
        self._usage = None
        self._text = ""
        self._reported = False

    def __iter__(self):
        try:
            for chunk in self._stream:
                if getattr(chunk, "usage", None):
                    self._usage = chunk.usage
                if chunk.choices:
                    self._text += getattr(chunk.choices[0].delta, "content", None) or ""
                yield chunk
        finally:
            self._report()

    def close(self):
        self._stream.close()
        self._report()

    def _report(self):
        if not self._reported:
            self._reported = True
            _report_usage(self._on_usage, self._create_kwargs, self._usage, self._text)


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


# Replies that also place the conversation in a stage start with a marker naming the stage the talk is working on
# ([[GOAL]] to [[CLOSING]]), or [[END]] once the session is over. STAY, NEXT and numbers are older forms, still understood.
STAGE_MARKERS = {1: "GOAL", 2: "REALITY", 3: "OPTIONS", 4: "COMMITMENT", 5: "CLOSING"}
_STAGE_SIGNAL_RE = re.compile(r"\[\[\s*(STAY|NEXT|END|GOAL|REALITY|OPTIONS|COMMITMENT|CLOSING|[1-5])\s*\]\]", re.IGNORECASE)

# Naming the stage the talk is in is something models do reliably; asked instead to decide when to move on, they
# nearly always stayed, so the tracker sat on the first stage while the conversation had moved on. Words, with the
# kinds of question each covers, worked better than stage numbers, which models tended to copy from turn to turn.
STAGE_MARKER_GUIDE = """[[GOAL]] what they want from this session and how they will know they got it
[[REALITY]] what is happening now, what they have tried, what already works, past successes, strengths and resources
[[OPTIONS]] ideas for moving forward: what they could try, what else is possible
[[COMMITMENT]] choosing what to do: which option, the first step, when, what support they need, what might get in the way
[[CLOSING]] wrapping up: what they are taking away, how they feel now compared with the start, acknowledging their progress"""


def _marker(state: CoachingState) -> str:
    return f"[[{STAGE_MARKERS.get(state.value, 'END')}]]"


def _as_written(msg: dict) -> str:
    """A past reply with its stage marker put back. Models copy their earlier replies: shown them without markers,
    they stopped writing markers after two or three turns, and the stage stopped moving."""
    stage = msg.get("stage")
    if not stage:
        return msg["content"]
    return f"[[{STAGE_MARKERS.get(stage, 'END')}]] {msg['content']}"


def _labelled_stage(signal: str | None, current: CoachingState) -> CoachingState:
    """The stage a marker puts the conversation in. It never goes back; [[END]] is handled by the agents."""
    numbers = {word: number for number, word in STAGE_MARKERS.items()}
    if signal in numbers:
        signal = str(numbers[signal])
    if not signal or not signal.isdigit():
        return current
    return CoachingState(max(current.value, min(int(signal), CoachingState.CLOSING.value)))


def _split_stage_signal(raw: str) -> tuple[str | None, str]:
    """Return (signal, visible text). While streaming, text after an unfinished '[[' is held back."""
    match = _STAGE_SIGNAL_RE.search(raw)
    signal = match.group(1).upper() if match else None
    visible = _STAGE_SIGNAL_RE.sub("", raw).split("[[", 1)[0]
    return signal, visible.strip()


def _conversation_window(context: list[dict], head: int = 6, tail: int = 16) -> list[dict]:
    """The start of a conversation, where the goal is agreed, plus its most recent messages.

    Short sessions are sent whole; long ones keep the goal in view without the cost growing with every turn.
    """
    if len(context) <= head + tail:
        return list(context)
    return list(context[:head]) + list(context[-tail:])


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


def _repair_json_brackets(raw: str) -> str:
    """Fix mismatched closing brackets, the slip models make most in long JSON (often in Chinese).

    A list closed with '}' is read as a missing ']' when more text follows (`["a", "b"}, "next"`), or as a ']' typed
    as '}' when another closer follows (`["a", "b"}}`). Anything still open at the end is closed.
    """
    out: list[str] = []
    stack: list[str] = []
    in_string = escaped = False
    for index, ch in enumerate(raw):
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "[":
            stack.pop()
            following = raw[index + 1:].lstrip()[:1]
            if following in ("}", "]"):
                out.append("]")
                continue
            out.append("]")
            if stack:
                stack.pop()
        elif ch == "]" and stack and stack[-1] == "{":
            stack.pop()
            out.append("}")
            if stack:
                stack.pop()
        elif ch in "]}":
            if not stack:
                continue
            stack.pop()
        out.append(ch)
    out.extend("]" if opener == "[" else "}" for opener in reversed(stack))
    return "".join(out)


def _json_completion(client, *, messages: list[dict], max_tokens: int, temperature: float, attempts: int = 2):
    """Ask the model for a JSON object and return it parsed.

    Uses the provider's JSON mode, repairs mismatched brackets, and asks once more (cooler) before giving up.
    The prompt must mention JSON, which JSON mode requires.
    """
    error: Exception | None = None
    for attempt in range(attempts):
        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature if attempt == 0 else min(temperature, 0.3),
            response_format={"type": "json_object"},
        )
        raw = _strip_json_fence(_response_text(resp))
        for candidate in (raw, _repair_json_brackets(raw)):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                error = exc
    raise error


def _translate_texts(api_key: str, texts: list[str], target_lang: str, on_usage=None) -> list[str]:
    """Translate several messages in one model call instead of one call per message."""
    target = "Simplified Chinese" if target_lang == "zh" else "English"
    data = _json_completion(
        _build_client(api_key, on_usage=on_usage),
        messages=[
            {
                "role": "system",
                "content": (
                    f"Translate each string in the JSON array to {target}. {_language_output_rule(target_lang)} "
                    'Return a JSON object {"translations": [...]} holding the translated strings, in the same order and with the same length.'
                ),
            },
            {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
        ],
        max_tokens=min(4000, 300 * len(texts)),
        temperature=0.1,
    )
    translated = data.get("translations") if isinstance(data, dict) else data
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


_WRAPPING_QUOTES = {'"': '"', "“": "”", "'": "'", "「": "」", "『": "』"}


def _strip_wrapping_quotes(text: str) -> str:
    """Drop quote marks a model sometimes puts around its whole reply."""
    close = _WRAPPING_QUOTES.get(text[:1])
    if close and len(text) > 2 and text.endswith(close) and text[0] not in text[1:-1] and close not in text[1:-1]:
        return text[1:-1].strip()
    return text


def _clean_response_language(text: str, language: str) -> str:
    cleaned = _strip_wrapping_quotes((text or "").strip())
    if cleaned[:2] in ("- ", "• ") and "\n- " not in cleaned and "\n• " not in cleaned:
        cleaned = cleaned[2:].lstrip()  # a stray bullet in front of a one-paragraph reply
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
