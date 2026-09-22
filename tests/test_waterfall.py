"""Pin the Chapter 4 waterfalls."""

import statistics

from voicelab import runlog
from waterfall import call_events


def medians(run):
    calls = [c for c in runlog.read(f"runs/{run}/trials.jsonl") if c["ok"]]
    traces = [s for s in runlog.read(f"runs/{run}/stages.jsonl")
              if s["stage"] == "trace"]
    per_call = [call_events(c, traces) for c in calls]
    names = {n for p in per_call for n in p}
    return {n: statistics.median(p[n] for p in per_call if n in p)
            for n in names}


def test_cascaded_waterfall_in_order():
    m = medians("ch04-cascaded")
    order = ["user listening known", "final transcript", "agent thinking",
             "first token", "first speech byte", "agent speaking",
             "caller gets sound", "caller hears"]
    times = [m[n] for n in order]
    assert times == sorted(times)
    assert round(m["caller hears"], 3) == 7.267


def test_the_voice_is_the_largest_stage():
    from waterfall import stage_lengths
    calls = [c for c in runlog.read("runs/ch04-cascaded/trials.jsonl")]
    traces = [s for s in runlog.read("runs/ch04-cascaded/stages.jsonl")
              if s["stage"] == "trace"]
    stages = [stage_lengths(call_events(c, traces)) for c in calls]
    voice = statistics.median(s["first sentence voiced"] for s in stages)
    model = statistics.median(s["model's first token"] for s in stages)
    assert round(voice, 3) == 3.007 and round(model, 3) == 0.752


def test_realtime_hides_its_stages():
    m = medians("ch04-realtime")
    assert "first token" not in m
    assert m["user listening"] > m["caller hears"]  # learned afterwards
