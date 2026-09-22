"""Chapter 11: a small set of documents, and a way to find one.

Retrieval for a voice agent has the same job as retrieval anywhere: find
the passage that answers the question. What is different is what happens
next. A page can show five sources and let the reader choose. A call has
one channel, and every word spent on a citation is a word the caller has
to sit through.

So these passages carry an id, and the id is for the log, not the ear.

The scorer here is deliberately plain: term overlap weighted by how rare
each term is across the passages, which is the idea behind every ranking
function before the embeddings arrived. It needs no key, no service and
no index, and on eight passages it is not the interesting part.
"""

import math
import re
from dataclasses import dataclass

PASSAGES: dict[str, str] = {
    "refund-timing": (
        "A refund for a duplicate charge is issued within one business "
        "day. It reaches the customer's bank 5 to 10 business days later."
    ),
    "refund-eligibility": (
        "A duplicate charge is always refunded in full. A charge the "
        "customer disputes for another reason is reviewed first."
    ),
    "returns-window": (
        "Anything bought can be returned within 30 days of delivery. "
        "The 30 days run from delivery, not from the order date."
    ),
    "returns-postage": (
        "Return postage is paid by us when the item is faulty, and by "
        "the customer otherwise."
    ),
    "shipping-address": (
        "An order that has already shipped cannot have its address "
        "changed. It has to be returned once it arrives."
    ),
    "shipping-speed": (
        "Standard delivery takes 3 to 5 working days. Next-day delivery "
        "ordered before 4 pm arrives the following working day."
    ),
    "cancelling": (
        "There is no fee for cancelling a subscription early. The "
        "subscription runs until the end of the period already paid for."
    ),
    "support-hours": (
        "The support line is open until 6 pm on Saturdays, and until "
        "8 pm on weekdays. It is closed on Sundays."
    ),
}

WORD = re.compile(r"[a-z0-9]+")


def terms(text: str) -> list[str]:
    return WORD.findall(text.lower())


def _idf() -> dict[str, float]:
    """How rare each word is across the passages."""
    seen: dict[str, int] = {}
    for text in PASSAGES.values():
        for word in set(terms(text)):
            seen[word] = seen.get(word, 0) + 1
    total = len(PASSAGES)
    return {w: math.log(total / n) + 1 for w, n in seen.items()}


IDF = _idf()


@dataclass(frozen=True)
class Hit:
    passage_id: str
    text: str
    score: float


def search(question: str, limit: int = 2) -> list[Hit]:
    """The best passages for a question, most convincing first."""
    wanted = set(terms(question))
    hits = []
    for passage_id, text in PASSAGES.items():
        words = set(terms(text))
        score = sum(IDF.get(w, 0.0) for w in wanted & words)
        if score:
            hits.append(Hit(passage_id, text, round(score, 3)))
    hits.sort(key=lambda h: -h.score)
    return hits[:limit]
