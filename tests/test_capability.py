"""Chapter 20: what a carried chat context actually keeps, and what
it silently drops, when the new agent's tools are not the old
agent's tools.

This is not testing anything this book wrote. `Agent.__init__` calls
`chat_ctx.copy(tools=self._tools)` on whatever it is given
(`livekit/agents/voice/agent.py`), and `ChatContext.copy` itself
drops any `function_call`/`function_call_output` item whose tool
name is not in that list (`livekit/agents/llm/chat_context.py`).
Plain messages are never touched by that filter. Pinning both halves
of that fact is the point: shared conversation is not shared power,
but it is also not shared proof.
"""

from livekit.agents import Agent, function_tool, llm


@function_tool
async def issue_refund(order_number: str) -> str:
    """Issue a refund for an order.

    Args:
        order_number: the order number the caller gives you
    """
    return f"Refunded order {order_number}."


def _history_after_a_real_refund() -> llm.ChatContext:
    return llm.ChatContext([
        llm.ChatMessage(role="user",
                        content=["please refund order A1002"]),
        llm.FunctionCall(call_id="c1", arguments='{"order_number": "A1002"}',
                         name="issue_refund"),
        llm.FunctionCallOutput(call_id="c1", name="issue_refund",
                               output="Refunded order A1002.",
                               is_error=False),
        llm.ChatMessage(role="assistant",
                        content=["I've refunded your order."]),
    ])


def test_the_agent_with_the_tool_keeps_the_proof():
    billing = Agent(instructions="billing", tools=[issue_refund],
                    chat_ctx=_history_after_a_real_refund())
    kinds = [item.type for item in billing.chat_ctx.items]
    assert "function_call" in kinds
    assert "function_call_output" in kinds


def test_the_agent_without_the_tool_loses_the_proof_but_not_the_words():
    billing = Agent(instructions="billing", tools=[issue_refund],
                    chat_ctx=_history_after_a_real_refund())
    technical = Agent(instructions="technical", chat_ctx=billing.chat_ctx)
    kinds = [item.type for item in technical.chat_ctx.items]
    assert "function_call" not in kinds
    assert "function_call_output" not in kinds
    texts = [
        m.text_content for m in technical.chat_ctx.items
        if m.type == "message"
    ]
    assert "I've refunded your order." in texts
