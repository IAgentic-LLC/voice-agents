"""Chapter 31: a version's tool names build the real tool objects
this book has used since Chapters 9 and 18, or refuse to.

Chapter 35: `room` is the real `rtc.Room` a factory acts on, not
just a name to log against, so these tests pass a fake with a real
`.name` attribute, the same fake `tests/test_transfer.py` already
uses for `warm_transfer` itself.
"""

import asyncio

import pytest

from voicelab import consent
from voicelab.tool_factory import TOOL_FACTORIES, build_tools, run_transfer_to_human


class FakeRoom:
    def __init__(self, name="room-1"):
        self.name = name


def test_every_known_tool_builds_a_real_function_tool(tmp_path):
    tools = build_tools(
        ["book_callback", "issue_refund"], str(tmp_path / "ledger.jsonl"),
        FakeRoom(), str(tmp_path / "stages.jsonl"),
    )
    assert len(tools) == 2
    assert {t.info.name for t in tools} == {"book_callback", "issue_refund"}


def test_an_empty_list_builds_no_tools(tmp_path):
    tools = build_tools(
        [], str(tmp_path / "ledger.jsonl"), FakeRoom(),
        str(tmp_path / "stages.jsonl"),
    )
    assert tools == []


def test_an_unknown_tool_name_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no such tool"):
        build_tools(
            ["book_callback", "delete_everything"],
            str(tmp_path / "ledger.jsonl"), FakeRoom(),
            str(tmp_path / "stages.jsonl"),
        )


def test_the_factory_registry_names_match_the_real_tool_they_build(
    tmp_path,
):
    for name, factory in TOOL_FACTORIES.items():
        tool = factory(
            str(tmp_path / "ledger.jsonl"), FakeRoom(),
            str(tmp_path / "stages.jsonl"),
        )
        assert tool.info.name == name


def test_transfer_refuses_with_no_destination_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("TRANSFER_TO_NUMBER", raising=False)
    result = asyncio.run(run_transfer_to_human(
        FakeRoom(), str(tmp_path / "stages.jsonl")))
    assert "not able to transfer" in result


def test_transfer_refuses_a_destination_with_no_consent_on_record(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("TRANSFER_TO_NUMBER", "+15550000000")
    monkeypatch.setenv("TRANSFER_CONSENT_PATH", str(tmp_path / "consent.jsonl"))
    monkeypatch.setenv("TRANSFER_DNC_PATH", str(tmp_path / "dnc.txt"))
    result = asyncio.run(run_transfer_to_human(
        FakeRoom(), str(tmp_path / "stages.jsonl")))
    assert "not able to transfer" in result


def test_transfer_refuses_a_number_on_the_do_not_call_list(tmp_path, monkeypatch):
    consent_path = str(tmp_path / "consent.jsonl")
    dnc_path = tmp_path / "dnc.txt"
    dnc_path.write_text("+15550000000\n", encoding="utf8")
    consent.grant_consent(consent_path, "+15550000000", "test")
    monkeypatch.setenv("TRANSFER_TO_NUMBER", "+15550000000")
    monkeypatch.setenv("TRANSFER_CONSENT_PATH", consent_path)
    monkeypatch.setenv("TRANSFER_DNC_PATH", str(dnc_path))
    result = asyncio.run(run_transfer_to_human(
        FakeRoom(), str(tmp_path / "stages.jsonl")))
    assert "not able to transfer" in result


def test_transfer_places_a_real_warm_transfer_once_consented(
    tmp_path, monkeypatch,
):
    consent_path = str(tmp_path / "consent.jsonl")
    consent.grant_consent(consent_path, "+15550000000", "test")
    monkeypatch.setenv("TRANSFER_TO_NUMBER", "+15550000000")
    monkeypatch.setenv("TRANSFER_CONSENT_PATH", consent_path)
    monkeypatch.setenv("TRANSFER_DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setenv("SIP_OUTBOUND_TRUNK_ID", "ST_trunk")

    async def fake_warm_transfer(room, target, trunk_id):
        assert target == "+15550000000"
        assert trunk_id == "ST_trunk"
        return {"ok": True, "identity": "human-1", "call_id": "SCL_test"}

    import voicelab.tool_factory as tf
    monkeypatch.setattr(tf.transfer, "warm_transfer", fake_warm_transfer)

    result = asyncio.run(run_transfer_to_human(
        FakeRoom(), str(tmp_path / "stages.jsonl")))
    assert "connected" in result.lower()


def test_transfer_reports_failure_when_the_human_never_joins(
    tmp_path, monkeypatch,
):
    consent_path = str(tmp_path / "consent.jsonl")
    consent.grant_consent(consent_path, "+15550000000", "test")
    monkeypatch.setenv("TRANSFER_TO_NUMBER", "+15550000000")
    monkeypatch.setenv("TRANSFER_CONSENT_PATH", consent_path)
    monkeypatch.setenv("TRANSFER_DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setenv("SIP_OUTBOUND_TRUNK_ID", "ST_trunk")

    async def fake_warm_transfer(room, target, trunk_id):
        return {"ok": False, "identity": "human-1", "call_id": "SCL_test"}

    import voicelab.tool_factory as tf
    monkeypatch.setattr(tf.transfer, "warm_transfer", fake_warm_transfer)

    result = asyncio.run(run_transfer_to_human(
        FakeRoom(), str(tmp_path / "stages.jsonl")))
    assert "couldn't reach" in result
