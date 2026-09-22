"""Chapter 8: what a call cost, from the tokens the agent counted.

Both agents write one usage record per call at shutdown. The record is
whatever LiveKit's usage collector holds, one entry per model, so a
cascaded call has three entries and a realtime call has one. Prices come
from Google's published list and are kept in one place here, because
they change and every number in the book that depends on them should
change with them.
"""

from typing import Any

from livekit.agents import AgentSession

from voicelab import runlog


def record(session: AgentSession, stages: str) -> None:
    """Write this call's token counts. Never raises: a logging failure
    must not break a call."""
    try:
        models = []
        for usage in session.usage.model_usage:
            dump = getattr(usage, "model_dump", None)
            models.append(dump() if dump else vars(usage))
        runlog.append(stages, {"stage": "usage", "models": models})
    except Exception as exc:
        runlog.append(stages, {"stage": "usage_error", "error": repr(exc)})


def totals(models: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Tokens and seconds per model, for one call."""
    out: dict[str, dict[str, float]] = {}
    for one in models:
        model = one.get("model", "?")
        counts = out.setdefault(model, {})
        for field, value in one.items():
            if isinstance(value, (int, float)) and value:
                counts[field] = counts.get(field, 0) + value
    return out
