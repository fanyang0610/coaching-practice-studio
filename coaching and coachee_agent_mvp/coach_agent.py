import json
import random
import uuid

from coaching_core import CoachingState, CoachingSubPhase, STAGE_DESCRIPTIONS, _build_client, _chat_model, _clean_response_language, _conversation_window, _language_output_rule, _response_text, _split_stage_signal, _stream_text, _strip_json_fence, _translate_texts
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

        if decide_stage:
            self._apply_stage_signal(signal)
        self.context.append({"role": "coach", "content": response})

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

    def translate_history(self, new_lang: str, api_key: str | None = None):
        if self.language == new_lang:
            return

        old_lang = self.language
        dict_map = TRANSLATE_EN_TO_ZH if new_lang == "zh" else TRANSLATE_ZH_TO_EN
        llm_messages_to_translate: list[tuple[int, str]] = []

        for idx, msg in enumerate(self.context):
            if msg["role"] != "coach":
                continue

            translated = _translate_template_message(msg["content"], old_lang, dict_map)
            if translated is not None:
                self.context[idx]["content"] = translated
            else:
                llm_messages_to_translate.append((idx, msg["content"]))

        if llm_messages_to_translate and api_key and self.mode == "llm":
            self._batch_translate_llm(llm_messages_to_translate, new_lang, api_key)

        self.language = new_lang

    def _batch_translate_llm(self, items: list[tuple[int, str]], target_lang: str, api_key: str):
        try:
            translated = _translate_texts(api_key, [text for _, text in items], target_lang, on_usage=self.on_usage)
        except Exception as exc:
            print(f"Failed to translate history via LLM: {exc}")
            return
        for (idx, _), text in zip(items, translated):
            self.context[idx]["content"] = text

    def _evaluate_state_transition(self, api_key: str | None = None) -> bool:
        """Advance the stage flow for a new client turn. Returns True when the LLM reply should decide it."""
        if self.current_sub_phase == CoachingSubPhase.OPEN:
            self.current_sub_phase = CoachingSubPhase.DEEPEN
            return False

        if self.current_sub_phase == CoachingSubPhase.DEEPEN:
            if self.turns_in_current_stage <= 2:
                return False

            if self.turns_in_current_stage >= 6:
                self.current_sub_phase = CoachingSubPhase.BRIDGE
                return False

            if self.mode == "llm" and api_key:
                return True
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
        elif signal == "NEXT" or (signal is None and self.turns_in_current_stage >= 4):
            # No marker means the model ignored the format; pace the stage like template mode does.
            self.current_sub_phase = CoachingSubPhase.BRIDGE

    def _stage_decision_rules(self) -> str:
        states = list(CoachingState)
        next_state = states[states.index(self.current_state) + 1]
        return f"""

REQUIRED OUTPUT FORMAT: the very first characters of your output must be one stage marker, then your reply.
[[STAY]] - keep exploring this stage: follow the DEEPEN guidance above.
[[NEXT]] - the client has clearly answered this stage's goal or wants to move on: briefly summarise what they gained here, then ask one opening question for the next stage ({next_state.name}: {STAGE_DESCRIPTIONS[next_state]}).
[[END]] - the client wants to stop, says goodbye or thanks to wrap up, or the conversation has reached a natural conclusion: give a brief, warm closing summary that acknowledges their progress and commitments, with no question.
Example output: [[STAY]] It sounds like mornings are when you feel strongest. What makes them work for you?
Never mention the marker or stage names in the reply itself."""

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
Variation lens: choose a fresh entry point among clarity, desired outcome, useful focus, recent progress, decision tension, inner resource, or first small step."""
        if self.last_card:
            notes = "; ".join(f"{key.replace('_', ' ')}: {value}" for key, value in self.last_card.items() if value)
            system_prompt += f"""

FOLLOW-UP: in their previous session the client made this plan ({notes}).
Instead of the guidelines' fresh entry point, warmly ask how it went with that next step, and leave room to continue with it or to bring something new today. Still ask only ONE question."""

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
Current stage: **{self.current_state.name}** ({stage_desc})
Sub-phase: {self.current_sub_phase.name}

Guidelines:
1. First, briefly acknowledge the client's last response with empathy using their words.
2. Then, ask ONE powerful, open-ended coaching question that deepens their thinking.
3. Keep it concise. Do NOT give advice, suggestions, or multi-step tasks.
4. If in DEEPEN phase, probe for resources, values, or hidden possibilities.
5. If in BRIDGE phase, summarise the current success of this stage and pivot to the next.
6. Always {lang_instr}. {_language_output_rule(self.language)}
7. Never repeat yourself or generic template questions.
8. If the client mentions harming themselves or being in danger, stop the coaching exercise, respond with care, and encourage them to contact local emergency services or a crisis line.{persona_extension}"""
            if decide_stage:
                system_prompt += self._stage_decision_rules()

            messages = [{"role": "system", "content": system_prompt}]
            for msg in _conversation_window(self.context):
                role = "user" if msg["role"] == "client" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

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
        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "system", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
        )
        data = json.loads(_strip_json_fence(_response_text(resp)))
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
            
            prompt = (
                "You are an AI learning module. Analyze this coaching session where the human played the 'Client'. "
                "Identify their recurring coaching strengths and areas where they need more challenge. "
                "Return ONLY a JSON object with this shape: "
                "{"
                "\"coaching_style\": \"short summary of their mindset/approach\", "
                "\"strengths\": [\"strength1\", \"strength2\"], "
                "\"growth_areas\": [\"area1\", \"area2\"]"
                "}"
            )
            
            resp = client.chat.completions.create(
                model=_chat_model(),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "\n".join(transcript)}
                ],
                max_tokens=300,
                temperature=0.3,
            )
            
            # Clean possible markdown
            content = _response_text(resp).strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            
            return json.loads(content)
        except Exception:
            return {}
