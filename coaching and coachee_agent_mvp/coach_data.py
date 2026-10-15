from coaching_core import CoachingState

ACKNOWLEDGMENTS = {
    "en": [
        "I hear you.",
        "Thank you for sharing that.",
        "That sounds like a meaningful insight.",
        "I appreciate your honesty.",
        "That's a powerful reflection.",
        "I'm following you.",
        "Interesting perspective.",
    ],
    "zh": [
        "我听到了你的分享。",
        "感谢你分享这些想法。",
        "这是一个非常有意义的洞察。",
        "感谢你的诚实。",
        "这是一个很有力量的反思。",
        "我理解你的意思。",
        "很有趣的视角。",
    ],
}


OPENING_QUESTIONS = {
    "en": {
        CoachingState.CONTRACT: [
            "What would you like to achieve by the end of our conversation today?",
            "If this session was incredibly valuable to you, what would be the outcome?",
            "What is the most important topic for you to focus on right now?",
        ],
        CoachingState.EXPERIENCE: [
            "What resources or strengths do you already have that can help you with this?",
            "Tell me about a time when you successfully handled a similar situation.",
            "On a scale of 1 to 10, where are you right now towards this goal?",
        ],
        CoachingState.ACTION: [
            "If anything were possible and you had no constraints, what could you do?",
            "What are three different paths you could take to move forward?",
            "What would be the smallest, easiest step you could take today?",
        ],
        CoachingState.VALUE: [
            "Of the options we discussed, which one are you going to commit to?",
            "When specifically will you take this first step?",
            "How will you know that you have succeeded in taking this step?",
        ],
        # Asked when commitment hands over to closing; the client's answer ends the session.
        CoachingState.CLOSING: [
            "What are you taking away from our conversation today?",
            "How do you feel now, compared with when we started?",
            "What has become clearer for you today?",
        ],
    },
    "zh": {
        CoachingState.CONTRACT: [
            "在今天的对话结束时，你想达成什么目标？",
            "如果这次教练辅导对你非常有价值，它的成果会是什么？",
            "你现在最关注的话题是什么？",
        ],
        CoachingState.EXPERIENCE: [
            "你已经拥有哪些可以帮助你实现这一目标的资源或优势？",
            "请告诉我一个你成功处理类似情况的经历。",
            "如果1到10分，你目前距离这个目标在几分？",
        ],
        CoachingState.ACTION: [
            "如果没有任何限制，一切皆有可能，你会怎么做？",
            "为了向前迈进，你可以采取哪三种不同的途径？",
            "你今天可以采取的最细微、最简单的一步是什么？",
        ],
        CoachingState.VALUE: [
            "在我们讨论的选项中，你打算致力于哪一个？",
            "你具体会在什么时候采取这第一步？",
            "你怎么知道你已经成功迈出了这一步？",
        ],
        CoachingState.CLOSING: [
            "今天的对话，你最想带走的是什么？",
            "和刚开始相比，你现在感觉怎么样？",
            "今天有什么变得更清楚了？",
        ],
    },
}


DEEPENING_QUESTIONS = {
    "en": {
        CoachingState.CONTRACT: [
            "What makes that goal particularly important for you right now?",
            "How will achieving this change things for you in your daily life?",
            "If you achieve this, what else will it enable you to do?",
            "What would be the first sign that you're on the right track?",
        ],
        CoachingState.EXPERIENCE: [
            "What did you learn about yourself in those successful moments?",
            "What other strengths can you bring to the table?",
            "Looking at your current situation, what is 'working' despite the challenges?",
            "What would a 'scale of 10' look like specifically?",
        ],
        CoachingState.ACTION: [
            "What excites you most about these options?",
            "Which of these options feels most aligned with your values?",
            "Who could support you in making this happen?",
            "If you were your own best coach, what advice would you give yourself here?",
        ],
        CoachingState.VALUE: [
            "What is your level of commitment to this action on a scale of 1-10?",
            "What might get in the way, and how will you handle that?",
            "What is the very first thing you'll do after we finish this session?",
            "How can you make this commitment even more solid?",
        ],
    },
    "zh": {
        CoachingState.CONTRACT: [
            "为什么这个目标对现在的你特别重要？",
            "实现这个目标会如何改变你的日常生活？",
            "如果你达成了这个目标，它还会让你有能力去做什么？",
            "如果你走在正确的轨道上，第一个迹象会是什么？",
        ],
        CoachingState.EXPERIENCE: [
            "在那些成功的时刻，你对自己有了哪些了解？",
            "你还有哪些优势可以发挥出来？",
            "观察你目前的情况，尽管有挑战，哪些部分依然是有效的？",
            "具体的‘10分’看起来会是什么样子？",
        ],
        CoachingState.ACTION: [
            "在这些选项中，什么最让你感到兴奋？",
            "这些选项中哪一个最符合你的价值观？",
            "谁可以支持你实现这一目标？",
            "如果你是你自己最好的教练，你会给自己什么建议？",
        ],
        CoachingState.VALUE: [
            "从1到10，你对这个行动的承诺程度是多少？",
            "可能会出现什么阻碍？你会如何应对？",
            "结束这次辅导后，你做的第一件事会是什么？",
            "你如何能让这份承诺变得更加坚定？",
        ],
    },
}


BRIDGE_PHRASES = {
    "en": {
        CoachingState.CONTRACT: "Now that we have a clear focus, let's explore where you are currently in relation to it.",
        CoachingState.EXPERIENCE: "Having looked at your current resources, let's look ahead at the possibilities.",
        CoachingState.ACTION: "With these exciting options in mind, let's decide on a concrete path forward.",
        CoachingState.VALUE: "You have a solid plan. Let's take a moment to reflect on our conversation today.",
    },
    "zh": {
        CoachingState.CONTRACT: "现在我们有了清晰的目标，让我们看看你目前与这个目标之间的现状。",
        CoachingState.EXPERIENCE: "了解了你目前的资源，让我们展望一下未来的可能性。",
        CoachingState.ACTION: "带着这些令人兴奋的选项，让我们决定一个具体的行动路径。",
        CoachingState.VALUE: "你已经有了一个坚实的计划。让我们花点时间回顾一下今天的对话。",
    },
}


# Said after the session has ended, when the person can no longer reply, so none of them asks anything.
CLOSING_MESSAGES = {
    "en": [
        "Thank you for the work you did today. I hope your next step goes well.",
        "That's a good place to stop for today. Good luck with your next step.",
        "Thank you for thinking this through so openly today. Take care, and good luck with what comes next.",
    ],
    "zh": [
        "谢谢你今天的投入，祝你的下一步顺利。",
        "今天就先到这里，祝你接下来的行动顺利。",
        "谢谢你今天这么坦诚地梳理这些。保重，祝接下来一切顺利。",
    ],
}


TRANSLATE_EN_TO_ZH: dict[str, str] = {}
TRANSLATE_ZH_TO_EN: dict[str, str] = {}


def _build_translation_maps():
    for en, zh in zip(ACKNOWLEDGMENTS["en"], ACKNOWLEDGMENTS["zh"]):
        TRANSLATE_EN_TO_ZH[en] = zh
        TRANSLATE_ZH_TO_EN[zh] = en

    for state in CoachingState:
        if state in OPENING_QUESTIONS["en"]:
            for en, zh in zip(OPENING_QUESTIONS["en"][state], OPENING_QUESTIONS["zh"][state]):
                TRANSLATE_EN_TO_ZH[en] = zh
                TRANSLATE_ZH_TO_EN[zh] = en

    for state in CoachingState:
        if state in DEEPENING_QUESTIONS["en"]:
            for en, zh in zip(DEEPENING_QUESTIONS["en"][state], DEEPENING_QUESTIONS["zh"][state]):
                TRANSLATE_EN_TO_ZH[en] = zh
                TRANSLATE_ZH_TO_EN[zh] = en

    for state in CoachingState:
        if state in BRIDGE_PHRASES["en"]:
            en = BRIDGE_PHRASES["en"][state]
            zh = BRIDGE_PHRASES["zh"][state]
            TRANSLATE_EN_TO_ZH[en] = zh
            TRANSLATE_ZH_TO_EN[zh] = en

    for en, zh in zip(CLOSING_MESSAGES["en"], CLOSING_MESSAGES["zh"]):
        TRANSLATE_EN_TO_ZH[en] = zh
        TRANSLATE_ZH_TO_EN[zh] = en


def _translate_template_message(content: str, source_lang: str, target_map: dict[str, str]) -> str | None:
    if content in target_map:
        return target_map[content]

    for ack in ACKNOWLEDGMENTS[source_lang]:
        ack_prefix = f"{ack} "
        if content.startswith(ack_prefix):
            remainder = content[len(ack_prefix):].strip()

            if remainder in target_map:
                return f"{target_map[ack]} {target_map[remainder]}"

            for state in BRIDGE_PHRASES[source_lang]:
                bridge = BRIDGE_PHRASES[source_lang][state]
                if remainder.startswith(f"{bridge} "):
                    tail = remainder[len(bridge):].strip()
                    if bridge in target_map and tail in target_map:
                        return f"{target_map[ack]} {target_map[bridge]} {target_map[tail]}"

    for state in BRIDGE_PHRASES[source_lang]:
        bridge = BRIDGE_PHRASES[source_lang][state]
        if content.startswith(f"{bridge} "):
            tail = content[len(bridge):].strip()
            if bridge in target_map and tail in target_map:
                return f"{target_map[bridge]} {target_map[tail]}"

    return None


_build_translation_maps()


__all__ = [
    "ACKNOWLEDGMENTS",
    "BRIDGE_PHRASES",
    "CLOSING_MESSAGES",
    "DEEPENING_QUESTIONS",
    "OPENING_QUESTIONS",
    "TRANSLATE_EN_TO_ZH",
    "TRANSLATE_ZH_TO_EN",
    "_translate_template_message",
]
