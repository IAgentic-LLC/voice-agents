"""Chapter 18: the guard that exists, and the one that doesn't."""

from voicelab import orders, refund


def test_an_eligible_order_refunds(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    result = refund.issue(path, "A1001")
    assert result["ok"] is True
    assert result["committed_now"] is True
    assert result["amount"] == 24.99


def test_the_same_order_twice_only_commits_once(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    first = refund.issue(path, "A1001")
    second = refund.issue(path, "A1001")
    assert first["committed_now"] is True
    assert second["committed_now"] is False


def test_an_order_outside_the_window_is_refused(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    result = refund.issue(path, "A1003")
    assert result["ok"] is False
    assert "window" in result["reason"]


def test_a_missing_order_is_refused(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    result = refund.issue(path, "Z9999")
    assert result == {"ok": False, "reason": "no such order"}


def test_the_function_never_checks_who_is_calling(tmp_path):
    # This is this chapter's whole point, pinned as a test rather
    # than left as a claim: issue() has no caller-identity parameter
    # to check in the first place.
    import inspect
    sig = inspect.signature(refund.issue)
    assert "caller" not in sig.parameters
    assert "customer" not in sig.parameters
    # Devon's order refunds without anyone claiming to be Devon.
    path = str(tmp_path / "ledger.jsonl")
    result = refund.issue(path, "A1002")
    assert result["ok"] is True
    assert result["customer"] == "Devon Ruiz"
