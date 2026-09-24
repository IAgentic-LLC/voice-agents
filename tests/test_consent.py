"""Chapter 15: every outbound guard, tested with no call and no network."""

import datetime as dt

from voicelab import consent, runlog


def test_a_number_that_never_consented_cannot_be_called(tmp_path):
    consent_path = str(tmp_path / "consent.jsonl")
    assert consent.has_consent(consent_path, "+15550001234") is False


def test_consent_once_given_is_remembered(tmp_path):
    consent_path = str(tmp_path / "consent.jsonl")
    consent.grant_consent(consent_path, "+15550001234", "signed up on site")
    assert consent.has_consent(consent_path, "+15550001234") is True
    assert consent.has_consent(consent_path, "+15550009999") is False


def test_the_do_not_call_list_overrides_everything(tmp_path):
    dnc_path = str(tmp_path / "dnc.txt")
    consent_path = str(tmp_path / "consent.jsonl")
    trials_path = str(tmp_path / "trials.jsonl")
    dnc = tmp_path / "dnc.txt"
    dnc.write_text("+15550001234\n")
    consent.grant_consent(consent_path, "+15550001234", "signed up")
    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number="+15550001234", now=dt.datetime(2026, 1, 1, 12, 0),
    )
    assert allowed is False
    assert reason == "on the do-not-call list"


def test_quiet_hours_wraps_midnight():
    late = dt.datetime(2026, 1, 1, 22, 0)
    early = dt.datetime(2026, 1, 1, 6, 0)
    midday = dt.datetime(2026, 1, 1, 14, 0)
    edge_start = dt.datetime(2026, 1, 1, 21, 0)
    edge_end = dt.datetime(2026, 1, 1, 8, 0)
    assert consent.in_quiet_hours(late) is True
    assert consent.in_quiet_hours(early) is True
    assert consent.in_quiet_hours(midday) is False
    assert consent.in_quiet_hours(edge_start) is True   # inclusive start
    assert consent.in_quiet_hours(edge_end) is False    # exclusive end


def test_rate_limit_counts_only_recent_calls(tmp_path):
    log_path = str(tmp_path / "trials.jsonl")
    now = 1_000_000.0
    runlog.append(log_path, {"number": "+1555", "attempted": True,
                             "t": now - 10})
    # Backdate the timestamp runlog just wrote, so this test controls
    # time exactly instead of depending on the real clock.
    rows = runlog.read(log_path)
    rows[0]["t"] = now - 10
    import json
    with open(log_path, "w", encoding="utf8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    assert consent.rate_limited(log_path, "+1555", window_s=60,
                                max_calls=1, now=now) is True
    assert consent.rate_limited(log_path, "+1555", window_s=5,
                                max_calls=1, now=now) is False
    assert consent.rate_limited(log_path, "+1999", window_s=60,
                                max_calls=1, now=now) is False


def test_a_refusal_does_not_count_against_the_rate_limit(tmp_path):
    """A number refused for lack of consent was never actually called.
    Counting that refusal against the rate limit would mean a number
    nobody has ever reached can lock itself out anyway, which is the
    wrong direction for a safety guard to fail in."""
    log_path = str(tmp_path / "trials.jsonl")
    now = 1_000_000.0
    runlog.append(log_path, {"number": "+1555", "attempted": False,
                             "reason": "no consent on record"})
    rows = runlog.read(log_path)
    rows[0]["t"] = now - 5
    import json
    with open(log_path, "w", encoding="utf8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    assert consent.rate_limited(log_path, "+1555", window_s=60,
                                max_calls=1, now=now) is False


def test_a_full_hour_rate_limit_window_can_be_checked_at_its_boundary(
    tmp_path
):
    """Chapter 23: the same controlled-clock pattern the test above
    already used, pushed to its own edge. A real hour-long window is
    checked exactly at the instant it opens and the instant before,
    without this test ever waiting a real hour to find out."""
    log_path = str(tmp_path / "trials.jsonl")
    first_attempt = 1_700_000_000.0
    runlog.append(log_path, {"number": "+1555", "attempted": True,
                             "t": first_attempt})

    just_before = first_attempt + 3600 - 0.001
    just_after = first_attempt + 3600 + 0.001
    assert consent.rate_limited(log_path, "+1555", window_s=3600,
                                max_calls=1, now=just_before) is True
    assert consent.rate_limited(log_path, "+1555", window_s=3600,
                                max_calls=1, now=just_after) is False


def test_may_call_checks_in_a_fixed_order(tmp_path):
    """Do-not-call beats missing consent beats quiet hours beats rate
    limit. A caller reading the refusal reason needs to trust the
    order, not just the fact of a refusal."""
    dnc_path = str(tmp_path / "dnc.txt")
    consent_path = str(tmp_path / "consent.jsonl")
    trials_path = str(tmp_path / "trials.jsonl")
    (tmp_path / "dnc.txt").write_text("+1555\n")

    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number="+1555", now=dt.datetime(2026, 1, 1, 22, 0),
    )
    assert (allowed, reason) == (False, "on the do-not-call list")

    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number="+1999", now=dt.datetime(2026, 1, 1, 22, 0),
    )
    assert (allowed, reason) == (False, "no consent on record")

    consent.grant_consent(consent_path, "+1999", "test")
    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number="+1999", now=dt.datetime(2026, 1, 1, 22, 0),
    )
    assert (allowed, reason) == (False, "quiet hours")

    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number="+1999", now=dt.datetime(2026, 1, 1, 14, 0),
    )
    assert (allowed, reason) == (True, "allowed")
