import json
import random
import uuid
from coaching_core import CoachingState, CoachingSubPhase, STAGE_DESCRIPTIONS, _build_client, _chat_model, _clean_response_language, _language_output_rule, _response_text, _split_stage_signal, _stream_text, _translate_texts
from coachee_data import (
    COACHEE_ACKNOWLEDGMENTS,
    COACHEE_BRIDGES,
    COACHEE_STAGE_HINTS,
    COACHEE_STAGE_ORDER,
    CoachingMetrics,
    SCENARIOS,
    _choice,
    _scenario_bundle_from_single_language,
    _strip_json_fence,
)


class EricksonCoacheeAgent:
    assistant_role = "coachee"
    user_role = "coach"

    def __init__(self, mode: str = "template", language: str = "en", user_profile=None):
        self.mode = mode
        self.language = language
        self.current_state = CoachingState.CONTRACT
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.context: list[dict[str, str]] = []
        self.turns_in_current_stage = 0
        self.session_complete = False
        self.metrics = CoachingMetrics()
        self.scenario = random.choice(SCENARIOS)
        self._llm_scenario_ready = False
        self._stage_fact_cursor = {state: set() for state in CoachingState}
        self.user_profile = user_profile
        self.scenario_variation_seed = uuid.uuid4().hex[:8]

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

    def translate_history(self, new_lang: str, api_key: str | None = None):
        if self.language == new_lang:
            return

        if api_key and self.mode == "llm":
            self._translate_assistant_history(new_lang, api_key)

        self.language = new_lang

    def get_stage_prompt(self, api_key: str | None = None) -> str:
        prompt = ""
        for prompt, _ in self._stream_stage_prompt(api_key):
            pass
        return prompt

    def _stream_stage_prompt(self, api_key: str | None = None, decide_stage: bool = False):
        """Yield (text so far, stage signal) pairs; the last pair holds the final prompt."""
        if self.current_state == CoachingState.CLOSING:
            yield self._build_final_review(api_key), None
            return

        if self.mode == "llm":
            if not api_key:
                raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")
            self._ensure_llm_scenario(api_key)

        if not self.context:
            yield self.scenario.intro[self.language], None
            return

        if self.mode == "template":
            yield self._get_template_response(), None
            return

        yield from self._get_llm_response(api_key, decide_stage)

    def manual_advance_guard(self) -> str | None:
        if self.current_state == CoachingState.CLOSING:
            return None

        if self.metrics.stage_questions[self.current_state] > 0:
            return None

        if self.language == "zh":
            return "请先以教练身份在当前阶段提出至少一个问题，再手动推进到下一阶段。"
        return "Ask at least one coaching question in the current stage before manually advancing."

    def force_next_state(self) -> bool:
        if self.current_state == CoachingState.CLOSING:
            return False

        if self.current_sub_phase != CoachingSubPhase.BRIDGE:
            self.current_sub_phase = CoachingSubPhase.BRIDGE
            return True

        states = list(CoachingState)
        idx = states.index(self.current_state)
        self.current_state = states[idx + 1]
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.turns_in_current_stage = 0
        if self.current_state == CoachingState.CLOSING:
            self.session_complete = True
        return True

    def generate_response(self, user_input: str, api_key: str | None = None) -> str:
        response = ""
        for response in self.stream_response(user_input, api_key):
            pass
        return response

    def stream_response(self, user_input: str, api_key: str | None = None):
        """Yield the coachee reply as it streams in; the last value is the final reply."""
        if self.mode == "llm" and not api_key:
            raise ValueError("Please provide an API Key in the settings panel to use LLM mode.")

        if self.session_complete:
            raise ValueError("Session complete. Start a new session to continue.")

        decide_stage = False
        if user_input and user_input.strip():
            coach_message = user_input.strip()
            self.context.append({"role": self.user_role, "content": coach_message})
            self.turns_in_current_stage += 1
            self._track_coach_input(coach_message)
            decide_stage = self._evaluate_state_transition(api_key)

        try:
            response, signal = "", None
            for response, signal in self._stream_stage_prompt(api_key, decide_stage):
                if signal == "END":
                    break
                if response:
                    yield response
        except Exception as exc:
            if not (self.mode == "llm" and "Model returned no text content" in str(exc)):
                raise
            original_mode = self.mode
            self.mode = "template"
            try:
                response = self.get_stage_prompt()
            finally:
                self.mode = original_mode
            signal = None
            yield response

        if decide_stage:
            self._apply_stage_signal(signal)
            if self.current_state == CoachingState.CLOSING:
                response = self._build_final_review(api_key)
                yield response

        self.context.append({"role": self.assistant_role, "content": response})

        if self.current_state == CoachingState.CLOSING:
            self.session_complete = True

    def _translate_assistant_history(self, new_lang: str, api_key: str):
        indexes = [idx for idx, msg in enumerate(self.context) if msg["role"] == self.assistant_role]
        if not indexes:
            return
        try:
            translated = _translate_texts(api_key, [self.context[idx]["content"] for idx in indexes], new_lang)
        except Exception:
            return
        for idx, text in zip(indexes, translated):
            self.context[idx]["content"] = text

    def _ensure_llm_scenario(self, api_key: str):
        if self._llm_scenario_ready:
            return

        client = _build_client(api_key)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        
        persona_extension = ""
        if self.user_profile:
            p = self.user_profile
            persona_extension = (
                f"\nTAILORING REQUEST:\n"
                f"- User's Coaching Strengths: {', '.join(p.strengths)}\n"
                f"- User's Growth Areas: {', '.join(p.growth_areas)}\n"
                "Create a scenario that specifically challenges the user in their 'Growth Areas' while acknowledging their strengths."
            )

        prompt = (
            "Create one realistic Erickson coach-training coachee case. "
            "Return valid JSON only with this shape: "
            "{"
            "\"intro\": string, "
            "\"contract\": {\"goal\": [string, string], \"importance\": [string, string], \"success\": [string, string]}, "
            "\"experience\": {\"reality\": [string, string], \"obstacle\": [string, string], \"strength\": [string, string], \"past_success\": [string, string], \"scale\": [string, string]}, "
            "\"action\": {\"possibility\": [string, string], \"stretch\": [string, string], \"support\": [string, string]}, "
            "\"value\": {\"commitment\": [string, string], \"timeline\": [string, string], \"risk\": [string, string], \"accountability\": [string, string]}, "
            "\"closing\": {\"reflection\": [string, string]}"
            "}. "
            "CRITICAL: The 'intro' string MUST be the very first sentence spoken by the AI playing the COACHEE (e.g., sharing a problem or seeking help). "
            "It must NOT be a greeting from a coach. The AI is the CLIENT/COACHEE. "
            "Generate a diverse range of realistic adult professional or personal development topics. "
            "Use the session variation seed to vary the domain, stakes, emotional tone, and relationship context. "
            "Do not default to generic career or management dilemmas; include varied themes such as confidence, boundaries, transition, collaboration, family pressure, learning, health habits, creativity, identity, or decision fatigue when appropriate. "
            "The case should be emotionally coherent, coaching-friendly, and suitable for a 10-15 turn practice session. "
            f"{persona_extension}\n"
            f"Session variation seed: {self.scenario_variation_seed}\n"
            f"Write every string in {lang_instr}. {_language_output_rule(self.language)} Do not include markdown fences."
        )

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=[{"role": "system", "content": prompt}],
            max_tokens=900,
            temperature=0.9,
        )
        payload = json.loads(_strip_json_fence(_response_text(resp)))
        self.scenario = _scenario_bundle_from_single_language(payload)
        self._llm_scenario_ready = True

    def _track_coach_input(self, coach_message: str):
        lowered = coach_message.lower()
        self.metrics.total_questions += 1
        self.metrics.stage_questions[self.current_state] += 1

        if self._looks_like_open_question(coach_message):
            self.metrics.open_questions += 1
        if self._looks_reflective(lowered):
            self.metrics.reflective_turns += 1
        if self._has_action_orientation(lowered):
            self.metrics.action_questions += 1
        if self._has_commitment_orientation(lowered):
            self.metrics.commitment_questions += 1

        signal_map = self._coach_signal_map()
        for signal, matcher in signal_map.items():
            if matcher(lowered):
                self.metrics.coach_signals[self.current_state].add(signal)

    def _coach_signal_map(self):
        return {
            "goal": lambda text: any(token in text for token in ("goal", "outcome", "want", "achieve", "focus", "目标", "成果", "想要", "达到", "聚焦")),
            "importance": lambda text: any(token in text for token in ("why", "important", "matter", "意义", "重要", "为什么")),
            "success": lambda text: any(token in text for token in ("success", "sign", "measure", "know", "成功", "迹象", "衡量", "知道")),
            "reality": lambda text: any(token in text for token in ("right now", "current", "now", "现状", "现在", "眼下", "发生")),
            "resource": lambda text: any(token in text for token in ("strength", "resource", "support", "working", "优势", "资源", "支持", "有效")),
            "obstacle": lambda text: any(token in text for token in ("block", "stuck", "hard", "obstacle", "challenge", "卡", "阻碍", "困难", "挑战")),
            "options": lambda text: any(token in text for token in ("option", "possibility", "could", "different", "选择", "可能", "可以", "办法")),
            "commitment": lambda text: any(token in text for token in ("commit", "when", "next step", "first step", "timeline", "承诺", "什么时候", "下一步", "时间")),
            "closing": lambda text: any(token in text for token in ("takeaway", "summary", "wrap", "learn", "收获", "总结", "回顾", "带走")),
        }

    def _looks_like_open_question(self, text: str) -> bool:
        return "?" in text or "？" in text or any(
            token in text.lower()
            for token in ("what", "how", "when", "where", "which", "tell me", "如果", "什么", "如何", "哪些", "哪里", "请你说说")
        )

    def _looks_reflective(self, lowered: str) -> bool:
        return any(token in lowered for token in ("i hear", "it sounds", "you feel", "我听到", "听起来", "你感到", "你刚才提到"))

    def _has_action_orientation(self, lowered: str) -> bool:
        return any(token in lowered for token in ("next", "step", "option", "experiment", "行动", "下一步", "尝试", "方案"))

    def _has_commitment_orientation(self, lowered: str) -> bool:
        return any(token in lowered for token in ("when", "commit", "accountable", "timeline", "什么时候", "承诺", "负责", "时间点"))

    def _evaluate_state_transition(self, api_key: str | None = None) -> bool:
        """Advance the stage flow for a new coach turn. Returns True when the LLM reply should decide it."""
        if self.current_state == CoachingState.CLOSING:
            return False

        if self.current_sub_phase in (CoachingSubPhase.OPEN, CoachingSubPhase.DEEPEN):
            if self.mode == "llm" and api_key:
                return True

            if self.current_sub_phase == CoachingSubPhase.OPEN:
                self.current_sub_phase = CoachingSubPhase.DEEPEN
                return False

            if self._template_stage_ready():
                self.current_sub_phase = CoachingSubPhase.BRIDGE
            return False

        # BRIDGE -> Switch State
        states = list(CoachingState)
        idx = states.index(self.current_state)
        
        # Move to next stage, or end if last
        if idx >= len(states) - 2: # VALUE is index 3, CLOSING is index 4
            self.current_state = CoachingState.CLOSING
            self.session_complete = True
        else:
            self.current_state = states[idx + 1]
            
        self.current_sub_phase = CoachingSubPhase.OPEN
        self.turns_in_current_stage = 0

    def _template_stage_ready(self) -> bool:
        facts = self.metrics.facts_shared[self.current_state]
        questions = self.metrics.stage_questions[self.current_state]
        signals = self.metrics.coach_signals[self.current_state]

        thresholds = {
            CoachingState.CONTRACT: (2, 2, {"goal", "importance", "success"}),
            CoachingState.EXPERIENCE: (2, 3, {"reality", "resource", "obstacle"}),
            CoachingState.ACTION: (2, 2, {"options"}),
            CoachingState.VALUE: (2, 3, {"commitment"}),
        }
        min_questions, min_facts, required_signals = thresholds[self.current_state]
        signal_hit = bool(required_signals & signals) or questions >= min_questions + 1
        return questions >= min_questions and len(facts) >= min_facts and signal_hit

    def _stage_payload(self) -> dict[str, list[str]]:
        stage_map = {
            CoachingState.CONTRACT: self.scenario.contract,
            CoachingState.EXPERIENCE: self.scenario.experience,
            CoachingState.ACTION: self.scenario.action,
            CoachingState.VALUE: self.scenario.value,
            CoachingState.CLOSING: self.scenario.closing,
        }
        payload = stage_map[self.current_state]
        return {key: values[self.language] for key, values in payload.items()}

    def _pick_stage_fact(self, preferred_key: str | None = None) -> tuple[str, str]:
        payload = self._stage_payload()
        shared = self.metrics.facts_shared[self.current_state]
        candidates = list(payload.keys())

        if preferred_key in payload and preferred_key not in shared:
            candidates = [preferred_key] + [key for key in candidates if key != preferred_key]
        else:
            unshared = [key for key in candidates if key not in shared]
            if unshared:
                candidates = unshared + [key for key in candidates if key in shared]

        key = candidates[0]
        line = _choice(payload[key], self._stage_fact_cursor[self.current_state])
        shared.add(key)
        return key, line

    def _match_preferred_fact(self) -> str | None:
        signals = self.metrics.coach_signals[self.current_state]

        mappings = {
            CoachingState.CONTRACT: ["goal", "importance", "success"],
            CoachingState.EXPERIENCE: ["reality", "obstacle", "resource"],
            CoachingState.ACTION: ["options", "stretch", "support"],
            CoachingState.VALUE: ["commitment", "timeline", "risk", "accountability"],
        }

        if self.current_state not in mappings:
            return None

        aliases = {
            "resource": "strength",
            "options": "possibility",
            "commitment": "commitment",
        }

        for signal in mappings[self.current_state]:
            if signal in signals:
                return aliases.get(signal, signal)
        return None

    def _get_template_response(self) -> str:
        if self.current_sub_phase == CoachingSubPhase.BRIDGE:
            return COACHEE_BRIDGES[self.language][self.current_state]

        preferred_key = self._match_preferred_fact()
        _, detail = self._pick_stage_fact(preferred_key)
        ack = random.choice(COACHEE_ACKNOWLEDGMENTS[self.language])
        return f"{ack} {detail}"

    def _apply_stage_signal(self, signal: str | None):
        if signal == "END":
            self.current_state = CoachingState.CLOSING
            self.session_complete = True
            self.current_sub_phase = CoachingSubPhase.OPEN
            self.turns_in_current_stage = 0
        elif signal == "NEXT" or (signal is None and self._template_stage_ready() and self.turns_in_current_stage >= 4):
            # No marker means the model ignored the format; only advance if the template logic is confident.
            self.current_sub_phase = CoachingSubPhase.BRIDGE
        elif self.current_sub_phase == CoachingSubPhase.OPEN:
            self.current_sub_phase = CoachingSubPhase.DEEPEN

    def _stage_decision_rules(self) -> str:
        return (
            "\n\nREQUIRED OUTPUT FORMAT: the very first characters of your output must be one stage marker, then your coachee reply.\n"
            "[[STAY]] - this stage still needs exploring.\n"
            "[[NEXT]] - the coach has covered this stage, but more coaching is still needed.\n"
            "[[END]] - the session is over: the coach says goodbye, good luck or that's all (ZH: 下次见, 谢谢, 结束了, 由衷感谢), "
            "you have a clear plan and nothing left to explore, either side wants to stop, or the conversation has gone in circles "
            "for more than 4 turns with no new insight.\n"
            "Example output: [[STAY]] Honestly, I keep putting it off because I'm afraid it won't be good enough.\n"
            "Never mention the marker in your reply."
        )

    def _get_llm_response(self, api_key: str, decide_stage: bool = False):
        """Stream the coachee reply as (text so far, stage signal) pairs; the last pair is final.

        When the reply decides the stage and opens with [[END]], stop early: the session closes with a review instead.
        """
        try:
            client = _build_client(api_key)
            self._ensure_llm_scenario(api_key)
            stage_payload = self._stage_payload()
            guide_lines = []
            for key, values in stage_payload.items():
                guide_lines.append(f"- {key}: {' | '.join(values)}")

            lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are role-playing a coachee in an Erickson coach-training simulation. "
                        "The human user is the coach. Stay in first person as the coachee. "
                        f"Current stage: {self.current_state.name} ({STAGE_DESCRIPTIONS[self.current_state]}). "
                        f"Stage intent: {COACHEE_STAGE_HINTS[self.language][self.current_state]}. "
                        f"Respond only in {lang_instr}. {_language_output_rule(self.language)} "
                        "Do not coach the user. Do not ask multiple questions back. "
                        "Offer 2-4 concise sentences that answer the coach's latest prompt, reveal only stage-relevant information, "
                        "and show a realistic emotional response. Use the scenario notes below as your hidden ground truth:\n"
                        + "\n".join(guide_lines)
                        + (self._stage_decision_rules() if decide_stage else "")
                    ),
                }
            ]
            for msg in self.context[-10:]:
                role = "assistant" if msg["role"] == self.assistant_role else "user"
                messages.append({"role": role, "content": msg["content"]})
            raw = ""
            for raw in _stream_text(client, model=_chat_model(), messages=messages, max_tokens=220, temperature=0.7):
                signal, visible = _split_stage_signal(raw)
                if decide_stage and signal == "END":
                    yield "", "END"
                    return
                yield visible, None
            signal, text = _split_stage_signal(raw)
            text = _clean_response_language(text, self.language)
            if not text:
                raise ValueError("Model returned no text content.")
            yield text, signal if decide_stage else None
        except Exception as exc:
            raise Exception(f"LLM error: {exc}")

    def _build_final_review(self, api_key: str | None = None) -> str:
        # Use LLM for review if available, otherwise fallback to template
        if self.mode == "llm" and api_key:
            try:
                return self._build_llm_final_review(api_key)
            except Exception:
                return self._build_template_final_review()
        
        # In template mode, if evidence is low, use the specific insufficient template
        if self._has_insufficient_evidence():
            return self._build_incomplete_review()
        return self._build_template_final_review()

    def _build_llm_final_review(self, api_key: str) -> str:
        client = _build_client(api_key)
        lang_instr = "English" if self.language == "en" else "Simplified Chinese (简体中文)"
        transcript = []
        for msg in self.context:
            speaker = "Coach" if msg["role"] == self.user_role else "Coachee"
            transcript.append(f"{speaker}: {msg['content']}")

        # Richer Erickson assessment prompt
        if self.language == "zh":
            struct = (
                "请严格按照以下格式输出：\n"
                "会话结果：[用一两句话总结本次模拟教练的效果和完整度]\n"
                "最后得分：[0-100]/100\n"
                "做得好的部分：\n- [具体的优点1]\n- [具体的优点2]\n"
                "需要提升的部分：\n- [针对埃里克森教练体系的具体建议1]\n- [针对埃里克森教练体系的具体建议2]\n"
                "下一步教练修炼方向：[针对教练个人成长的一句核心建议]"
            )
        else:
            struct = (
                "Use this structure exactly:\n"
                "Session Result: <summary of the coaching quality>\n"
                "Score: <0-100>/100\n"
                "What worked:\n- ...\n- ...\n"
                "What to improve:\n- ...\n- ...\n"
                "Next coaching edge: <one actionable growth tip>"
            )

        prompt = (
            "You are an expert Erickson Professional Coach Assessor. "
            "The human 'Coach' is training with an AI 'Coachee'. "
            "Analyze the provided transcript based on the Erickson solution-focused coaching methodology (The 5 Stages: Contract, Experience, Action, Value, Closing). "
            "Evaluate competencies like: Establishing the Contract, Creating Presence, Powerful Questioning, Active Listening, and Designing Actions. "
            "If the session was very short or skipped phases, provide a realistic (low) score and constructive feedback on why it was incomplete. "
            f"Respond only in {lang_instr}. {_language_output_rule(self.language)}\n"
            f"{struct}\n\n"
            "COACHING HISTORY TO EVALUATE:\n"
            + "\n".join(transcript[-25:])
        )

        resp = client.chat.completions.create(
            model=_chat_model(),
            messages=[
                {"role": "system", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return _clean_response_language(_response_text(resp), self.language)

    def _has_insufficient_evidence(self) -> bool:
        total_facts = sum(len(self.metrics.facts_shared[state]) for state in COACHEE_STAGE_ORDER)
        missing_stages = [state for state in COACHEE_STAGE_ORDER if self.metrics.stage_questions[state] == 0]
        return (
            self.metrics.total_questions < 6
            or total_facts < 6
            or bool(missing_stages)
        )

    def _build_incomplete_review(self) -> str:
        raw_score = min(28, self.metrics.total_questions * 3 + sum(len(self.metrics.facts_shared[state]) for state in COACHEE_STAGE_ORDER))
        if self.language == "zh":
            return (
                "会话结果：当前证据不足，不能判定这次陪练已经完成了一次有效的 Erickson 教练过程。\n"
                f"最后得分：{raw_score}/100\n"
                "做得好的部分：\n"
                "- 你已经开始尝试进入教练对话，但过程还没有形成完整阶段闭环。\n"
                "- 目前留下的有效教练证据有限，因此不适合给出过高评价。\n"
                "需要提升的部分：\n"
                "- 不要直接跳阶段；至少在目标合同、现实探索、可能性和行动承诺四个阶段各提出一轮真实问题。\n"
                "- 在收尾前，要让学员自己说出目标、资源、选项和承诺，而不是靠系统自动推进。\n"
                "下一步教练修炼方向：先把每个阶段问完整，再谈评分，这样反馈才会对教练能力提升有作用。"
            )

        return (
            "Session Result: There is not enough evidence to judge this as a complete Erickson coaching practice.\n"
            f"Score: {raw_score}/100\n"
            "What worked:\n"
            "- You started the coaching interaction, but the session did not complete a full stage-by-stage coaching arc.\n"
            "- The available coaching evidence is too limited to justify a high score.\n"
            "What to improve:\n"
            "- Do not skip stages; ask at least one real coaching question in contract, exploration, possibilities, and commitment.\n"
            "- Before closing, let the coachee articulate the goal, resources, options, and commitment instead of relying on automatic progression.\n"
            "Next coaching edge: Complete each stage with real coaching evidence before expecting the score and feedback to be meaningful."
        )

    def _build_template_final_review(self) -> str:
        scores = self._score_breakdown()
        overall = sum(scores.values())
        verdict = self._final_verdict(overall)
        strengths = self._strengths()
        improvements = self._improvements()
        closing_line = self._coaching_edge(overall)

        if self.language == "zh":
            return (
                f"会话结果：{verdict}\n"
                f"最后得分：{overall}/100\n"
                "做得好的部分：\n"
                f"- {strengths[0]}\n"
                f"- {strengths[1]}\n"
                "需要提升的部分：\n"
                f"- {improvements[0]}\n"
                f"- {improvements[1]}\n"
                f"下一步教练修炼方向：{closing_line}"
            )

        return (
            f"Session Result: {verdict}\n"
            f"Score: {overall}/100\n"
            "What worked:\n"
            f"- {strengths[0]}\n"
            f"- {strengths[1]}\n"
            "What to improve:\n"
            f"- {improvements[0]}\n"
            f"- {improvements[1]}\n"
            f"Next coaching edge: {closing_line}"
        )

    def _score_breakdown(self) -> dict[str, int]:
        stage_facts = self.metrics.facts_shared
        stage_questions = self.metrics.stage_questions

        contract = min(20, len(stage_facts[CoachingState.CONTRACT]) * 6 + min(stage_questions[CoachingState.CONTRACT], 3) * 2)
        experience = min(20, len(stage_facts[CoachingState.EXPERIENCE]) * 4 + min(stage_questions[CoachingState.EXPERIENCE], 4) * 2)
        action = min(20, len(stage_facts[CoachingState.ACTION]) * 6 + min(self.metrics.action_questions, 4) * 2)
        value = min(20, len(stage_facts[CoachingState.VALUE]) * 5 + min(self.metrics.commitment_questions, 4) * 2)
        presence = min(20, self.metrics.open_questions * 3 + self.metrics.reflective_turns * 4 + (4 if self.metrics.stage_questions[CoachingState.VALUE] > 0 else 0))
        return {
            "contract": contract,
            "experience": experience,
            "action": action,
            "value": value,
            "presence": presence,
        }

    def _final_verdict(self, overall: int) -> str:
        if self.language == "zh":
            if overall >= 85:
                return "这次教练过程达到了一个扎实的结束标准，来访目标、探索和承诺都有较好的闭环。"
            if overall >= 70:
                return "这次教练过程基本完成，已经形成清晰推进，但结束力度和深度还可以更强。"
            return "这次教练过程完成了部分关键步骤，但在目标澄清、可能性拓展或承诺收束上仍有明显空间。"

        if overall >= 85:
            return "This coaching process reached a strong closing standard with clear contract, exploration, and commitment."
        if overall >= 70:
            return "This coaching process was broadly complete, with solid movement and room for a stronger ending."
        return "This coaching process covered some key steps, but the contract, possibility work, or commitment close needs more depth."

    def _strengths(self) -> list[str]:
        if self.language == "zh":
            strengths = []
            if self.metrics.open_questions >= 3:
                strengths.append("你持续使用开放式问题，给了学员足够的思考空间。")
            if len(self.metrics.facts_shared[CoachingState.EXPERIENCE]) >= 3:
                strengths.append("你没有停留在表层问题，而是把现状、阻碍和资源都带了出来。")
            if len(self.metrics.facts_shared[CoachingState.VALUE]) >= 3:
                strengths.append("你把对话落到了明确行动、时间点和 accountability，而不是停在抽象想法。")
            if not strengths:
                strengths.append("你已经在尝试以提问而不是建议的方式推进对话。")
            if len(strengths) == 1:
                strengths.append("你让学员逐步从问题感转向了更具体的解决方向。")
            return strengths[:2]

        strengths = []
        if self.metrics.open_questions >= 3:
            strengths.append("You used open questions consistently and gave the coachee room to think.")
        if len(self.metrics.facts_shared[CoachingState.EXPERIENCE]) >= 3:
            strengths.append("You explored beyond the surface and brought out reality, obstacles, and resources.")
        if len(self.metrics.facts_shared[CoachingState.VALUE]) >= 3:
            strengths.append("You landed the conversation on action, timing, and accountability rather than staying abstract.")
        if not strengths:
            strengths.append("You were already trying to lead with questions instead of advice.")
        if len(strengths) == 1:
            strengths.append("You helped the coachee move from problem-talk toward a more actionable direction.")
        return strengths[:2]

    def _improvements(self) -> list[str]:
        if self.language == "zh":
            items = []
            if len(self.metrics.facts_shared[CoachingState.CONTRACT]) < 3:
                items.append("在前段可以更快把本次会谈目标、意义和成功标准问得更具体。")
            if len(self.metrics.facts_shared[CoachingState.ACTION]) < 2:
                items.append("在进入承诺前，可以多停留一会儿，帮助学员打开更多可能性，而不是过早收束。")
            if len(self.metrics.facts_shared[CoachingState.VALUE]) < 3:
                items.append("结束前还可以更明确地确认第一步、时间点和潜在阻碍的应对方式。")
            if not items:
                items.append("可以加入更多带有镜像和提炼的回应，让学员更明显地感受到被看见。")
            if len(items) == 1:
                items.append("收尾时可以再多做一步回顾，帮助学员说出本次最有价值的洞察。")
            return items[:2]

        items = []
        if len(self.metrics.facts_shared[CoachingState.CONTRACT]) < 3:
            items.append("Early in the session, sharpen the contract faster by clarifying the goal, importance, and success criteria.")
        if len(self.metrics.facts_shared[CoachingState.ACTION]) < 2:
            items.append("Before moving into commitment, spend longer opening up possibilities instead of narrowing too quickly.")
        if len(self.metrics.facts_shared[CoachingState.VALUE]) < 3:
            items.append("Close with a clearer first step, timeline, and plan for likely obstacles.")
        if not items:
            items.append("Add more reflective responses so the coachee feels more explicitly heard before the next question.")
        if len(items) == 1:
            items.append("Use the ending to draw out the coachee's own summary of what mattered most.")
        return items[:2]

    def _coaching_edge(self, overall: int) -> str:
        if self.language == "zh":
            if overall >= 85:
                return "下一步可以练习把你的镜像回应再做得更精准，让提问的力量更稳定。"
            if overall >= 70:
                return "下一步重点是让每个阶段都更完整，尤其是在可能性拓展和收尾回顾上。"
            return "下一步先聚焦于目标合同和行动承诺两个关键节点，把问题问得更具体、更可衡量。"

        if overall >= 85:
            return "Your next edge is making your reflections even sharper so each question lands with more precision."
        if overall >= 70:
            return "Your next edge is completing each stage more fully, especially possibility work and the final close."
        return "Your next edge is tightening the contract and the action commitment so the session becomes more concrete and measurable."

    def analyze_session_for_memory(self, api_key: str) -> dict:
        """Analyze the human coach's performance to extract learning insights for the AI coachee."""
        try:
            client = _build_client(api_key)
            transcript = []
            for msg in self.context[-30:]:
                role = "Coach" if msg["role"] == self.user_role else "Coachee"
                transcript.append(f"{role}: {msg['content']}")
            
            prompt = (
                "You are an AI learning module analyzing a human coach's training performance. "
                "Evaluate the human 'Coach' based on Erickson methodology. "
                "Identify their recurring strengths and the specific areas where they should be challenged more in future simulations. "
                "Return ONLY a JSON object with this shape: "
                "{"
                "\"learning_patterns\": \"short summary of how the human coach learns or adjusts\", "
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
            
            content = _response_text(resp).strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            
            return json.loads(content)
        except Exception:
            return {}
