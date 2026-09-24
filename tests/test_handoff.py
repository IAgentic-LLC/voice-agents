"""Chapter 19: carrying a handoff's context forward is one keyword
argument, not something the framework does on its own."""

from livekit.agents import Agent, llm

from voicelab import handoff


def _receptionist_with_one_message() -> Agent:
    ctx = llm.ChatContext(
        [llm.ChatMessage(role="user", content=["my order is A1002"])]
    )
    return Agent(instructions="receptionist", chat_ctx=ctx)


def test_carry_false_hands_the_next_agent_nothing():
    receptionist = _receptionist_with_one_message()
    assert handoff.context_to_carry(receptionist, carry=False) is None


def test_carry_true_hands_the_next_agent_the_same_items():
    receptionist = _receptionist_with_one_message()
    carried = handoff.context_to_carry(receptionist, carry=True)
    assert carried is not None
    assert len(carried.items) == 1
    assert carried.items[0].text_content == "my order is A1002"


def test_an_agent_given_nothing_starts_with_an_empty_context():
    # Pinning Agent's own default, not this chapter's code: this is
    # what carry=False silently reproduces.
    blank = Agent(instructions="technical support")
    assert blank.chat_ctx.items == []
