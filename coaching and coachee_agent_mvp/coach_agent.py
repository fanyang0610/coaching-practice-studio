import json
import logging
import random
import re
import uuid

from coaching_core import CoachingState, CoachingSubPhase, STAGE_DESCRIPTIONS, STAGE_MARKER_GUIDE, _as_written, _build_client, _chat_model, _clean_response_language, ContextCapacityError, _json_completion, _labelled_stage, _language_output_rule, _marker, _response_text, _split_stage_signal, _stream_text, _translate_texts
from coach_data import (
    ACKNOWLEDGMENTS,
    BRIDGE_PHRASES,
    CLOSING_MESSAGES,
    DEEPENING_QUESTIONS,
    OPENING_QUESTIONS,
    TRANSLATE_EN_TO_ZH,
    TRANSLATE_ZH_TO_EN,
    _translate_template_message,
)


ACTION_CARD_FIELDS = ("goal", "next_step", "by_when", "support")


def can_recover_action_card(row: dict, state: dict) -> bool:
    """Only missing results of finished AI-coach conversations can be recovered."""
    return (row["module"] == "coach" and row["status"] == "completed" and row["mode"] == "llm"
            and not row.get("card") and state.get("action_card_result", {}).get("status") != "ready"
            and any(m.get("role") == "client" for m in state.get("context", [])))


# After this many client turns in one stage, the AI coach is asked to sum up and move on.
STAGE_NUDGE_TURNS = 5

# These are writing directions, not canned lines. An opaque random seed alone gave the model almost identical openings.
OPENING_APPROACHES = {"en": (
    "Go straight into a relaxed invitation to choose where to begin. No greeting or introductory sentence this time.",
    "Start with a short, casual welcome, then invite whatever is on their mind. Keep it like spoken conversation.",
    "Briefly make room for thoughts that aren't sorted out yet, then invite a starting point. Don't require a clear goal.",
    "Invite something they would enjoy having space to talk through. It needn't be a problem to solve. Skip the greeting.",
    "Open with curiosity about what they would like to get out of talking together, without asking for a formal goal "
    "or measurable result. Use an easy, conversational question.",
    "Offer a brief, unhurried welcome and let them pick up whichever thread they choose. Don't tell them how they feel.",
), "zh": (
    "直接用一句自然的问话，邀请对方选一个起点，不加招呼或铺垫。",
    "先简短、随意地打个招呼，再好奇地问问对方此刻想说些什么，像刚碰面时聊天。",
    "先用一句口语让对方知道，想法还没整理好也可以说，再问一个轻松的开放问题。",
    "邀请对方讲一件想找人聊聊的事，不必是烦恼或需要解决的问题，不加招呼。",
    "好奇地问问对方希望这段聊天带来什么，不要求明确目标，语气轻松，不像填表。",
    "先用一句简短的话留一点从容的空间，再让对方自己选从哪儿说起，不猜测对方的心情。",
)}

# What a good coach works on in each stage, for the AI coach's own instructions.
STAGE_FOCUS = {
    CoachingState.CONTRACT: "goal: agree what they want from this conversation, why it matters to them, and how they will "
                            "know at the end that it helped",
    CoachingState.EXPERIENCE: "reality: what is happening now, what they have tried, times when it already goes a little "
                              "better, their strengths, and who or what helps; a scale from 1 to 10 can help",
    CoachingState.ACTION: "options: help them find several possibilities of their own; ask what else they could do, and "
                          "don't settle on the first idea too soon",
    CoachingState.VALUE: "commitment: help them choose, then make it concrete: the first small step, when, what might get "
                         "in the way, who could support them, and how confident they feel",
    CoachingState.CLOSING: "closing: invite them to say what they are taking away and how they feel now compared with the "
                           "start, then say goodbye",
}

# The rhythm of a real coach. Told only not to parrot, the AI coach still opened nearly every English reply by restating
# the client's words, then copied that habit from its own earlier replies. Coach lines only: shown a whole dialogue,
# it once went on to write the client's answer too.
RHYTHM_EXAMPLE = {
    "en": "What would you do with an hour to yourself? / Mm. When did you last read something you enjoyed? / "
          "What was different then? / That sounds exhausting. What keeps you going on days like that? / "
          "Not checking your phone. How did you manage that?",
    "zh": "如果有一个小时完全属于你，你会做什么？ / 嗯。上一次读到喜欢的书是什么时候？ / 那时候有什么不一样？ / "
          "听起来真的很累。那样的日子里，是什么让你撑下来的？ / 没老看手机。你是怎么做到的？",
}


# The first sentence of a reply, up to its first full stop, exclamation or question mark.
_FIRST_SENTENCE_RE = re.compile(r"^[^.!?。！？]*[.!?。！？]")


def _opens_with_comment(reply: str) -> bool:
    """Whether a reply says something before its question ("A rough draft first. What would it take...?")."""
    first = _FIRST_SENTENCE_RE.match(reply.strip())
    return bool(first) and first.group(0)[-1] not in "?？" and ("?" in reply or "？" in reply)


# A question mark that ends a question (not one inside quotes), and anything written after it.
_AFTER_QUESTION_RE = re.compile(r"[?？](?![\"'”’」』])\s*(\S.*)$", re.DOTALL)


def _end_at_question(text: str) -> tuple[str, bool]:
    """A coaching reply ends with its one question. Now and then the model kept writing past it, into a stray word and
    then the client's next answer, so anything after the first question is cut. Returns (text, whether it was cut)."""
    match = _AFTER_QUESTION_RE.search(text)
    if not match:
        return text, False
    return text[:match.start(1)].rstrip(), True


# Put beside the client's latest message when the coach's last reply opened with a comment (see _get_llm_response).
STRAIGHT_TO_QUESTION_NOTE = {
    "en": "[Note to the coach, not from the client: start with your stage marker as usual. Your last reply opened with "
          "a comment before its question, so go straight to your question this time, unless the client has just shared "
          "something painful; then acknowledge it in a few words first.]",
    "zh": "[给教练的提示，不是来访者说的话：照常先写阶段标记。你上一条回复在提问前先复述或评论了一句，这一次请直接提问；"
          "如果对方刚说了很痛苦的事，就先用几个字回应一下。]",
}

# When the client has used every message a conversation allows. The action card follows, as after any goodbye.
LIMIT_GOODBYE = {
    "en": "We've covered a lot in this conversation, so let's stop here for today. Thank you for the thought you've put in.",
    "zh": "这次我们已经聊了很多，今天就先到这里吧。谢谢你认真的投入。",
}


class CoachAgent:
    assistant_role = "coach"
    user_role = "client"

    def __init__(self, mode="template", language="en", user_profile=None, *, fresh_start=False):
        self.mode = mode
        self.language = language
        self.current_state = CoachingState.CONTRACT
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.context: list[dict[str, str]] = []
        self.turns_in_current_stage = 0
        self._last_template: str | None = None
        self.user_profile = user_profile
        self.fresh_start = fresh_start
        # Called with (model, prompt_tokens, completion_tokens) after each model call; set by the web app.
        self.on_usage = None
        self.opening_variation_seed = uuid.uuid4().hex[:8]
        # The action card from this person's previous session, set by the web app so the opening can follow up on it.
        self.last_card: dict | None = None
        # A derived artifact, kept outside the original dialogue.
        self.action_card_result: dict = {}
        # The closing stage is a conversation of its own; the session ends when the coach says goodbye.
        self.session_complete = False
        # Stages the conversation jumped over, shown as skipped rather than done.
        self.skipped_stages: set[int] = set()

    def set_mode(self, mode: str) -> bool:
        if mode in ("template", "llm"):
            self.mode = mode
            return True
        return False

    def set_language(self, language: str) -> bool:
        if language in ("en", "zh"):
            self.language = language
            return True
        return False

    def is_session_ended(self) -> bool:
        return self.session_complete

    def to_dict(self) -> dict:
        """Everything needed to resume this conversation later (the user profile is stored separately)."""
        return {
            "mode": self.mode,
            "language": self.language,
            "state": self.current_state.name,
            "sub_phase": self.current_sub_phase.name,
            "context": self.context,
            "turns": self.turns_in_current_stage,
            "last_template": self._last_template,
            "seed": self.opening_variation_seed,
            "fresh_start": self.fresh_start,
            "session_complete": self.session_complete,
            "skipped": sorted(self.skipped_stages),
            "action_card_result": self.action_card_result,
        }

    @classmethod
    def from_dict(cls, data: dict, user_profile=None) -> "CoachAgent":
        agent = cls(mode=data["mode"], language=data["language"], user_profile=user_profile,
                    fresh_start=data.get("fresh_start", False))
        agent.current_state = CoachingState[data["state"]]
        agent.current_sub_phase = CoachingSubPhase[data["sub_phase"]]
        agent.context = list(data["context"])
        agent.turns_in_current_stage = data["turns"]
        agent._last_template = data.get("last_template")
        agent.opening_variation_seed = data["seed"]
        # Sessions saved before closing became a stage of its own ended on reaching it.
        agent.session_complete = data.get("session_complete", agent.current_state == CoachingState.CLOSING)
        agent.skipped_stages = set(data.get("skipped", []))
        agent.action_card_result = data.get("action_card_result", {})
        return agent

    def get_stage_prompt(self, api_key: str | None = None) -> str:
        prompt = ""
        for prompt, _ in self._stream_stage_prompt(api_key):
            pass
        return prompt

    def _stream_stage_prompt(self, api_key: str | None = None, decide_stage: bool = False):
        """Yield (text so far, stage signal) pairs; the last pair holds the final prompt."""
        if self.session_complete:
            # Reached by skipping ahead: close with a real goodbye when the AI is available.
            if self.mode == "llm" and api_key and self.context:
                try:
                    yield self._get_llm_closing_summary(api_key), None
                    return
                except Exception:
                    pass
            yield random.choice(CLOSING_MESSAGES[self.language]), None
            return

        if self.mode == "template":
            yield self._get_template_response(), None
            return

        if not api_key:
            raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")

        if not self.context and self.current_sub_phase == CoachingSubPhase.OPEN:
            yield self._get_llm_opening_response(api_key), None
            return

        yield from self._get_llm_response(api_key, decide_stage)

    def end_at_limit(self, limit: int, api_key: str | None = None) -> str:
        """The client used every message a conversation allows: a short goodbye ends the session."""
        self.session_complete = True
        goodbye = LIMIT_GOODBYE[self.language]
        self.context.append({"role": self.assistant_role, "content": goodbye})
        return goodbye

    def force_next_state(self) -> bool:
        """Skip Ahead: the next stage. From the closing stage it ends the session, and so does reaching closing in
        template mode, which has no closing conversation."""
        if self.session_complete:
            return False
        if self.current_state == CoachingState.CLOSING:
            self.session_complete = True
        else:
            self.current_state = CoachingState(self.current_state.value + 1)
            self.session_complete = self.current_state == CoachingState.CLOSING and self.mode != "llm"
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.turns_in_current_stage = 0
        return True

    def generate_response(self, user_input: str, api_key: str | None = None) -> str:
        response = ""
        for response in self.stream_response(user_input, api_key):
            pass
        return response

    def stream_response(self, user_input: str, api_key: str | None = None):
        """Yield the coach reply as it streams in; the last value is the final reply."""
        if self.mode == "llm" and not api_key:
            raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")

        old_state = self.current_state
        old_sub = self.current_sub_phase
        old_turns = self.turns_in_current_stage
        old_context_len = len(self.context)
        decide_stage = False

        if user_input and user_input.strip():
            self.context.append({"role": "client", "content": user_input.strip()})
            self.turns_in_current_stage += 1
            decide_stage = self._evaluate_state_transition(api_key)

        if self.session_complete:
            if self.mode == "llm" and api_key:
                try:
                    response = self._get_llm_closing_summary(api_key)
                except Exception:
                    response = random.choice(CLOSING_MESSAGES[self.language])
            else:
                response = random.choice(CLOSING_MESSAGES[self.language])
            self.context.append({"role": "coach", "content": response})
            yield response
            return

        try:
            for attempt in range(2):
                try:
                    response, signal = "", None
                    for response, signal in self._stream_stage_prompt(api_key, decide_stage):
                        if response:
                            yield response
                    break
                except Exception as exc:
                    # An empty reply (or one in the wrong language, emptied by the clean-up) gets one more try. There is
                    # no canned stand-in: the web app keeps the client's message and asks them to send it again.
                    if attempt or "Model returned no text content" not in str(exc):
                        raise
        except Exception as exc:
            self.current_state = old_state
            self.current_sub_phase = old_sub
            self.turns_in_current_stage = old_turns
            self.session_complete = False
            self.context = self.context[:old_context_len]
            raise exc

        reply = {"role": "coach", "content": response}
        if decide_stage or signal == "END":
            self._apply_stage_signal(signal)
            reply["stage"] = "END" if self.is_session_ended() else self.current_state.value
        self.context.append(reply)

    def _get_llm_closing_summary(self, api_key: str) -> str:
        client = _build_client(api_key, on_usage=self.on_usage)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a warm solution-focused coach, and this coaching conversation is ending now. "
                    "Say goodbye in two or three plain, warm sentences that reflect what the client worked out and "
                    "their next step, in their own words. No question, no grand praise, no coaching jargon. "
                    f"Respond ONLY in {lang_instr}. {_language_output_rule(self.language)}"
                ),
            }
        ]
        for msg in self.context:
            role = "user" if msg["role"] == "client" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        # A stray stage marker would show in the chat: models see markers in the other replies of this conversation.
        return _clean_response_language(_split_stage_signal(_response_text(resp))[1], self.language)

    def translate_history(self, new_lang: str, api_key: str | None = None) -> bool:
        """Translate the coach's messages into new_lang. Returns False, changing nothing, if the AI couldn't translate."""
        if self.language == new_lang:
            return True

        dict_map = TRANSLATE_EN_TO_ZH if new_lang == "zh" else TRANSLATE_ZH_TO_EN
        updates: dict[int, str] = {}
        llm_items: list[tuple[int, str]] = []
        for idx, msg in enumerate(self.context):
            if msg["role"] != "coach":
                continue
            translated = _translate_template_message(msg["content"], self.language, dict_map)
            if translated is not None:
                updates[idx] = translated
            else:
                llm_items.append((idx, msg["content"]))

        if llm_items and api_key and self.mode == "llm":
            try:
                texts = _translate_texts(api_key, [text for _, text in llm_items], new_lang, on_usage=self.on_usage)
            except Exception:
                logging.getLogger("coaching_studio").warning("Translating the conversation failed", exc_info=True)
                return False
            updates.update({idx: text for (idx, _), text in zip(llm_items, texts)})

        for idx, text in updates.items():
            self.context[idx]["content"] = text
        self.language = new_lang
        return True

    def _evaluate_state_transition(self, api_key: str | None = None) -> bool:
        """Advance the stage flow for a new client turn. Returns True when the LLM reply should decide it."""
        if self.mode == "llm" and api_key:
            # Every AI reply names the stage it works on (_apply_stage_signal); a long stage gets a nudge to move on.
            nudge = self.turns_in_current_stage >= STAGE_NUDGE_TURNS
            self.current_sub_phase = CoachingSubPhase.BRIDGE if nudge else CoachingSubPhase.DEEPEN
            return True

        if self.current_sub_phase == CoachingSubPhase.OPEN:
            self.current_sub_phase = CoachingSubPhase.DEEPEN
            return False

        if self.current_sub_phase == CoachingSubPhase.DEEPEN:
            if self.turns_in_current_stage >= 4:
                self.current_sub_phase = CoachingSubPhase.BRIDGE
            return False

        states = list(CoachingState)
        idx = states.index(self.current_state)
        if idx < len(states) - 1:
            self.current_state = states[idx + 1]
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0
        # Template mode asks its closing question at the end of commitment; the answer ends the session.
        self.session_complete = self.current_state == CoachingState.CLOSING
        return False

    def _move_to(self, stage: CoachingState):
        """Go forward to a stage; any stage jumped over is remembered as skipped."""
        self.skipped_stages.update(range(self.current_state.value + 1, stage.value))
        self.current_state = stage

    def _apply_stage_signal(self, signal: str | None):
        if signal == "END":
            self._move_to(CoachingState.CLOSING)
            self.session_complete = True
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0
            return
        stage = _labelled_stage(signal, self.current_state)
        if signal == "NEXT" or (signal is None and self.current_sub_phase == CoachingSubPhase.BRIDGE):
            # No marker on a reply that was asked to move on: take it that it did, as template mode would.
            stage = CoachingState(min(self.current_state.value + 1, CoachingState.CLOSING.value))
        if stage != self.current_state:
            # The reply has already opened the new stage, so the tracker moves now, not after the client's answer.
            self._move_to(stage)
            self.current_sub_phase = CoachingSubPhase.DEEPEN
            self.turns_in_current_stage = 0

    def _stage_decision_rules(self) -> str:
        here = _marker(self.current_state)
        if self.current_state == CoachingState.CLOSING:
            move_on = "say goodbye with [[END]]"
        elif self.current_state == CoachingState.VALUE:
            move_on = "move on with [[CLOSING]]: invite them to say what they are taking away from today"
        else:
            move_on = (f"move on with {_marker(CoachingState(self.current_state.value + 1))}: link it in a few words to "
                       "what they said (now and then asking whether they are ready), then ask one opening question for "
                       "that stage")
        nudge = ""
        if self.current_sub_phase == CoachingSubPhase.BRIDGE:
            nudge = f"\nThis stage has already taken {self.turns_in_current_stage} exchanges. Unless the client is in the middle of something important, now {move_on}."
        return f"""

REQUIRED OUTPUT FORMAT: the very first characters of your output must be one marker, then your reply.
The marker names the stage your reply works on:
{STAGE_MARKER_GUIDE}
[[END]] - say goodbye: two or three warm, plain sentences that reflect what they worked out and their next step, in their words, with no question and no grand praise. Use it once they have answered your closing question, or straight away if the client says they want to finish (goodbye, that's all for today, I have to go). Before [[COMMITMENT]], use it only if the client asks to finish. A thank-you on its own is not a request to finish.
The conversation has reached {here}. Stay with {here} while this stage still needs work; a short look back at an earlier topic keeps {here} too. Once it has done its job, {move_on}. If the client has already moved on to a later stage, follow them and use that stage's marker. Never use the marker of an earlier stage.{nudge}
Example output: [[REALITY]] Two calm evenings a week. What are your evenings like at the moment?
Never mention the marker or stage names in the reply itself."""

    def _end_only_rules(self) -> str:
        """Between stage decisions the client can still finish, so a goodbye always really closes the session."""
        return """

REQUIRED OUTPUT FORMAT: the very first characters of your output must be one marker, then your reply.
[[STAY]] - continue the coaching as guided above. Use this almost always.
[[END]] - only if the client clearly says they want to finish now (for example "that's all for today", goodbye, or they need to go): give a brief, warm closing summary that acknowledges their progress and commitments, with no question.
A thank-you on its own is not a request to finish: acknowledge it and continue with your question.
Never mention the marker in the reply itself."""

    def _get_template_response(self) -> str:
        lang = self.language
        state = self.current_state
        sub = self.current_sub_phase
        ack = random.choice(ACKNOWLEDGMENTS[lang])

        if sub == CoachingSubPhase.OPEN:
            return random.choice(OPENING_QUESTIONS[lang][state])

        if sub == CoachingSubPhase.DEEPEN:
            options = DEEPENING_QUESTIONS[lang][state]
            if len(options) > 1 and self._last_template in options:
                options = [q for q in options if q != self._last_template]
            question = random.choice(options)
            self._last_template = question
            return f"{ack} {question}"

        bridge = BRIDGE_PHRASES[lang][state]
        states = list(CoachingState)
        next_state = states[states.index(state) + 1]
        next_question = random.choice(OPENING_QUESTIONS[lang][next_state])
        return f"{ack} {bridge} {next_question}"

    def _get_llm_opening_response(self, api_key: str) -> str:
        client = _build_client(api_key, on_usage=self.on_usage)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        approaches = OPENING_APPROACHES[self.language]
        approach = approaches[int(self.opening_variation_seed, 16) % len(approaches)]
        opening_lens = (
            "The client chose to start a new conversation. Invite them to choose whatever they would like to talk about "
            "today. Leave the topic entirely open. Do not suggest a topic or ask how a previous conversation or plan "
            "went."
            if self.fresh_start else
            "Choose a fresh entry point among clarity, desired outcome, useful focus, what matters most today, or "
            "what would make this time worthwhile. This is the start of the session: ask what they want from it, "
            "not yet about actions or steps."
        )
        system_prompt = f"""You are a thoughtful coach starting a conversation with someone who hasn't spoken yet.
Make contact as a person, with an easy, attentive tone, before trying to establish a goal.

Follow this writing direction for this opening: {approach}
Session boundary: {opening_lens}

Write one or two short sentences, including just ONE open-ended question. Follow the chosen direction in both sentence shape and tone, rather than falling back on your usual opening.
Leave the subject to them. Don't assume their mood, problems, physical surroundings, or shared history. No advice, coaching jargon, service slogans, or exaggerated intimacy.
Respond only in {lang_instr}. {_language_output_rule(self.language)}
In Chinese, speak naturally using 你; avoid formal, translated-sounding language and forced 呢 or 呀 endings.
Output only ONE finished opening addressed to the person, without quotation marks, alternatives, or commentary."""
        if self.current_state != CoachingState.CONTRACT:
            system_prompt += f"\nCurrent focus: {STAGE_DESCRIPTIONS[self.current_state]}"
        follow_up = self.last_card if not self.fresh_start else None
        if follow_up:
            notes = "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in follow_up.items() if value)
            system_prompt += f"""

FOLLOW-UP: in their previous session the client made this plan ({notes}).
Instead of a fresh entry point, warmly ask how it went with that next step. Ask exactly ONE question and nothing else; if they would rather talk about something new, they will say so."""

        # An opening emptied by the language clean-up (written in the other language) would show as a blank bubble: one
        # more try, then the error lets the page say plainly that the AI isn't available.
        for _ in range(2):
            resp = client.chat.completions.create(
                model=_chat_model(),
                messages=[{"role": "system", "content": system_prompt}],
                max_tokens=160 if follow_up else 120,
                temperature=0.7,
            )
            opening = _clean_response_language(_response_text(resp), self.language)
            if opening:
                return _end_at_question(opening)[0] if self.fresh_start else opening
        raise ValueError("Model returned no text content.")

    def _get_llm_response(self, api_key: str, decide_stage: bool = False):
        """Stream the coach reply as (text so far, stage signal) pairs; the last pair is final."""
        try:
            client = _build_client(api_key, on_usage=self.on_usage)
            lang_instr = "respond in English" if self.language == "en" else "respond in Simplified Chinese (简体中文)"
            persona_extension = ""
            if self.fresh_start:
                persona_extension = (
                    "\n\nFollow the topic the client brings to this conversation. If they bring up a past event or plan, "
                    "use only the details shared in this conversation."
                )
            elif self.user_profile:
                p = self.user_profile
                persona_extension = (
                    f"\n\nUSER INSIGHTS (Customize your style based on these):\n"
                    f"- General Style: {p.coaching_style_insights}\n"
                    f"- Known Strengths: {', '.join(p.strengths)}\n"
                    f"- Growth Areas: {', '.join(p.growth_areas)}\n"
                    "Adjust your level of challenge and focus to help the user grow in their 'Growth Areas'."
                )

            skipped = ""
            if self.context and self.context[-1]["role"] == "coach":
                # No new message from the client: they pressed Skip Ahead.
                skipped = ("\nThe client has chosen to skip ahead to this stage. In a few words, link to where you were, "
                           "then ask one opening question for this stage.")
            system_prompt = f"""You are a warm, experienced solution-focused coach in a one-to-one chat. Coaching conversations move through five stages: goal, reality, options, commitment and closing.
Now in stage {self.current_state.value} of 5, {STAGE_FOCUS[self.current_state]}.

How to talk:
1. Sound like a thoughtful person, not a textbook: short everyday sentences, usually one to three in all. Avoid coaching jargon (such as values honoured, inner resources, align, leverage, channel, journey, hold space) and never open with praise (such as great, amazing, powerful, wonderful, 很好, 太棒了).
2. Don't parrot. Usually start straight with your question, or with a short, natural acknowledgement. Echo the client's words only now and then, when one word or feeling really matters, and never open two replies in a row by restating what they said. When the client shows strong feeling, acknowledge it simply and stay with it before moving on. At a turning point, sum up in one sentence.
3. Ask one open question at a time, never two, and never one you have asked already, even in other words: one or two "what else?" questions are enough.
4. Follow their pace: give a thoughtful client room, keep moving with a decisive one, and when they don't know, make it easier: a smaller question, a scale from 1 to 10, or a time when it went a bit better.
5. Don't give advice, suggestions or ideas of your own: the answers come from them.
6. End every reply with your question, except when you say goodbye.
7. If the client mentions harming themselves or being in danger, stop the coaching, respond with care, and encourage them to contact local emergency services or a crisis line (in mainland China: 12356, or 120 / 110 in an emergency).
8. Write only your own reply, never the client's words. Always {lang_instr}. {_language_output_rule(self.language)}

Coach lines with the rhythm to aim for, from other conversations (don't reuse them): {RHYTHM_EXAMPLE[self.language]}{persona_extension}{skipped}"""
            system_prompt += self._stage_decision_rules() if decide_stage else self._end_only_rules()

            messages = [{"role": "system", "content": system_prompt}]
            for msg in self.context:
                role = "user" if msg["role"] == "client" else "assistant"
                messages.append({"role": role, "content": _as_written(msg)})
            # Told not to, the AI coach still opened nearly every reply by restating the client's words, copying its
            # own earlier replies. A note beside the client's latest message, where the model is looking, does better
            # than any rule in the instructions above. The client never sees it.
            last_reply = next((msg["content"] for msg in reversed(self.context[:-1]) if msg["role"] == "coach"), "")
            if messages[-1]["role"] == "user" and _opens_with_comment(last_reply):
                messages[-1] = {"role": "user",
                                "content": messages[-1]["content"] + "\n\n" + STRAIGHT_TO_QUESTION_NOTE[self.language]}

            raw = ""
            for raw in _stream_text(client, model=_chat_model(), messages=messages, max_tokens=250, temperature=0.7):
                visible, cut = _end_at_question(_split_stage_signal(raw)[1])
                if cut:
                    break  # the reply is complete, and what follows isn't the coach's (trimmed below)
                yield visible, None
            signal, text = _split_stage_signal(raw)
            text = _end_at_question(_clean_response_language(text, self.language))[0]
            if not text:
                raise ValueError("Model returned no text content.")
            yield text, signal
        except ContextCapacityError:
            raise
        except Exception as exc:
            raise Exception(f"LLM error: {exc}")

    def action_card(self, api_key: str) -> dict | None:
        """The plan the client arrived at, as {goal, next_step, by_when, support}, or None if there isn't one yet."""
        client = _build_client(api_key, on_usage=self.on_usage)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        transcript = "\n".join(
            f'{"Client" if msg["role"] == "client" else "Coach"}: {msg["content"]}'
            for msg in self.context
        )
        prompt = (
            "Read this finished coaching conversation and write the client's action card. "
            'Return valid JSON only: {"goal": string, "next_step": string, "by_when": string, "support": string}. '
            "goal: what the client wants, in one short sentence. next_step: the concrete action they committed to. "
            "by_when: when they will do it. support: who or what will help them. "
            "Use the client's own words where possible. If something was not discussed, use an empty string; never invent. "
            f"Write every value in {lang_instr}. {_language_output_rule(self.language)} Do not include markdown fences.\n\n"
            f"CONVERSATION:\n{transcript}"
        )
        data = _json_completion(client, messages=[{"role": "system", "content": prompt}], max_tokens=300, temperature=0.2)
        card = {key: str(data.get(key) or "").strip()[:300] for key in ACTION_CARD_FIELDS}
        return card if card["goal"] or card["next_step"] else None

    def analyze_session_for_memory(self, api_key: str) -> dict:
        """Analyze the session history to extract new user insights."""
        try:
            client = _build_client(api_key, on_usage=self.on_usage)
            transcript = []
            for msg in self.context:
                role = "Coach" if msg["role"] == "coach" else "Client"
                transcript.append(f"{role}: {msg['content']}")
            
            lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
            prompt = (
                "You are an AI learning module. Analyze this coaching session where the human played the 'Client'. "
                "Identify their recurring coaching strengths and areas where they need more challenge. "
                "Return ONLY a JSON object with this shape: "
                "{"
                "\"coaching_style\": \"short summary of their mindset/approach\", "
                "\"strengths\": [\"strength1\", \"strength2\"], "
                "\"growth_areas\": [\"area1\", \"area2\"]"
                "}. "
                f"Write every value in {lang_instr}. {_language_output_rule(self.language)}"
            )
            return _json_completion(client, messages=[{"role": "system", "content": prompt},
                                                      {"role": "user", "content": "\n".join(transcript)}],
                                    max_tokens=300, temperature=0.3)
        except Exception:
            return {}
