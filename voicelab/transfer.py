"""Chapter 17: a transfer that knows whether it actually happened.

Two shapes, both real. `cold_transfer` hands the caller to another
number with a SIP REFER and leaves; the LiveKit room closes under
the agent the moment the carrier accepts it. `warm_transfer` dials a
human into the same room the caller is already in, waits for a real
media event proving they are actually there, and only then lets the
agent disconnect.

Both return the outcome as data, never as an assumption. LiveKit's
own SDK docstring for the underlying call says it plainly: "a status
other than successful means the transfer did not complete, even
when no error was raised." A caller told "you're being transferred"
by a model that never checked is a caller lied to by accident.
"""

import asyncio

from livekit import api, rtc


def cold_result(resp: "api.TransferSIPParticipantResponse") -> dict:
    """Read a transfer response the way this chapter insists on: the
    status field decides, not whether an exception was raised."""
    return {
        "ok": resp.status == api.SIPTransferStatus.STS_TRANSFER_SUCCESSFUL,
        "status": api.SIPTransferStatus.Name(resp.status),
        "reason": api.SIPTransferReason.Name(resp.reason),
        "sip_status_code": api.SIPStatusCode.Name(resp.sip_status.code),
        "sip_status_text": resp.sip_status.status,
    }


async def cold_transfer(room_name: str, participant_identity: str,
                        transfer_to: str, *,
                        ringing_timeout: float = 30.0,
                        client=None) -> dict:
    """SIP REFER the caller to `transfer_to`. Requires the trunk's own
    transfer setting to be enabled; if it is not, this fails with a
    real error rather than a silent no-op."""
    lk = client or api.LiveKitAPI()
    try:
        req = api.TransferSIPParticipantRequest(
            room_name=room_name,
            participant_identity=participant_identity,
            transfer_to=transfer_to,
        )
        # ringing_timeout is a protobuf Duration, set as a sub-field,
        # not a constructor keyword (that raises: "expected a
        # timedelta object got float", found by this module's own
        # tests, not by reading the .proto by hand).
        req.ringing_timeout.seconds = int(ringing_timeout)
        resp = await lk.sip.transfer_sip_participant(req)
        return cold_result(resp)
    except Exception as e:  # noqa: BLE001 - report, never hide
        return {"ok": False, "error": str(e)}
    finally:
        if client is None:
            await lk.aclose()


async def warm_transfer(room, transfer_to: str, trunk_id: str, *,
                        wait_s: float = 30.0, client=None,
                        identity: str | None = None) -> dict:
    """Dial a human into `room` (the caller's own LiveKit room, not a
    separate consultation room: MoveParticipant, the officially
    documented way to bridge a consultation room into the caller's,
    only works on LiveKit Cloud, and this server is self-hosted).
    Returns once the human's audio track is confirmed subscribed, or
    once `wait_s` elapses without it, so the agent never disconnects
    on the strength of a dial alone."""
    lk = client or api.LiveKitAPI()
    joined = asyncio.Event()
    identity = identity or f"warm-transfer-{int(asyncio.get_event_loop().time() * 1000)}"
    # create_sip_participant's sip_call_to wants a bare E.164 number,
    # the same way outbound.py's place_sip_call calls it in Chapter
    # 15. transfer_sip_participant's transfer_to wants a "tel:" URI
    # instead. Both this function's callers pass the same
    # TRANSFER_TO value for either mode, so this is the one place
    # that strips the prefix the other API needs and this one does
    # not: a real 400 ("The called number is not correctly
    # formatted") on the first live call this chapter placed, not a
    # guess from reading two API references side by side.
    bare_number = transfer_to.removeprefix("tel:")

    def on_track(track, pub, participant: rtc.RemoteParticipant) -> None:
        if participant.identity == identity:
            joined.set()

    room.on("track_subscribed", on_track)
    try:
        info = await lk.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id, sip_call_to=bare_number,
                room_name=room.name, participant_identity=identity,
                wait_until_answered=True,
            ),
            timeout=wait_s,
        )
    except Exception as e:  # noqa: BLE001 - report, never hide
        room.off("track_subscribed", on_track)
        if client is None:
            await lk.aclose()
        return {"ok": False, "error": str(e)}
    if client is None:
        await lk.aclose()
    try:
        await asyncio.wait_for(joined.wait(), timeout=wait_s)
        confirmed = True
    except asyncio.TimeoutError:
        confirmed = False
    room.off("track_subscribed", on_track)
    return {"ok": confirmed, "identity": identity,
            "call_id": info.sip_call_id}
