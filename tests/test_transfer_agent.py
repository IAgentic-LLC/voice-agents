"""Chapter 17: the tool that stops itself from transferring twice.

`transfer_to_human`'s `FunctionTool` wrapper is directly callable
(bypassing the LLM), which is what lets these call the exact
function the model calls, and confirm the exact bug a real call
exposed: nothing made the agent leave after a successful transfer,
so a caller who kept talking got dialed to a human three times in
one call.
"""

import asyncio

import transfer_agent


class FakeSession:
    def __init__(self):
        self.said = []

    def say(self, text, **kwargs):
        self.said.append(text)

        class Done:
            def __await__(self):
                return iter(())

        return Done()


class FakeRunContext:
    def __init__(self, session):
        self.session = session


class FakeRoom:
    def __init__(self, name="room1"):
        self.name = name
        self.disconnected = False

    async def disconnect(self):
        self.disconnected = True


def test_transfer_tool_rejects_a_second_call_while_the_first_is_in_flight():
    tool = transfer_agent.make_tool(FakeRoom(), {"value": "caller1"},
                                    "runs/mine/stages.jsonl")
    assert tool.info.on_duplicate == "reject"
    assert tool.info.duplicate_scope == "name_and_args"


def test_a_successful_transfer_disconnects_the_agent_itself(monkeypatch):
    room = FakeRoom()
    session = FakeSession()

    async def fake_cold_transfer(room_name, identity, transfer_to):
        return {"ok": True, "status": "STS_TRANSFER_SUCCESSFUL"}

    monkeypatch.setattr(transfer_agent, "TRANSFER_MODE", "cold")
    monkeypatch.setattr(transfer_agent.transfer, "cold_transfer",
                        fake_cold_transfer)
    tool = transfer_agent.make_tool(room, {"value": "caller1"},
                                    "runs/mine/stages.jsonl")

    result = asyncio.run(tool(FakeRunContext(session)))

    assert room.disconnected is True
    assert session.said
    assert "disconnected" in result.lower()


def test_a_failed_transfer_leaves_the_agent_in_the_call(monkeypatch):
    room = FakeRoom()
    session = FakeSession()

    async def fake_cold_transfer(room_name, identity, transfer_to):
        return {"ok": False, "error": "no answer"}

    monkeypatch.setattr(transfer_agent, "TRANSFER_MODE", "cold")
    monkeypatch.setattr(transfer_agent.transfer, "cold_transfer",
                        fake_cold_transfer)
    tool = transfer_agent.make_tool(room, {"value": "caller1"},
                                    "runs/mine/stages.jsonl")

    result = asyncio.run(tool(FakeRunContext(session)))

    assert room.disconnected is False
    assert not session.said
    assert "did not go through" in result
