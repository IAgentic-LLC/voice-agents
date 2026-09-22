"""Pin the Chapter 12 results, and the guard the runs never tripped."""

from kept import knew_at, said_in
from voicelab import memory, runlog


def calls_of(run):
    return runlog.read(f"runs/{run}/trials.jsonl")


def traced(run, event):
    return [r for r in runlog.read(f"runs/{run}/stages.jsonl")
            if r.get("stage") == "trace" and r["event"] == event]


def test_a_dropped_connection_ends_the_conversation():
    """Nothing the caller said after rejoining was ever heard."""
    call = calls_of("ch12-drop")[0]
    after = [r for r in traced("ch12-drop", "user said")
             if r["at"] > call["rejoined_wall"]]
    assert after == []
    assert len(knew_at("runs/ch12-drop")) == 1  # one session, then gone


def test_holding_the_session_open_keeps_the_history():
    call = calls_of("ch12-hold")[0]
    after = [r for r in traced("ch12-hold", "assistant said")
             if r["at"] > call["rejoined_wall"]]
    assert after, "the agent answered after the caller came back"
    assert "already" in after[0]["text"].lower()


def test_two_calls_without_a_store_are_two_strangers():
    knew = knew_at("runs/ch12-calls-off")
    assert len(knew) == 2
    assert all("no record" in line for line in knew)


def test_a_store_makes_the_second_call_different():
    knew = knew_at("runs/ch12-calls-on")
    assert len(knew) == 2
    assert "not spoken to this caller before" in knew[0]
    assert "callback_day is Thursday" in knew[1]
    said = said_in("runs/ch12-calls-on",
                   calls_of("ch12-calls-on")[1]["room"])
    assert "already know" in said.lower()


def test_the_card_number_never_reached_the_store():
    kept = memory.recall("runs/ch12-store/memory.jsonl", "caller")
    assert set(kept) == {"callback_day", "callback_time"}
    assert kept["callback_day"] == "Thursday"
    # and the agent said why
    said = said_in("runs/ch12-card", calls_of("ch12-card")[0]["room"])
    assert "cannot" in said.lower() and "card" in said.lower()


def test_the_store_refuses_anything_not_on_the_list(tmp_path):
    """The guard the model never made us use."""
    path = str(tmp_path / "memory.jsonl")
    answer = memory.remember(path, "caller", "card_number", "4551 2345")
    assert "not allowed" in answer
    assert memory.recall(path, "caller") == {}


def test_the_store_keeps_the_latest_value_of_each_fact(tmp_path):
    path = str(tmp_path / "memory.jsonl")
    memory.remember(path, "caller", "callback_day", "Thursday")
    memory.remember(path, "caller", "callback_day", "Friday")
    assert memory.recall(path, "caller") == {"callback_day": "Friday"}


def test_one_caller_cannot_read_another(tmp_path):
    path = str(tmp_path / "memory.jsonl")
    memory.remember(path, "alice", "name", "Alice")
    assert memory.recall(path, "bob") == {}
    assert "not spoken" in memory.describe(path, "bob")
