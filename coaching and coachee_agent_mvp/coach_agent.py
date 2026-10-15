import json
import logging
import random
import uuid

from coaching_core import CoachingState, CoachingSubPhase, STAGE_DESCRIPTIONS, STAGE_MARKER_GUIDE, _as_written, _build_client, _chat_model, _clean_response_language, _conversation_window, _json_completion, _labelled_stage, _language_output_rule, _marker, _response_text, _split_stage_signal, _stream_text, _translate_texts
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
# After this many client turns in one stage, the AI coach is asked to sum up and move on.
STAGE_NUDGE_TURNS = 5


class EricksonCoachingAgent:
    assistant_role = "coach"
    user_role = "client"

    def __init__(self, mode="template", language="en", user_profile=None):
        self.mode = mode
        self.language = language
        self.current_state = CoachingState.CONTRACT
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.context: list[dict[str, str]] = []
        self.turns_in_current_stage = 0
        self._last_template: str | None = None
        self.user_profile = user_profile
        # Called with (model, prompt_tokens, completion_tokens) after each model call; set by the web app.
        self.on_usage = None
        self.opening_variation_seed = uuid.uuid4().hex[:8]
        # The action card from this person's previous session, set by the web app so the opening can follow up on it.
        self.last_card: dict | None = None

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
        return self.current_state == CoachingState.CLOSING

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
        }

    @classmethod
    def from_dict(cls, data: dict, user_profile=None) -> "EricksonCoachingAgent":
        agent = cls(mode=data["mode"], language=data["language"], user_profile=user_profile)
        agent.current_state = CoachingState[data["state"]]
        agent.current_sub_phase = CoachingSubPhase[data["sub_phase"]]
        agent.context = list(data["context"])
        agent.turns_in_current_stage = data["turns"]
        agent._last_template = data.get("last_template")
        agent.opening_variation_seed = data["seed"]
        return agent

    def get_stage_prompt(self, api_key: str | None = None) -> str:
        prompt = ""
        for prompt, _ in self._stream_stage_prompt(api_key):
            pass
        return prompt

    def _stream_stage_prompt(self, api_key: str | None = None, decide_stage: bool = False):
        """Yield (text so far, stage signal) pairs; the last pair holds the final prompt."""
        if self.current_state == CoachingState.CLOSING:
            # Reached by skipping ahead: close with a real summary when the AI is available.
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

    def force_next_state(self) -> bool:
        states = list(CoachingState)
        idx = states.index(self.current_state)
        if idx < len(states) - 1:
            self.current_state = states[idx + 1]
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0
            return True
        return False

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

        if self.current_state == CoachingState.CLOSING:
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
            response, signal = "", None
            for response, signal in self._stream_stage_prompt(api_key, decide_stage):
                if response:
                    yield response
        except Exception as exc:
            if self.mode == "llm" and "Model returned no text content" in str(exc):
                original_mode = self.mode
                self.mode = "template"
                try:
                    response = self.get_stage_prompt()
                finally:
                    self.mode = original_mode
                self.context.append({"role": "coach", "content": response})
                yield response
                return

            self.current_state = old_state
            self.current_sub_phase = old_sub
            self.turns_in_current_stage = old_turns
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
                    "You are a professional solution-focused coach. "
                    "The coaching session has ended. Based on the conversation history, "
                    "provide a brief, warm, and inspiring closing summary. "
                    "Acknowledge the client's progress and the actions they committed to. "
                    f"Respond ONLY in {lang_instr}. {_language_output_rule(self.language)}"
                ),
            }
        ]
        for msg in _conversation_window(self.context):
            role = "user" if msg["role"] == "client" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return _clean_response_language(_response_text(resp), self.language)

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
                logging.getLogger("erickson_coach").warning("Translating the conversation failed", exc_info=True)
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
        return False

    def _apply_stage_signal(self, signal: str | None):
        if signal == "END":
            self.current_state = CoachingState.CLOSING
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0
            return
        stage = _labelled_stage(signal, self.current_state)
        if signal == "NEXT" or (signal is None and self.current_sub_phase == CoachingSubPhase.BRIDGE):
            # No marker on a reply that was asked to move on: take it that it did, as template mode would.
            stage = CoachingState(min(self.current_state.value + 1, CoachingState.VALUE.value))
        if stage != self.current_state:
            # The reply has already opened the new stage, so the tracker moves now, not after the client's answer.
            self.current_state = stage
            self.current_sub_phase = CoachingSubPhase.DEEPEN
            self.turns_in_current_stage = 0

    def _stage_decision_rules(self) -> str:
        states = list(CoachingState)
        here = _marker(self.current_state)
        if self.current_state == CoachingState.VALUE:
            move_on = "close the session with [[END]]"
        else:
            move_on = f"move on with {_marker(states[states.index(self.current_state) + 1])}: briefly sum up what they gained here, then ask one opening question for that stage"
        nudge = ""
        if self.current_sub_phase == CoachingSubPhase.BRIDGE:
            nudge = f"\nThis stage has already taken {self.turns_in_current_stage} exchanges. Unless the client is in the middle of something important, now {move_on}."
        return f"""

REQUIRED OUTPUT FORMAT: the very first characters of your output must be one marker, then your reply.
The marker names the stage your reply works on:
{STAGE_MARKER_GUIDE}
[[END]] - close the session: a brief, warm summary that acknowledges their progress and commitments, with no question. Use it when the client clearly says they want to finish (goodbye, that's all for today), or once they have a concrete commitment and confirm they have what they need. Before [[COMMITMENT]], use it only if the client asks to finish. A thank-you on its own is not a request to finish.
The conversation has reached {here}. Stay with {here} while this stage still needs work. Once it has done its job, {move_on}. If the client has already moved on to a later stage, follow them and use that stage's marker. Never use the marker of an earlier stage.{nudge}
Example output: [[REALITY]] So the goal is two calm evenings a week. What is happening on your evenings at the moment?
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
        stage_desc = STAGE_DESCRIPTIONS[self.current_state]
        system_prompt = f"""You are a professional solution-focused coach guiding a five-stage coaching conversation (contract, reality, possibilities, commitment, closing).
Current stage: **{self.current_state.name}** ({stage_desc})
Sub-phase: OPEN

Generate the first coaching prompt for this stage.
	Guidelines:
	1. Ask ONE concise, open-ended question.
	2. Do NOT provide advice.
	3. Do NOT mention the stage name.
	4. Use the session variation seed to vary wording, angle, and emotional entry point; avoid repeating common default openings across sessions.
	5. Respond only in {lang_instr}. {_language_output_rule(self.language)}

Session variation seed: {self.opening_variation_seed}
Variation lens: choose a fresh entry point among clarity, desired outcome, useful focus, what matters most today, or what would make this time worthwhile. This is the start of the session: ask what they want from it, not yet about actions or steps."""
        if self.last_card:
            notes = "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in self.last_card.items() if value)
            system_prompt += f"""

FOLLOW-UP: in their previous session the client made this plan ({notes}).
Instead of a fresh entry point, warmly ask how it went with that next step. Ask exactly ONE question and nothing else; if they would rather talk about something new, they will say so."""

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=160 if self.last_card else 120,
            temperature=0.7,
        )
        return _clean_response_language(_response_text(resp), self.language)

    def _get_llm_response(self, api_key: str, decide_stage: bool = False):
        """Stream the coach reply as (text so far, stage signal) pairs; the last pair is final."""
        try:
            client = _build_client(api_key, on_usage=self.on_usage)
            lang_instr = "respond in English" if self.language == "en" else "respond in Simplified Chinese (简体中文)"
            stage_desc = STAGE_DESCRIPTIONS[self.current_state]
            persona_extension = ""
            if self.user_profile:
                p = self.user_profile
                persona_extension = (
                    f"\n\nUSER INSIGHTS (Customize your style based on these):\n"
                    f"- General Style: {p.coaching_style_insights}\n"
                    f"- Known Strengths: {', '.join(p.strengths)}\n"
                    f"- Growth Areas: {', '.join(p.growth_areas)}\n"
                    "Adjust your level of challenge and focus to help the user grow in their 'Growth Areas'."
                )

            system_prompt = f"""You are a professional solution-focused coach guiding a five-stage coaching conversation (contract, reality, possibilities, commitment, closing).
Current stage: {self.current_state.value} of 5 ({stage_desc})
Sub-phase: {self.current_sub_phase.name}

Guidelines:
1. First, briefly reflect the client's last response in their own words, in one short sentence. Vary how you do this, and leave out praise words such as inspiring, powerful, amazing or beautiful.
2. Then, ask ONE powerful, open-ended coaching question that deepens their thinking.
3. Keep it concise, in plain sentences with no lists or bullet points. Do NOT give advice, suggestions, or multi-step tasks.
4. If in DEEPEN phase, probe for resources, values, or hidden possibilities.
5. If in BRIDGE phase, summarise the current success of this stage and pivot to the next.
6. Always {lang_instr}. {_language_output_rule(self.language)}
7. Never repeat a question you have already asked in this conversation, and avoid generic template questions.
8. If the client mentions harming themselves or being in danger, stop the coaching exercise, respond with care, and encourage them to contact local emergency services or a crisis line.
9. End every reply with your one question. Only a closing summary at the very end of the session has no question.{persona_extension}"""
            system_prompt += self._stage_decision_rules() if decide_stage else self._end_only_rules()

            messages = [{"role": "system", "content": system_prompt}]
            for msg in _conversation_window(self.context):
                role = "user" if msg["role"] == "client" else "assistant"
                messages.append({"role": role, "content": _as_written(msg)})

            raw = ""
            for raw in _stream_text(client, model=_chat_model(), messages=messages, max_tokens=250, temperature=0.7):
                yield _split_stage_signal(raw)[1], None
            signal, text = _split_stage_signal(raw)
            text = _clean_response_language(text, self.language)
            if not text:
                raise ValueError("Model returned no text content.")
            yield text, signal
        except Exception as exc:
            raise Exception(f"LLM error: {exc}")

    def action_card(self, api_key: str) -> dict | None:
        """The plan the client arrived at, as {goal, next_step, by_when, support}, or None if there isn't one yet."""
        client = _build_client(api_key, on_usage=self.on_usage)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        transcript = "\n".join(
            f'{"Client" if msg["role"] == "client" else "Coach"}: {msg["content"]}'
            for msg in _conversation_window(self.context, head=8, tail=30)
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
            for msg in self.context[-30:]:
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
