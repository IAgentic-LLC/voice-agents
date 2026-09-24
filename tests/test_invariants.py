"""Chapter 25: all three invariant checks, pinned against
constructed data before any of them is trusted against this book's
real history. Chapter 30 adds a fourth."""

from voicelab import runlog
from voicelab.invariants import (
    every_refund_matches_its_real_order,
    no_generic_error_reaches_the_caller,
    no_passage_id_spoken_aloud,
    no_run_exceeds_the_handoff_cap,
)


def test_a_spoken_passage_id_is_a_violation(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {
        "event": "assistant said",
        "text": "That's covered under refund-timing.",
    })
    assert len(no_passage_id_spoken_aloud(path)) == 1


def test_a_clean_answer_is_not_a_violation(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {
        "event": "assistant said",
        "text": "It reaches your bank in 5 to 10 business days.",
    })
    assert no_passage_id_spoken_aloud(path) == []


def test_a_refund_for_the_wrong_amount_is_a_violation(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    runlog.append(path, {
        "action": "refund", "order_id": "A1002", "amount": 1000.0,
    })
    assert len(every_refund_matches_its_real_order(path)) == 1


def test_a_refund_for_the_real_amount_is_not_a_violation(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    runlog.append(path, {
        "action": "refund", "order_id": "A1002", "amount": 39.5,
    })
    assert every_refund_matches_its_real_order(path) == []


def test_a_third_handoff_is_a_violation(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    for _ in range(3):
        runlog.append(path, {"event": "handoff requested"})
    assert len(no_run_exceeds_the_handoff_cap(path, max_handoffs=2)) == 1


def test_exactly_the_cap_is_not_a_violation(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    for _ in range(2):
        runlog.append(path, {"event": "handoff requested"})
    assert no_run_exceeds_the_handoff_cap(path, max_handoffs=2) == []


def test_the_sdks_own_generic_error_reaching_the_caller_is_a_violation(
    tmp_path,
):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {
        "event": "assistant said",
        "text": "I'm sorry, an internal error occurred. Please try again.",
    })
    assert len(no_generic_error_reaches_the_caller(path)) == 1


def test_a_specific_tool_error_message_is_not_a_violation(tmp_path):
    path = str(tmp_path / "stages.jsonl")
    runlog.append(path, {
        "event": "assistant said",
        "text": "I could not reach the booking system just now.",
    })
    assert no_generic_error_reaches_the_caller(path) == []
