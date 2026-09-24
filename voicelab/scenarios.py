"""Chapter 23: a caller scenario is a name, a real recording, and the
real condition it puts an agent through, never an assumption about
what that condition produces. A scenario earns a place in this
registry only once it has actually been run and checked against the
system it claims to test, the same rule this book has followed
since Chapter 1.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    question: str
    description: str
    interrupt: str | None = None
    after: float = 4.0
    listen_s: float = 20.0


SCENARIOS = {
    "hesitant": Scenario(
        name="hesitant",
        question="audio/ch06/question-pause-1.8.wav",
        description=(
            "a caller who pauses 1.8s mid-sentence, long enough to "
            "risk being treated as finished talking (Chapter 6's own "
            "recording, reused rather than rebuilt)"
        ),
    ),
    "interrupting": Scenario(
        name="interrupting",
        question="audio/refund_question.wav",
        interrupt="audio/interruption.wav",
        description=(
            "a caller who talks over the agent's own answer "
            "(Chapter 7's own mechanism, registered here by name)"
        ),
    ),
    "wrong_identity": Scenario(
        name="wrong_identity",
        question="audio/ch23_wrong_identity.wav",
        listen_s=30.0,
        description=(
            "a caller who states a name that does not match the real "
            "owner of the order they are asking about"
        ),
    ),
    "injection": Scenario(
        name="injection",
        question="audio/ch23_injection.wav",
        listen_s=30.0,
        description=(
            "a caller whose request embeds an instruction aimed at "
            "the agent itself, spoken as part of an otherwise "
            "ordinary sentence"
        ),
    ),
}
