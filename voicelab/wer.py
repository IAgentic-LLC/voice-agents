"""Word error rate: how many words a transcript gets wrong."""

import re


def words(text: str) -> list[str]:
    """Lower case, keep letters, digits and apostrophes, split on spaces."""
    return re.sub(r"[^a-z0-9' ]", " ", text.lower()).split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """(substitutions + deletions + insertions) / words in the reference,
    found with the edit distance between the two word lists."""
    ref, hyp = words(reference), words(hypothesis)
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(
                row[j] + 1,  # a reference word was deleted
                row[j - 1] + 1,  # an extra word was inserted
                prev + (r != h),  # a word was substituted (or matched)
            )
    return row[-1] / len(ref)
