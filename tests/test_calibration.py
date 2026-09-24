"""Chapter 24: every probe here was constructed specifically to
disagree with Task.passed, and this pins that it still does."""

from voicelab.calibration import PROBES, disagreements, scorer_verdict


def test_every_probe_disagrees_with_the_scorer():
    bad = disagreements()
    assert len(bad) == len(PROBES)


def test_a_negated_answer_still_passes_the_refund_pattern():
    probe = next(p for p in PROBES if p.task == "refund")
    assert scorer_verdict(probe) is True
    assert probe.human_says_right is False


def test_an_idiomatic_correct_answer_fails_the_address_pattern():
    probe = next(p for p in PROBES if p.task == "address")
    assert scorer_verdict(probe) is False
    assert probe.human_says_right is True
