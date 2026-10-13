import random
from dataclasses import dataclass, field

from coaching_core import CoachingState, _strip_json_fence

COACHEE_STAGE_ORDER = [
    CoachingState.CONTRACT,
    CoachingState.EXPERIENCE,
    CoachingState.ACTION,
    CoachingState.VALUE,
]


COACHEE_ACKNOWLEDGMENTS = {
    "en": [
        "That question helps.",
        "Let me think that through.",
        "I notice that lands with me.",
        "I can feel that opening something up.",
    ],
    "zh": [
        "这个问题对我有帮助。",
        "让我认真想一想。",
        "我感觉这个问题触动到我了。",
        "这个角度让我有些新的看见。",
    ],
}


COACHEE_BRIDGES = {
    "en": {
        CoachingState.CONTRACT: "Saying it out loud makes the goal clearer. I am ready to look at what is really happening right now.",
        CoachingState.EXPERIENCE: "I can see the reality more clearly now. I am ready to explore what options I actually have.",
        CoachingState.ACTION: "I have more possibilities on the table now. I am ready to choose what I will really commit to.",
        CoachingState.VALUE: "My next step feels concrete now. I am ready to wrap up and look at how this coaching process went.",
    },
    "zh": {
        CoachingState.CONTRACT: "这样说出来以后，我的目标更清晰了。我准备好看看自己眼下真实的处境了。",
        CoachingState.EXPERIENCE: "现在我对现实处境看得更清楚了。我准备开始探索自己真正可以采取的选项。",
        CoachingState.ACTION: "现在桌面上的可能性更多了。我准备决定自己真正要承诺的行动。",
        CoachingState.VALUE: "我的下一步已经变得具体了。我准备收束这次对话，也看看整个教练过程进行得怎么样。",
    },
}


COACHEE_STAGE_HINTS = {
    "en": {
        CoachingState.CONTRACT: "Help the coachee clarify a concrete session outcome.",
        CoachingState.EXPERIENCE: "Explore reality, strengths, resources, and what is already working.",
        CoachingState.ACTION: "Open up new possibilities before narrowing toward a choice.",
        CoachingState.VALUE: "Land on a committed next step, timeline, and accountability.",
        CoachingState.CLOSING: "Close the session and review the coaching quality.",
    },
    "zh": {
        CoachingState.CONTRACT: "帮助学员澄清一个具体的本次会谈目标。",
        CoachingState.EXPERIENCE: "探索现状、优势、资源，以及已经有效的部分。",
        CoachingState.ACTION: "先打开更多可能性，再逐步收束到选择。",
        CoachingState.VALUE: "落到明确的下一步、时间点和责任承诺。",
        CoachingState.CLOSING: "结束本次会谈，并回顾教练过程质量。",
    },
}


@dataclass(frozen=True)
class ScenarioBundle:
    intro: dict[str, str]
    contract: dict[str, list[str]]
    experience: dict[str, list[str]]
    action: dict[str, list[str]]
    value: dict[str, list[str]]
    closing: dict[str, list[str]]


@dataclass
class CoachingMetrics:
    open_questions: int = 0
    reflective_turns: int = 0
    action_questions: int = 0
    commitment_questions: int = 0
    total_questions: int = 0
    stage_questions: dict[CoachingState, int] = field(default_factory=lambda: {state: 0 for state in CoachingState})
    coach_signals: dict[CoachingState, set[str]] = field(default_factory=lambda: {state: set() for state in CoachingState})
    facts_shared: dict[CoachingState, set[str]] = field(default_factory=lambda: {state: set() for state in CoachingState})


SCENARIOS = [
    ScenarioBundle(
        intro={
            "en": "I am managing a small product team, and I keep stepping in to solve every problem myself. I want coaching on how to delegate without feeling that I am losing control.",
            "zh": "我在带一个小型产品团队，但我总是忍不住亲自下场解决每个问题。我想借这次教练对话理清，怎样在不失控的前提下更好地授权。",
        },
        contract={
            "goal": {
                "en": [
                    "By the end of this conversation, I want a clear way to decide what I should keep and what I should hand over.",
                    "A useful outcome for me would be leaving with one concrete delegation move I trust enough to try this week.",
                ],
                "zh": [
                    "在这次对话结束前，我想清楚自己该保留什么、又该交出去什么。",
                    "如果这次对我有帮助，我希望能带着一个我愿意在本周尝试的具体授权动作离开。",
                ],
            },
            "importance": {
                "en": [
                    "This matters because my team is waiting for me too much, and I am exhausted from being the bottleneck.",
                    "If I do not change this, my team will not grow and I will keep burning out.",
                ],
                "zh": [
                    "这对我重要，是因为团队现在太依赖我，而我自己也快被这种瓶颈状态拖垮了。",
                    "如果我不调整，团队不会成长，我自己也会继续被消耗。",
                ],
            },
            "success": {
                "en": [
                    "A sign of success would be that I can walk into next week's planning meeting knowing exactly which decisions I will stop rescuing.",
                    "I would know this worked if I could let one team member own a deliverable end to end without taking it back.",
                ],
                "zh": [
                    "如果我下周开计划会时，能明确知道哪些决定我不再替团队兜底，那就是一个成功迹象。",
                    "如果我能让一位成员完整负责一个交付件，而且自己不再把它拿回来，我就知道这次有成果了。",
                ],
            },
        },
        experience={
            "reality": {
                "en": [
                    "Right now I jump in fastest because I know the context, so everyone comes back to me for final decisions.",
                    "My calendar is packed with review meetings because I have taught the team that I am the safety net.",
                ],
                "zh": [
                    "现在我总是最快跳进去，因为我最熟悉上下文，所以最后所有决定又回到我这里。",
                    "我的日程几乎被各种 review 占满，因为我已经把自己训练成了团队的安全网。",
                ],
            },
            "obstacle": {
                "en": [
                    "The hard part is that I worry mistakes will slow everything down and reflect badly on me.",
                    "I also notice guilt. Delegating sounds right, but emotionally it feels like I am abandoning the team.",
                ],
                "zh": [
                    "最难的是，我担心一旦出错会拖慢节奏，也会显得我没有带好团队。",
                    "我还会有一种愧疚感。理性上我知道要授权，但情感上又像是在丢下团队。",
                ],
            },
            "strength": {
                "en": [
                    "One strength I do have is that I am good at seeing people's potential and matching work to their growth edge.",
                    "When I slow down, I can actually coach people well. I just stop doing that under pressure.",
                ],
                "zh": [
                    "我的一个优势是，我其实很会看到别人的潜力，也能把工作和他们的成长边界匹配起来。",
                    "在我放慢的时候，我其实很会带人，只是压力一来我就不这么做了。",
                ],
            },
            "past_success": {
                "en": [
                    "There was one project last quarter where I let a designer lead stakeholder updates, and she handled it better than I expected.",
                    "I have delegated well before when I was explicit about the outcome instead of prescribing every step.",
                ],
                "zh": [
                    "上个季度有个项目，我曾让一位设计师主导干系人同步，结果她做得比我预期还好。",
                    "以前我授权做得好的时候，通常都是我把结果讲清楚，而不是把每一步都规定死。",
                ],
            },
            "scale": {
                "en": [
                    "On a scale of 1 to 10, I am probably at a 4. I am aware of the issue, but I still fall back into old habits quickly.",
                    "A 10 would look like trusting the team with ownership while I stay available as support instead of control.",
                ],
                "zh": [
                    "如果 1 到 10 分，我现在大概在 4 分。我知道问题在哪，但很容易又回到老习惯。",
                    "如果是 10 分，那会是我能够把 ownership 交给团队，而我提供的是支持，不是控制。",
                ],
            },
        },
        action={
            "possibility": {
                "en": [
                    "One option is to choose a low-risk project and make the decision rights explicit before it starts.",
                    "Another option is to stop answering immediately and ask my team what they recommend before I step in.",
                ],
                "zh": [
                    "一个选项是挑一个风险较低的项目，在开始前就把决策权限讲清楚。",
                    "另一个选项是，我先不马上给答案，而是先问团队成员的判断，再决定是否介入。",
                ],
            },
            "stretch": {
                "en": [
                    "If I were being bold, I would let my senior PM run the next client sync without me in the room.",
                    "The exciting version would be shifting from chief problem-solver to a manager who develops decision-makers.",
                ],
                "zh": [
                    "如果我更大胆一点，我会让资深 PM 在没有我在场的情况下主持下一次客户同步。",
                    "更让我兴奋的版本，是我从“首席救火员”变成“培养决策者的管理者”。",
                ],
            },
            "support": {
                "en": [
                    "The person who could support me most is my senior PM because she already wants more ownership.",
                    "My manager could also help if I tell him I am deliberately practicing delegation instead of avoiding responsibility.",
                ],
                "zh": [
                    "最能支持我的人其实是资深 PM，因为她本来就希望承担更多 ownership。",
                    "如果我明确告诉上级，我是在刻意练习授权而不是逃避责任，他也能支持我。",
                ],
            },
        },
        value={
            "commitment": {
                "en": [
                    "The action I am most ready to commit to is handing the next sprint planning follow-up to my senior PM.",
                    "I want to commit to defining the outcome, guardrails, and decision rights before that handoff happens.",
                ],
                "zh": [
                    "我现在最愿意承诺的动作，是把下一次 sprint planning 的后续跟进交给资深 PM。",
                    "我也愿意在交接前把预期结果、边界和决策权限讲清楚。",
                ],
            },
            "timeline": {
                "en": [
                    "I can do that on Tuesday before the planning meeting, and I can send the delegation note right after lunch.",
                    "The first step happens this week, not sometime later. If I wait, I will avoid it.",
                ],
                "zh": [
                    "我可以在周二计划会前做这件事，午饭后就把授权说明发出去。",
                    "第一步必须发生在这周，而不是以后再说；一拖延我就会逃开。",
                ],
            },
            "risk": {
                "en": [
                    "The main risk is that I will see an imperfect draft and take the work back. I need a rule to pause before rescuing.",
                    "Another risk is that I send mixed messages, so I need to be explicit that ownership stays with her.",
                ],
                "zh": [
                    "最大的风险是，我一看到不够完美的版本就把事情重新接回来，所以我需要一个先暂停、别立刻救火的规则。",
                    "另一个风险是我会传递混乱信号，所以我需要明确告诉对方 ownership 仍然在她手里。",
                ],
            },
            "accountability": {
                "en": [
                    "To stay accountable, I could message my manager after the meeting and tell him what I delegated and what I held back from reclaiming.",
                    "I also want to check in with myself after the meeting and note whether I coached or controlled.",
                ],
                "zh": [
                    "为了保持承诺，我可以在会后给上级发消息，告诉他我授权了什么，以及我克制住没有重新收回什么。",
                    "我也想在会后给自己做个复盘，看看自己是在教练式支持，还是又回到了控制。",
                ],
            },
        },
        closing={
            "reflection": {
                "en": [
                    "What shifted for me most is that delegation now feels like a way to grow the team, not just a personal risk.",
                    "The most valuable part was realizing I already have evidence that people can step up when I stop over-directing.",
                ],
                "zh": [
                    "对我来说最大的转变是，我开始把授权看成一种帮助团队成长的方式，而不只是个人风险。",
                    "最有价值的部分，是我看见自己其实已经有证据证明：只要我不事事过度指挥，别人是能站出来的。",
                ],
            }
        },
    ),
    ScenarioBundle(
        intro={
            "en": "I have been thinking about a possible career pivot for months, and I keep circling instead of deciding. I want coaching that helps me find a direction I can truly move on.",
            "zh": "我已经纠结职业转型这件事好几个月了，一直在打转却没有决定。我想通过这次教练把方向理出来，至少能真正往前走一步。",
        },
        contract={
            "goal": {
                "en": [
                    "A good outcome would be leaving with a decision framework instead of another vague feeling.",
                    "By the end of this session, I want to know what kind of move I am actually committing to test first.",
                ],
                "zh": [
                    "对我来说，一个好的结果是带着一个清晰的决策框架离开，而不是再多一种模糊感觉。",
                    "在这次对话结束前，我想知道自己真正准备先测试哪一种转型方向。",
                ],
            },
            "importance": {
                "en": [
                    "This matters because staying undecided is draining my confidence and making me show up half-heartedly in my current role.",
                    "If I keep postponing this, another year will pass and I will still be talking about change instead of making it.",
                ],
                "zh": [
                    "这件事重要，是因为持续不做决定正在消耗我的自信，也让我在现在的工作里越来越心不在焉。",
                    "如果我继续拖延，再过一年我可能还在谈“想改变”，而不是已经开始改变。",
                ],
            },
            "success": {
                "en": [
                    "A success sign would be that I can name one direction and one experiment I will run in the next two weeks.",
                    "I would know this worked if my next step feels chosen rather than endlessly analyzed.",
                ],
                "zh": [
                    "如果我能说出一个方向，以及未来两周要做的一个验证实验，那就是成功迹象。",
                    "如果我的下一步是“我选择了”，而不是“我又分析了一轮”，我就知道这次对话有效。",
                ],
            },
        },
        experience={
            "reality": {
                "en": [
                    "Right now I keep comparing three options: staying and growing, moving into consulting, or building something of my own.",
                    "I read, journal, and ask friends for advice, but I still avoid any move that would create real exposure.",
                ],
                "zh": [
                    "现在我一直在比较三个方向：留下来继续成长、转去做咨询，或者自己做点东西。",
                    "我会看资料、写日记、问朋友意见，但只要一涉及真正会暴露风险的动作，我就又停住了。",
                ],
            },
            "obstacle": {
                "en": [
                    "The main block is fear of making the wrong choice and discovering I gave up stability for something that is not actually right for me.",
                    "I also notice that I want certainty before acting, which is probably unrealistic.",
                ],
                "zh": [
                    "最大的卡点，是我害怕选错，最后发现自己为了不适合的方向放弃了稳定。",
                    "我也发现自己总想在行动前先获得确定性，而这本身可能就不现实。",
                ],
            },
            "strength": {
                "en": [
                    "I am actually strong at learning fast and building relationships, and both would help in a pivot.",
                    "When I believe in something, I can be very disciplined and persistent.",
                ],
                "zh": [
                    "其实我的强项是学得快、也擅长建立关系，这两点在转型里都会有帮助。",
                    "只要我真正认定一件事，我通常会很自律，也很能坚持。",
                ],
            },
            "past_success": {
                "en": [
                    "I changed industries once before, and what made it work was talking to real people instead of guessing from the outside.",
                    "One reason that transition worked was that I tested with small experiments before making a full leap.",
                ],
                "zh": [
                    "我以前也换过一次行业，那次之所以成功，是因为我去和真实的人聊，而不是只在外面猜。",
                    "那次转变有用的另一个原因，是我先做了小实验，再决定要不要全面切换。",
                ],
            },
            "scale": {
                "en": [
                    "I would put myself at a 5 out of 10. I am not confused about everything, but I am not yet converting clarity into movement.",
                    "A 10 would look like choosing a direction and learning from action instead of waiting for perfect confidence.",
                ],
                "zh": [
                    "如果 1 到 10 分，我给自己 5 分。我不是完全没头绪，但我还没有把清晰感转化成行动。",
                    "10 分会是我选定一个方向，并从行动里学习，而不是等到完全自信才开始。",
                ],
            },
        },
        action={
            "possibility": {
                "en": [
                    "One path is to stay in my current role for six more months but deliberately build consulting-style projects on the side.",
                    "Another path is to run informational interviews with people who already work in the roles I am imagining.",
                ],
                "zh": [
                    "一个路径是我先在当前岗位再待六个月，但刻意在业余时间搭一些咨询型项目。",
                    "另一个路径是，我去和已经在我设想岗位上的人做信息访谈。",
                ],
            },
            "stretch": {
                "en": [
                    "If I were really trusting myself, I would stop asking which option is safest and start asking which one feels most alive.",
                    "The bolder move would be launching a small pilot offer and seeing whether I enjoy serving clients directly.",
                ],
                "zh": [
                    "如果我更相信自己，我会停止问“哪个最安全”，改成问“哪个最让我有生命力”。",
                    "更大胆的动作，是直接推出一个小型试点服务，看看自己是否真的享受直接服务客户。",
                ],
            },
            "support": {
                "en": [
                    "A former mentor could support me because she knows both my strengths and the consulting world.",
                    "Two friends have already offered to introduce me to people in adjacent roles if I ask.",
                ],
                "zh": [
                    "我以前的一位导师能支持我，因为她既了解我的优势，也了解咨询行业。",
                    "另外有两个朋友已经说过，如果我开口，他们愿意帮我介绍相关岗位的人。",
                ],
            },
        },
        value={
            "commitment": {
                "en": [
                    "The move I am ready to commit to is scheduling three informational interviews before deciding anything larger.",
                    "I also want to create one simple page that describes the kind of work I might offer, just to make the idea real.",
                ],
                "zh": [
                    "我现在最愿意承诺的动作，是在做更大决定前，先约三场信息访谈。",
                    "我也想做一个很简单的页面，把我可能提供的服务写出来，先让这个想法变得真实。",
                ],
            },
            "timeline": {
                "en": [
                    "I can send the first two outreach messages tomorrow evening and block time for the third on Thursday.",
                    "The page draft could be done by Sunday if I stop making it more complicated than it needs to be.",
                ],
                "zh": [
                    "我可以明天晚上先发出两条邀约消息，周四再把第三条发出去。",
                    "如果我不把事情搞复杂，那个页面草稿周日之前就能完成。",
                ],
            },
            "risk": {
                "en": [
                    "The biggest risk is that I hide inside research again and call it preparation.",
                    "I also know I may judge the first conversations too harshly and treat awkwardness as evidence I should stop.",
                ],
                "zh": [
                    "最大的风险，是我又躲回研究和分析里，并把那种拖延包装成“准备”。",
                    "我也知道自己可能会过度解读前几次交流的不顺，把尴尬当成应该停止的证据。",
                ],
            },
            "accountability": {
                "en": [
                    "To stay accountable, I want to text a friend after I send the outreach messages and tell her exactly what I did.",
                    "I also want to review on Sunday what I learned from acting instead of what I still cannot guarantee.",
                ],
                "zh": [
                    "为了保持承诺，我想在发出邀约后给朋友发消息，明确告诉她我具体做了什么。",
                    "我也想在周日回看时，把重点放在我从行动里学到了什么，而不是还不能保证什么。",
                ],
            },
        },
        closing={
            "reflection": {
                "en": [
                    "What changed most is that I stopped treating the next move as a permanent verdict and started seeing it as an experiment.",
                    "The most useful shift was realizing I do not need certainty before action; I need action that creates better information.",
                ],
                "zh": [
                    "最大的变化是，我不再把下一步看成永久判决，而开始把它看成一个实验。",
                    "最有价值的转变，是我意识到自己不需要先拥有确定性才行动，而是需要用行动创造更好的信息。",
                ],
            }
        },
    ),
]


def _choice(options: list[str], used: set[str]) -> str:
    remaining = [item for item in options if item not in used]
    if remaining:
        pick = random.choice(remaining)
        used.add(pick)
        return pick
    return random.choice(options)


def _mirror_lang_payload(text_or_lines):
    if isinstance(text_or_lines, list):
        return {"en": text_or_lines, "zh": text_or_lines}
    return {"en": text_or_lines, "zh": text_or_lines}


def _scenario_bundle_from_single_language(data: dict) -> ScenarioBundle:
    def pack_map(section: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
        return {key: _mirror_lang_payload(value) for key, value in section.items()}

    return ScenarioBundle(
        intro=_mirror_lang_payload(data["intro"]),
        contract=pack_map(data["contract"]),
        experience=pack_map(data["experience"]),
        action=pack_map(data["action"]),
        value=pack_map(data["value"]),
        closing=pack_map(data["closing"]),
    )


__all__ = [
    "COACHEE_ACKNOWLEDGMENTS",
    "COACHEE_BRIDGES",
    "COACHEE_STAGE_HINTS",
    "COACHEE_STAGE_ORDER",
    "CoachingMetrics",
    "SCENARIOS",
    "ScenarioBundle",
    "_choice",
    "_scenario_bundle_from_single_language",
    "_strip_json_fence",
]
