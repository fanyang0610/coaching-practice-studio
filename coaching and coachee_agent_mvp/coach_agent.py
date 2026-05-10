import json
import random
import uuid

from coaching_core import CoachingState, CoachingSubPhase, STAGE_DESCRIPTIONS, _build_client, _chat_model, _clean_response_language, _language_output_rule, _response_text
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
        self.opening_variation_seed = uuid.uuid4().hex[:8]

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

    def get_stage_prompt(self, api_key: str | None = None) -> str:
        if self.current_state == CoachingState.CLOSING:
            return random.choice(CLOSING_MESSAGES[self.language])

        if self.mode == "template":
            return self._get_template_response()

        if not api_key:
            raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")

        if not self.context and self.current_sub_phase == CoachingSubPhase.OPEN:
            return self._get_llm_opening_response(api_key)

        return self._get_llm_response(api_key)

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
        if self.mode == "llm" and not api_key:
            raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")

        old_state = self.current_state
        old_sub = self.current_sub_phase
        old_turns = self.turns_in_current_stage
        old_context_len = len(self.context)

        if user_input and user_input.strip():
            self.context.append({"role": "client", "content": user_input.strip()})
            self.turns_in_current_stage += 1
            self._evaluate_state_transition(api_key)

        if self.current_state == CoachingState.CLOSING:
            if self.mode == "llm" and api_key:
                try:
                    response = self._get_llm_closing_summary(api_key)
                except Exception:
                    response = random.choice(CLOSING_MESSAGES[self.language])
            else:
                response = random.choice(CLOSING_MESSAGES[self.language])
            self.context.append({"role": "coach", "content": response})
            return response

        try:
            response = self.get_stage_prompt(api_key)
        except Exception as exc:
            if self.mode == "llm" and "Model returned no text content" in str(exc):
                original_mode = self.mode
                self.mode = "template"
                try:
                    response = self.get_stage_prompt()
                finally:
                    self.mode = original_mode
                self.context.append({"role": "coach", "content": response})
                return response

            self.current_state = old_state
            self.current_sub_phase = old_sub
            self.turns_in_current_stage = old_turns
            self.context = self.context[:old_context_len]
            raise exc

        self.context.append({"role": "coach", "content": response})
        return response

    def _get_llm_closing_summary(self, api_key: str) -> str:
        client = _build_client(api_key)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional Erickson Solution-Focused Coach. "
                    "The coaching session has ended. Based on the conversation history, "
                    "provide a brief, warm, and inspiring closing summary. "
                    "Acknowledge the client's progress and the actions they committed to. "
                    f"Respond ONLY in {lang_instr}. {_language_output_rule(self.language)}"
                ),
            }
        ]
        for msg in self.context[-15:]:
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
            client = _build_client(api_key)
            target = "Simplified Chinese" if target_lang == "zh" else "English"

            for idx, text in items:
                resp = client.chat.completions.create(
                    model=_chat_model(),
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"Translate the following text accurately to {target}. "
                                f"{_language_output_rule(target_lang)} Output only the translation."
                            ),
                        },
                        {"role": "user", "content": text},
                    ],
                    max_tokens=250,
                    temperature=0.1,
                )
                self.context[idx]["content"] = _clean_response_language(_response_text(resp), target_lang)
        except Exception as exc:
            print(f"Failed to translate history via LLM: {exc}")

    def _evaluate_state_transition(self, api_key: str | None = None):
        if self.current_sub_phase == CoachingSubPhase.OPEN:
            self.current_sub_phase = CoachingSubPhase.DEEPEN
            return

        if self.current_sub_phase == CoachingSubPhase.DEEPEN:
            if self.turns_in_current_stage <= 2:
                return

            if self.turns_in_current_stage >= 6:
                self.current_sub_phase = CoachingSubPhase.BRIDGE
                return

            if self.mode == "llm" and api_key:
                signal = self._llm_check_transition(api_key)
                if signal == "END":
                    self.current_state = CoachingState.CLOSING
                    self.current_sub_phase = CoachingSubPhase.OPEN
                    self.turns_in_current_stage = 0
                    return
                elif signal == "NEXT":
                    self.current_sub_phase = CoachingSubPhase.BRIDGE
                    return
                return # Stay in DEEPEN if signal is NO/None
            elif self.turns_in_current_stage >= 4:
                self.current_sub_phase = CoachingSubPhase.BRIDGE
            return

        states = list(CoachingState)
        idx = states.index(self.current_state)
        if idx < len(states) - 1:
            self.current_state = states[idx + 1]
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0

    def _llm_check_transition(self, api_key: str) -> str:
        """Determines if we should move to NEXT stage, END the session, or stay (NO)."""
        try:
            client = _build_client(api_key)
            stage_desc = STAGE_DESCRIPTIONS[self.current_state]
            system_prompt = f"""You are evaluating the flow of a coaching session.
Current stage: **{self.current_state.name}** ({stage_desc})

Your task is to determine the next logical step for the conversation.
Signals to END the session:
- The client explicitly says they want to stop, wrap up, or that they have enough.
- The client says 'Goodbye', 'Thank you', 'That's all', etc.
- The conversation has reached a natural conclusion.

Signals to move to the NEXT stage:
- The client has answered the primary goal of the current stage clearly.
- The client explicitly expresses readiness to move forward.

Otherwise, we should stay in the current stage to explore deeper.

Reply with exactly one of these tokens:
END - if the session should conclude immediately.
NEXT - if we are ready for the next coaching stage.
NO - if we should continue exploring the current stage."""

            messages = [{"role": "system", "content": system_prompt}]
            for msg in self.context[-8:]:
                role = "user" if msg["role"] == "client" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

            resp = client.chat.completions.create(
                model=_chat_model(),
                messages=messages,
                max_tokens=10,
                temperature=0.1,
            )
            content = _response_text(resp).upper()
            if "END" in content: return "END"
            if "NEXT" in content: return "NEXT"
            return "NO"
        except Exception:
            return "NO"

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
        client = _build_client(api_key)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        stage_desc = STAGE_DESCRIPTIONS[self.current_state]
        system_prompt = f"""You are a professional Erickson Solution-Focused Coach following the Arrow Model.
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

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=120,
            temperature=0.7,
        )
        return _clean_response_language(_response_text(resp), self.language)

    def _get_llm_response(self, api_key: str) -> str:
        try:
            client = _build_client(api_key)
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

            system_prompt = f"""You are a professional Erickson Solution-Focused Coach following the Arrow Model.
Current stage: **{self.current_state.name}** ({stage_desc})
Sub-phase: {self.current_sub_phase.name}

Guidelines:
1. First, briefly acknowledge the client's last response with empathy using their words.
2. Then, ask ONE powerful, open-ended coaching question that deepens their thinking.
3. Keep it concise. Do NOT give advice, suggestions, or multi-step tasks.
4. If in DEEPEN phase, probe for resources, values, or hidden possibilities.
5. If in BRIDGE phase, summarise the current success of this stage and pivot to the next.
6. Always {lang_instr}. {_language_output_rule(self.language)}
7. Never repeat yourself or generic template questions.{persona_extension}"""

            messages = [{"role": "system", "content": system_prompt}]
            for msg in self.context[-10:]:
                role = "user" if msg["role"] == "client" else "assistant"
                messages.append({"role": role, "content": msg["content"]})

            resp = client.chat.completions.create(
                model=_chat_model(),
                messages=messages,
                max_tokens=250,
                temperature=0.7,
            )
            return _clean_response_language(_response_text(resp), self.language)
        except Exception as exc:
            raise Exception(f"LLM error: {exc}")

    def analyze_session_for_memory(self, api_key: str) -> dict:
        """Analyze the session history to extract new user insights."""
        try:
            client = _build_client(api_key)
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
