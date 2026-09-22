"""Chapter 8: the same words for both agents, and the tasks they answer.

The cascaded agent and the realtime agent are only comparable if they are
told exactly the same things. Both import INSTRUCTIONS from here.

Each task is a recorded question and the fact a correct answer has to
contain. The facts are in the instructions above, so an agent that
listened and answered from its instructions can get every one right. The
check is a pattern match on the answer's words, which is a weak measure:
it cannot tell a right answer from a right number in a wrong sentence.
Chapter 8 prints every transcript beside its score for that reason.
"""

import re
from dataclasses import dataclass

POLICY = """
Refunds for a duplicate charge are issued within one business day, and
reach the customer's bank in 5 to 10 business days.
Anything bought can be returned within 30 days of delivery.
An order that has already shipped cannot have its address changed; it
has to be returned once it arrives.
There is no fee for cancelling a subscription early.
The support line is open until 6 pm on Saturdays.
"""

INSTRUCTIONS = (
    "You are a concise customer support assistant. "
    "Answer in one or two short sentences. "
    "Answer only from this policy, and include the specific detail the "
    "caller asks for:" + POLICY
)


@dataclass(frozen=True)
class Task:
    name: str
    question: str        # the recording the caller plays
    asks: str            # what the caller wants, for the report
    wants: str           # a right answer contains this
    tolerate: str = ""   # the same fact said another way

    def passed(self, answer: str) -> bool:
        patterns = [self.wants] + ([self.tolerate] if self.tolerate else [])
        return any(re.search(p, answer, re.I) for p in patterns)


TASKS = [
    Task("refund", "audio/refund_question.wav", "how long a refund takes",
         r"5\s*(to|-|and)\s*10", r"five\s*(to|-|and)\s*ten"),
    Task("return", "audio/ch08/return_window.wav", "the return window",
         r"\b30\b", r"thirty"),
    Task("address", "audio/ch08/change_address.wav",
         "changing a shipped order's address",
         r"\b(cannot|can't|can not|unable|not possible|no)\b"),
    Task("cancel", "audio/ch08/cancel_fee.wav", "an early cancellation fee",
         r"\bno\b.{0,20}fee", r"free|without a fee|no charge"),
    Task("hours", "audio/ch08/saturday_hours.wav", "Saturday closing time",
         r"\b6\s*(pm|p\.m\.)", r"six\s*(pm|p\.m\.|o'clock)"),
]

TASKS_BY_NAME = {task.name: task for task in TASKS}


def task_of(question: str) -> Task | None:
    """Which task a recorded call was asking."""
    for task in TASKS:
        if question.endswith(task.question.split("/")[-1]):
            return task
    return None
