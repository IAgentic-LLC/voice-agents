"""Chapter 15: the checks an outbound call has to pass before it dials.

An inbound call is invited: the caller chose to reach you. An outbound
call is not. Every one of these checks exists because "the code could
place the call" is not the same question as "the code should place the
call", and the difference is the caller's, not the machine's, to have
agreed to.

Every function here is pure: given the same inputs, the same answer,
every time, with no clock reached for except through the argument you
pass in. That is deliberate. A guard you cannot unit-test without
placing a real call is a guard you will not test.
"""

import datetime as dt
from pathlib import Path

from voicelab import runlog


def on_do_not_call_list(dnc_path: str, number: str) -> bool:
    """A number that asked, once, never to be called again.

    The file is one number per line. There is no expiry, no per-call
    override, and no code path that calls a listed number anyway.
    """
    path = Path(dnc_path)
    if not path.exists():
        return False
    listed = {line.strip() for line in path.read_text(encoding="utf8")
             .splitlines() if line.strip()}
    return number in listed


def has_consent(consent_path: str, number: str) -> bool:
    """Has this number ever agreed to be called for this purpose?

    Consent is a record, the same shape as Chapter 12's memory store:
    written once when it is given, read every time before a call. No
    consent record means no call, which is the safer of the two ways
    to be wrong about it.
    """
    for row in runlog.read(consent_path):
        if row.get("number") == number and row.get("granted"):
            return True
    return False


def grant_consent(consent_path: str, number: str, reason: str) -> None:
    runlog.append(consent_path, {
        "number": number, "granted": True, "reason": reason,
    })


def in_quiet_hours(now: dt.datetime, start_hour: int = 21,
                   end_hour: int = 8) -> bool:
    """Is it too late, or too early, in the callee's own timezone?

    `now` must already be in that timezone; this function does not
    guess one. The window wraps midnight, because most quiet hours do:
    21 to 8 means quiet from 9pm through to 8am the next morning.
    """
    hour = now.hour
    if start_hour > end_hour:  # wraps midnight
        return hour >= start_hour or hour < end_hour
    return start_hour <= hour < end_hour


def rate_limited(log_path: str, number: str, window_s: float,
                 max_calls: int, now: float) -> bool:
    """Have we already CALLED this number too many times, too recently?

    Every dial attempt is logged, but not every logged row is a call:
    a row can also be a refusal, from this same set of guards, before
    anything ever reached the network. Counting a refusal against the
    rate limit would mean a number nobody has actually called yet can
    still lock itself out, which is backwards, so only rows with
    `attempted: True` count.

    Only rows strictly in the past count too. A row with `t` after
    `now`, from clock skew between processes or a test that froze
    `now` without also freezing the write, must not silently count as
    recent just because the difference happens to be negative.
    """
    recent = [row for row in runlog.read(log_path)
             if row.get("number") == number and row.get("attempted")
             and 0 <= now - row["t"] < window_s]
    return len(recent) >= max_calls


def may_call(*, dnc_path: str, consent_path: str, log_path: str,
             number: str, now: dt.datetime, quiet_start: int = 21,
             quiet_end: int = 8, window_s: float = 3600,
             max_calls: int = 1) -> tuple[bool, str]:
    """Every guard, in the order that matters most.

    Returns (allowed, reason). The reason is always present, whether
    the call is allowed or not, so a caller can log why.
    """
    if on_do_not_call_list(dnc_path, number):
        return False, "on the do-not-call list"
    if not has_consent(consent_path, number):
        return False, "no consent on record"
    if in_quiet_hours(now, quiet_start, quiet_end):
        return False, "quiet hours"
    if rate_limited(log_path, number, window_s, max_calls, now.timestamp()):
        return False, "rate limited"
    return True, "allowed"
