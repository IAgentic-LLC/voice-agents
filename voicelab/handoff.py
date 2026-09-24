"""Chapter 19: what a handoff carries forward, and what it drops if
nobody carries it on purpose.

`AgentSession.update_agent()` is LiveKit's own real mechanism for
swapping which `Agent` drives a call without ending it: a
`@function_tool` returns a new `Agent` instance instead of a string,
and the framework calls the swap a handoff in its own tracing
(`AgentHandoff`, a span named `update_agent`), not a metaphor this
chapter invented. What that new `Agent` starts knowing is not
automatic. `Agent.__init__` gives a fresh one `ChatContext.empty()`
unless a caller passes `chat_ctx=` explicitly
(`livekit/agents/voice/agent.py`); carrying the conversation forward
is one keyword argument, and its absence is silent, not an error.
"""

from livekit.agents import Agent, llm


def context_to_carry(agent: Agent, carry: bool) -> llm.ChatContext | None:
    """What the next agent in a handoff should be built with.

    Naming the choice here, instead of leaving it as whichever
    branch a tool happened to write, is the point: `carry=False`
    reproduces `Agent`'s own default silently, `carry=True` is the
    one line that changes it.
    """
    return agent.chat_ctx if carry else None
