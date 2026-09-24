"""Chapter 17: a transfer read as data, not assumed from a lack of error.

`cold_transfer` and `warm_transfer` both take an injectable `client`
for the same reason `outbound.py`'s `place_sip_call` takes an
injectable `placer`: the one part that needs a live server is the
one part these tests never call.
"""

import asyncio

import pytest
from livekit import api

from voicelab import transfer


def test_a_successful_transfer_reads_as_ok():
    resp = api.TransferSIPParticipantResponse(
        transfer_id="ST_1",
        status=api.SIPTransferStatus.STS_TRANSFER_SUCCESSFUL,
        reason=api.SIPTransferReason.STR_COMPLETED,
        sip_status=api.SIPStatus(code=api.SIPStatusCode.SIP_STATUS_OK,
                                 status="OK"),
    )
    result = transfer.cold_result(resp)
    assert result == {"ok": True, "status": "STS_TRANSFER_SUCCESSFUL",
                      "reason": "STR_COMPLETED",
                      "sip_status_code": "SIP_STATUS_OK",
                      "sip_status_text": "OK"}


def test_a_ringing_timeout_reads_as_not_ok_even_with_no_exception():
    # The whole point of reading status instead of catching errors:
    # a ringing timeout raises nothing, and still isn't a transfer.
    resp = api.TransferSIPParticipantResponse(
        transfer_id="ST_2",
        status=api.SIPTransferStatus.STS_TRANSFER_FAILED,
        reason=api.SIPTransferReason.STR_RINGING_TIMEOUT,
        sip_status=api.SIPStatus(
            code=api.SIPStatusCode.SIP_STATUS_TEMPORARILY_UNAVAILABLE,
            status="Temporarily Unavailable"),
    )
    result = transfer.cold_result(resp)
    assert result["ok"] is False
    assert result["reason"] == "STR_RINGING_TIMEOUT"


class FakeSip:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def transfer_sip_participant(self, req, timeout=None):
        self.calls.append(req)
        if self.error:
            raise self.error
        return self.response

    async def create_sip_participant(self, req, timeout=None):
        self.calls.append(req)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, sip):
        self.sip = sip


def test_cold_transfer_reports_the_real_error_when_the_trunk_rejects_it():
    client = FakeClient(FakeSip(error=RuntimeError(
        "twirp error permission_denied: SIP transfers are not enabled")))
    result = asyncio.run(transfer.cold_transfer(
        "room1", "caller1", "tel:+15555550100", client=client))
    assert result["ok"] is False
    assert "not enabled" in result["error"]


class FakeRoom:
    def __init__(self):
        self.name = "room1"
        self._handlers = {}

    def on(self, event, handler):
        self._handlers[event] = handler

    def off(self, event, handler):
        self._handlers.pop(event, None)

    def fire_track_subscribed(self, identity):
        class P:
            pass
        p = P()
        p.identity = identity
        self._handlers["track_subscribed"](None, None, p)


class FakeSipInfo:
    sip_call_id = "SCL_test"


def test_warm_transfer_confirms_only_after_the_humans_own_track_arrives():
    room = FakeRoom()
    client = FakeClient(FakeSip(response=FakeSipInfo()))

    async def run():
        task = asyncio.create_task(transfer.warm_transfer(
            room, "tel:+15555550100", "ST_trunk", wait_s=1.0,
            client=client, identity="human-1"))
        await asyncio.sleep(0.05)
        room.fire_track_subscribed("human-1")
        return await task

    result = asyncio.run(run())
    assert result == {"ok": True, "identity": "human-1",
                      "call_id": "SCL_test"}


def test_warm_transfer_times_out_if_the_human_never_actually_joins():
    room = FakeRoom()
    client = FakeClient(FakeSip(response=FakeSipInfo()))
    result = asyncio.run(transfer.warm_transfer(
        room, "tel:+15555550100", "ST_trunk", wait_s=0.05,
        client=client, identity="human-2"))
    assert result["ok"] is False


def test_warm_transfer_strips_the_tel_prefix_before_dialing():
    # create_sip_participant wants a bare E.164 number; a real first
    # call sent it "tel:+254..." and got a real 400 back.
    room = FakeRoom()
    sip = FakeSip(response=FakeSipInfo())
    client = FakeClient(sip)

    async def run():
        task = asyncio.create_task(transfer.warm_transfer(
            room, "tel:+254756243672", "ST_trunk", wait_s=1.0,
            client=client, identity="human-4"))
        await asyncio.sleep(0.05)
        room.fire_track_subscribed("human-4")
        return await task

    asyncio.run(run())
    assert sip.calls[0].sip_call_to == "+254756243672"


def test_warm_transfer_reports_the_real_error_when_the_dial_itself_fails():
    room = FakeRoom()
    client = FakeClient(FakeSip(error=RuntimeError("no answer")))
    result = asyncio.run(transfer.warm_transfer(
        room, "tel:+15555550100", "ST_trunk", wait_s=0.1,
        client=client, identity="human-3"))
    assert result == {"ok": False, "error": "no answer"}
