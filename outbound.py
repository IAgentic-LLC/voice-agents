"""Chapter 15: an outbound call, with its own state, tracked as it happens.

    uv run outbound.py dial +49... --room ch15-... --run runs/mine-ch15
    uv run outbound.py report runs/ch15-*
    uv run outbound.py history
    uv run outbound.py history --to +254

`dial` places one real call through the LiveKit outbound trunk, passes
it through every guard in `voicelab.consent`, refuses to redial a
number the ledger already tried inside the retry window, and writes
every state transition to <run>/stages.jsonl as it happens: dialing,
each participant event, and the disconnect reason.

`report` reads back a run (or several) and prints the state machine
each call went through, with the timing between each stage.

The decision to place a call (`plan_call`) is a pure function with no
network in it, so it is unit-tested directly. Only `place_sip_call`,
the part that actually reaches LiveKit, needs a live server.

Needs LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and a SIP
outbound trunk id, all normally read from the environment set up in
deploy/oci.
"""

import asyncio
import datetime as dt
import os
import sys
import time
from dataclasses import dataclass

from voicelab import consent, ledger, runlog

TRUNK_ID = os.environ.get("SIP_OUTBOUND_TRUNK_ID", "")
DNC_PATH = os.environ.get("DNC_PATH", "runs/do-not-call.jsonl")
CONSENT_PATH = os.environ.get("CONSENT_PATH", "runs/consent.jsonl")
RETRY_WINDOW_S = float(os.environ.get("RETRY_WINDOW_S", "3600"))
MAX_CALLS_PER_WINDOW = int(os.environ.get("MAX_CALLS_PER_WINDOW", "1"))


@dataclass
class Plan:
    """What `plan_call` decided, and why. Never touches the network."""
    should_call: bool
    reason: str
    ledger_key: str


def plan_call(*, trials_path: str, number: str, now: dt.datetime,
              dnc_path: str = DNC_PATH, consent_path: str = CONSENT_PATH,
              window_s: float = RETRY_WINDOW_S,
              max_calls: int = MAX_CALLS_PER_WINDOW) -> Plan:
    """Decide whether to call, and compute the key that would guard it.

    Every check here is pure and reads only what is passed in, which
    is what makes it possible to test every branch, including the
    ones a real phone call would cost money to reach.
    """
    allowed, reason = consent.may_call(
        dnc_path=dnc_path, consent_path=consent_path, log_path=trials_path,
        number=number, now=now, window_s=window_s, max_calls=max_calls,
    )
    key = f"{number}:{int(now.timestamp() // window_s)}"
    if not allowed:
        return Plan(should_call=False, reason=reason, ledger_key=key)
    for row in runlog.read(trials_path):
        if row.get("key") == key:
            return Plan(should_call=False, reason="already attempted",
                       ledger_key=key)
    return Plan(should_call=True, reason="allowed", ledger_key=key)


async def watch_room(url: str, token: str, stages: str, room_name: str,
                     timeout_s: float, ready: asyncio.Event) -> None:
    """Record every state transition in the room as it happens.

    This is what turns "the call connected" into a state machine
    instead of a story told after reading logs by hand: each event
    below is a real callback, timestamped the moment it fires.
    """
    from livekit import rtc

    room = rtc.Room()
    done = asyncio.Event()

    def log(event: str, **fields) -> None:
        runlog.append(stages, {"stage": "call_state", "room": room_name,
                               "event": event, **fields})

    @room.on("participant_connected")
    def on_join(p) -> None:
        log("participant_joined", identity=p.identity)

    @room.on("track_subscribed")
    def on_track(track, pub, p) -> None:
        log("media_flowing", identity=p.identity, kind=str(track.kind))

    @room.on("participant_disconnected")
    def on_leave(p) -> None:
        log("participant_left", identity=p.identity,
            disconnect_reason=rtc.DisconnectReason.Name(
                p.disconnect_reason))
        done.set()

    @room.on("disconnected")
    def on_room_disconnect(reason) -> None:
        done.set()

    await room.connect(url, token)
    log("watching")
    ready.set()
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        log("watch_timeout")
    finally:
        await room.disconnect()


async def place_sip_call(number: str, room_name: str, stages: str,
                         wait_s: float = 30.0,
                         watch_timeout_s: float = 600.0) -> dict:
    """The one part of this file that needs a live LiveKit server.

    `wait_s` is how long to wait for the call to be answered, and is
    handed straight to `create_sip_participant`, which is what
    Chapter 15's own live test proved has to be separate from how
    long to keep watching afterward: a call answered comfortably
    inside `wait_s` still needs to be watched for its whole
    conversation, not just for `wait_s` from the start. The first
    version of this function used one clock for both, and its own
    watcher gave up 14 seconds before the real call ended, recording
    a fake timeout instead of the caller's real BYE.
    """
    from livekit import api
    from livekit.protocol import sip as sip_proto

    config = api.LiveKitAPI()
    identity = f"outbound-{int(time.time())}"
    token = (
        api.AccessToken()
        .with_identity("call-watcher")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    ready = asyncio.Event()
    watcher = asyncio.create_task(watch_room(
        os.environ["LIVEKIT_URL"], token, stages, room_name,
        watch_timeout_s, ready))
    await ready.wait()
    runlog.append(stages, {"stage": "call_state", "event": "dialing",
                           "number": number})
    try:
        info = await config.sip.create_sip_participant(
            sip_proto.CreateSIPParticipantRequest(
                sip_trunk_id=TRUNK_ID, sip_call_to=number,
                room_name=room_name, participant_identity=identity,
                wait_until_answered=True,
            ),
            timeout=wait_s,
        )
        return {"ok": True, "call_id": info.sip_call_id,
                "participant": info.participant_identity}
    except Exception as e:  # noqa: BLE001 - report, never hide
        return {"ok": False, "error": str(e)}
    finally:
        await watcher
        await config.aclose()


def dial(number: str, room_name: str, run_dir: str, *,
         force: bool = False, wait_s: float = 30.0,
         placer=place_sip_call, now: dt.datetime | None = None) -> dict:
    """Plan the call, then place it.

    `placer` and `now` are both swappable, for the same reason: a
    guard that can only be tested by controlling the real clock or
    reaching a real server is a guard that will not get tested. The
    first version of this function hardcoded `dt.datetime.now()`, so
    whether its own tests passed depended on what time of day the
    suite happened to run.
    """
    stages = f"{run_dir}/stages.jsonl"
    trials = f"{run_dir}/trials.jsonl"
    # Read DNC_PATH and CONSENT_PATH here, as live globals, rather than
    # letting plan_call fall back to its own default arguments. A
    # default value is bound once, at import time; if something
    # later points these constants elsewhere (a test, a config
    # reload), a default argument would never see the change, and
    # the guard would silently be checking the wrong files.
    plan = plan_call(trials_path=trials, number=number,
                     now=now or dt.datetime.now(), dnc_path=DNC_PATH,
                     consent_path=CONSENT_PATH, window_s=RETRY_WINDOW_S,
                     max_calls=MAX_CALLS_PER_WINDOW)

    if not plan.should_call and not force:
        runlog.append(stages, {"stage": "call_state", "event": "refused",
                               "number": number, "reason": plan.reason})
        # attempted: False. A refusal never reached the network, so
        # it must never count against this number's rate limit.
        runlog.append(trials, {"key": plan.ledger_key, "number": number,
                               "attempted": False, "ok": False,
                               "reason": plan.reason})
        return {"committed_now": False, "reason": plan.reason}

    runlog.append(stages, {"stage": "config", "number": number,
                           "trunk": TRUNK_ID, "room": room_name})
    result = asyncio.run(placer(number, room_name, stages, wait_s))
    runlog.append(trials, {"key": plan.ledger_key, "number": number,
                           "attempted": True, **result})
    return {"committed_now": True, **result}


def history(page_size: int = 10, to_prefix: str | None = None) -> None:
    """What Twilio's own record says about the most recent real calls.

    This is the carrier's account of events, not mine: it is what a
    reader with their own Twilio account can check independently of
    anything this book's own scripts claim. `to_prefix` filters to
    calls placed to one destination (a country code, or more of the
    number); it never hides a row silently, it is the difference
    between "here is everything" and "here is everything to +254".
    """
    import base64
    import json
    import urllib.request

    key = os.environ["TWILIO_API_KEY_SID"]
    secret = os.environ["TWILIO_API_KEY_SECRET"]
    account = os.environ["TWILIO_ACCOUNT_SID"]
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account}"
        f"/Calls.json?PageSize={page_size}",
        headers={"Authorization": f"Basic {auth}"},
    )
    data = json.loads(urllib.request.urlopen(req).read())
    calls = data["calls"]
    if to_prefix:
        calls = [c for c in calls if c["to"].startswith(to_prefix)]
    print(f"{'status':<12}{'duration':>10}  from -> to")
    for c in calls:
        to = c["to"][:5] + "X" * (len(c["to"]) - 5) if len(c["to"]) > 5 \
            else c["to"]
        print(f"{c['status']:<12}{c['duration'] + 's':>10}  "
              f"{c['from']} -> {to}")


def report(runs: list[str]) -> None:
    """The state machine each call went through, and the timing.

    `room` and `identity` label the whole call, not any one event in
    it, so they are printed once in the header instead of repeating
    on every row: a real call's `disconnect_reason` line is long
    enough on its own without the same room name and participant id
    it already carried three lines above.
    """
    for run in runs:
        rows = [r for r in runlog.read(f"{run}/stages.jsonl")
               if r.get("stage") == "call_state"]
        if not rows:
            continue
        header = f"== {run.split('/')[-1]}"
        constant = {k: r[k] for r in rows for k in ("room", "identity")
                   if k in r}
        if constant:
            header += "  (" + ", ".join(
                f"{k}={v}" for k, v in constant.items()) + ")"
        print(header)
        t0 = rows[0]["t"]
        for r in rows:
            extra = {k: v for k, v in r.items()
                    if k not in ("t", "stage", "event", "room", "identity")}
            extra_s = " ".join(f"{k}={v}" for k, v in extra.items())
            line = f"  {r['t'] - t0:+7.3f}s  {r['event']:<20}{extra_s}"
            print(line.rstrip())


if __name__ == "__main__":
    if sys.argv[1] == "dial":
        args = sys.argv[2:]
        run_dir = args[args.index("--run") + 1] if "--run" in args \
            else "runs/mine"
        room = args[args.index("--room") + 1] if "--room" in args \
            else f"outbound-{int(time.time())}"
        force = "--force" in args
        result = dial(args[0], room, run_dir, force=force)
        print(result)
    elif sys.argv[1] == "report":
        report(sys.argv[2:])
    elif sys.argv[1] == "history":
        args = sys.argv[2:]
        prefix = args[args.index("--to") + 1] if "--to" in args else None
        history(to_prefix=prefix)
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
