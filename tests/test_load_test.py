"""Chapter 29: load_test.py places its calls concurrently, not one
after another, and writes every result the same way caller.py does."""

import asyncio

import load_test


def test_run_places_every_call_at_the_same_time(monkeypatch, tmp_path):
    started = []

    async def fake_one_call(number, agent, run_dir, question):
        started.append((number, asyncio.get_running_loop().time()))
        await asyncio.sleep(0.05)
        return {"call": number, "agent": agent, "ok": True}

    monkeypatch.setattr(load_test, "one_call", fake_one_call)

    results = asyncio.run(load_test.run("a", 4, str(tmp_path), "q.wav"))

    assert len(results) == 4
    assert {r["call"] for r in results} == {1, 2, 3, 4}
    spread = max(t for _, t in started) - min(t for _, t in started)
    assert spread < 0.05


def test_main_writes_every_result_to_trials(monkeypatch, tmp_path):
    async def fake_one_call(number, agent, run_dir, question):
        return {"call": number, "agent": agent, "ok": True}

    monkeypatch.setattr(load_test, "one_call", fake_one_call)

    load_test.main("a", 3, str(tmp_path), "q.wav")

    from voicelab import runlog
    rows = runlog.read(tmp_path / "trials.jsonl")
    assert len(rows) == 3
