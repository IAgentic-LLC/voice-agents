"""Chapter 15: the decision to dial, and the retry it guards against.

`plan_call` and `dial`'s guard path never touch the network, so every
one of these runs free and fast. `dial` itself takes a `placer`
argument precisely so a test can stand in for the one part that
actually needs a live server.
"""

import datetime as dt

from voicelab import consent

import outbound


def setup(tmp_path, number="+15550001234"):
    dnc_path = str(tmp_path / "dnc.txt")
    consent_path = str(tmp_path / "consent.jsonl")
    trials_path = str(tmp_path / "trials.jsonl")
    consent.grant_consent(consent_path, number, "test setup")
    return dnc_path, consent_path, trials_path


def test_a_fresh_number_is_planned_to_call(tmp_path):
    dnc_path, consent_path, trials_path = setup(tmp_path)
    plan = outbound.plan_call(
        trials_path=trials_path, number="+15550001234",
        now=dt.datetime(2026, 1, 1, 14, 0),
        dnc_path=dnc_path, consent_path=consent_path,
    )
    assert plan.should_call is True
    assert plan.reason == "allowed"


def test_the_same_number_in_the_same_window_is_not_replanned(tmp_path):
    dnc_path, consent_path, trials_path = setup(tmp_path)
    now = dt.datetime(2026, 1, 1, 14, 0)
    plan = outbound.plan_call(
        trials_path=trials_path, number="+15550001234", now=now,
        dnc_path=dnc_path, consent_path=consent_path, window_s=3600,
    )
    from voicelab import runlog
    runlog.append(trials_path, {"key": plan.ledger_key,
                                "number": "+15550001234"})

    replanned = outbound.plan_call(
        trials_path=trials_path, number="+15550001234", now=now,
        dnc_path=dnc_path, consent_path=consent_path, window_s=3600,
    )
    assert replanned.should_call is False
    assert replanned.reason == "already attempted"


def test_a_new_window_allows_a_real_retry(tmp_path):
    dnc_path, consent_path, trials_path = setup(tmp_path)
    first = dt.datetime(2026, 1, 1, 14, 0)
    later = dt.datetime(2026, 1, 1, 18, 0)  # more than one hour later
    plan = outbound.plan_call(
        trials_path=trials_path, number="+15550001234", now=first,
        dnc_path=dnc_path, consent_path=consent_path, window_s=3600,
    )
    from voicelab import runlog
    runlog.append(trials_path, {"key": plan.ledger_key,
                                "number": "+15550001234"})

    retry_plan = outbound.plan_call(
        trials_path=trials_path, number="+15550001234", now=later,
        dnc_path=dnc_path, consent_path=consent_path, window_s=3600,
    )
    assert retry_plan.should_call is True
    assert retry_plan.ledger_key != plan.ledger_key


def test_dial_never_calls_the_placer_when_refused(tmp_path):
    """The guard has to run BEFORE the network call, not alongside it.
    This is the test that would fail if someone moved the consent
    check after the dial by mistake."""
    trials_path = str(tmp_path / "run" / "trials.jsonl")
    called = []

    async def fake_placer(number, room, stages, wait_s):
        called.append(number)
        return {"ok": True}

    result = outbound.dial(
        "+15550009999", "test-room", str(tmp_path / "run"),
        placer=fake_placer,
    )
    assert result["committed_now"] is False
    assert called == [], "the placer ran despite no consent on record"


def test_dial_calls_the_placer_exactly_once_when_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(outbound, "DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setattr(outbound, "CONSENT_PATH",
                        str(tmp_path / "consent.jsonl"))
    consent.grant_consent(str(tmp_path / "consent.jsonl"),
                          "+15550001234", "test")
    called = []

    async def fake_placer(number, room, stages, wait_s):
        called.append(number)
        return {"ok": True, "call_id": "SCL_fake"}

    result = outbound.dial(
        "+15550001234", "test-room", str(tmp_path / "run"),
        placer=fake_placer, now=dt.datetime(2026, 1, 1, 14, 0),
    )
    assert result == {"committed_now": True, "ok": True,
                      "call_id": "SCL_fake"}
    assert called == ["+15550001234"]


def test_dial_does_not_depend_on_the_real_wall_clock(tmp_path, monkeypatch):
    """The first version of `dial` called `dt.datetime.now()` directly,
    with no way for a test to control it, so whether this suite passed
    depended on what time of day it happened to run: outside quiet
    hours in the morning, refused after 9pm. `now` has to be
    injectable for the same reason `placer` is."""
    monkeypatch.setattr(outbound, "DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setattr(outbound, "CONSENT_PATH",
                        str(tmp_path / "consent.jsonl"))
    consent.grant_consent(str(tmp_path / "consent.jsonl"),
                          "+15550001234", "test")
    called = []

    async def fake_placer(number, room, stages, wait_s):
        called.append(number)
        return {"ok": True}

    late_at_night = dt.datetime(2026, 1, 1, 23, 0)
    result = outbound.dial(
        "+15550001234", "test-room", str(tmp_path / "run"),
        placer=fake_placer, now=late_at_night,
    )
    assert result == {"committed_now": False, "reason": "quiet hours"}
    assert called == [], "an 11pm call was placed anyway"


def test_watching_a_call_outlives_waiting_for_it_to_answer():
    """Chapter 15's own live test found this the hard way: a real call
    answered comfortably inside a 30 second wait still needed 44
    seconds of watching before the caller hung up, and the first
    version of place_sip_call used one 30 second clock for both, so
    its own watcher stopped 14 seconds before the real BYE. The
    default watch window has to outlast the default answer wait by a
    wide margin, not match it."""
    import inspect

    sig = inspect.signature(outbound.place_sip_call)
    wait_default = sig.parameters["wait_s"].default
    watch_default = sig.parameters["watch_timeout_s"].default
    assert watch_default > wait_default * 5


def test_dial_uses_the_current_dnc_and_consent_paths(tmp_path, monkeypatch):
    """A default argument is bound once, at import time. If `dial`
    relied on `plan_call`'s own defaults for DNC_PATH/CONSENT_PATH
    instead of reading the live globals, changing them after import
    (here, with monkeypatch; in production, a config reload) would
    have no effect, and the guard would keep checking the original
    files forever. This test failed against the first version of
    `dial`, which is why it exists."""
    monkeypatch.setattr(outbound, "DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setattr(outbound, "CONSENT_PATH",
                        str(tmp_path / "moved-consent.jsonl"))
    consent.grant_consent(str(tmp_path / "moved-consent.jsonl"),
                          "+15550001234", "test")
    called = []

    async def fake_placer(number, room, stages, wait_s):
        called.append(number)
        return {"ok": True}

    result = outbound.dial("+15550001234", "test-room",
                           str(tmp_path / "run"), placer=fake_placer,
                           now=dt.datetime(2026, 1, 1, 14, 0))
    assert called == ["+15550001234"]
    assert result["committed_now"] is True


def test_a_retry_inside_the_window_does_not_redial(tmp_path, monkeypatch):
    """The idempotency test that Chapter 9 could not run for real: two
    dial attempts for the same number inside the same window, and the
    second one must never reach the placer."""
    monkeypatch.setattr(outbound, "DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setattr(outbound, "CONSENT_PATH",
                        str(tmp_path / "consent.jsonl"))
    consent.grant_consent(str(tmp_path / "consent.jsonl"),
                          "+15550001234", "test")
    called = []

    async def fake_placer(number, room, stages, wait_s):
        called.append(number)
        return {"ok": True, "call_id": "SCL_fake"}

    run_dir = str(tmp_path / "run")
    fixed_now = dt.datetime(2026, 1, 1, 14, 0)
    outbound.dial("+15550001234", "test-room", run_dir, placer=fake_placer,
                  now=fixed_now)
    second = outbound.dial("+15550001234", "test-room", run_dir,
                           placer=fake_placer, now=fixed_now)

    assert second["committed_now"] is False
    assert called == ["+15550001234"], "the second attempt redialled"
