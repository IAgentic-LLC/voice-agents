"""Summarize one or more runs: answered calls, TTFA, and where the time went.

    uv run report.py runs/ch01-realtime runs/ch01-cascaded-split

Needs no key and no server: it only reads the JSON Lines files in each run.
"""

import statistics
import sys
import textwrap
from collections import Counter

from voicelab import runlog
from voicelab.stats import bootstrap_median_interval, wilson_interval


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def summarize(run_dir: str) -> dict:
    trials = runlog.read(f"{run_dir}/trials.jsonl")
    stages = runlog.read(f"{run_dir}/stages.jsonl")
    joined = [t for t in trials if "join_s" in t]
    answered = [t for t in joined if t["ok"]]
    ttfa = sorted(t["ttfa_s"] for t in answered)
    low, high = wilson_interval(len(answered), len(joined))
    out = {
        "run": run_dir,
        "calls": len(trials),
        "joined": len(joined),
        "answered": len(answered),
        "answered_interval": (low, high),
        "ttfa": ttfa,
        "turns": Counter(),
    }
    if ttfa:
        out["ttfa_median"] = statistics.median(ttfa)
        out["ttfa_interval"] = bootstrap_median_interval(ttfa)
    metrics = [s["metrics"] for s in stages if s["stage"] == "metrics"]

    def median_of(kind: str, field: str) -> float | None:
        # A cancelled request (the caller hung up first) logs -1; skip it.
        vals = [
            m[field] for m in metrics
            if m["type"] == kind and not m.get("cancelled") and m[field] >= 0
        ]
        return statistics.median(vals) if vals else None

    out["stt_s"] = statistics.median(
        [s["stt_s"] for s in stages if s["stage"] == "stt"] or [0]
    ) or None
    out["end_of_turn_s"] = median_of("eou_metrics", "end_of_utterance_delay")
    out["first_token_s"] = median_of("llm_metrics", "ttft")
    out["speech_first_byte_s"] = median_of("tts_metrics", "ttfb")
    out["model_calls"] = sum(m["type"] == "llm_metrics" for m in metrics)
    out["transcripts"] = Counter(
        s["text"] for s in stages if s["stage"] == "stt"
    )
    return out


def print_summary(s: dict) -> None:
    low, high = s["answered_interval"]
    print()
    print(f"== {s['run']}")
    print(f"calls {s['calls']}, agent joined {s['joined']}")
    print(f"answered {s['answered']} of {s['joined']} "
          f"(95% interval {pct(low)} to {pct(high)})")
    if s["ttfa"]:
        lo, hi = s["ttfa_interval"]
        print(f"time to first audio, median {s['ttfa_median']:.3f} s "
              f"(95% interval {lo:.3f} to {hi:.3f} s)")
        fastest, slowest = s["ttfa"][0], s["ttfa"][-1]
        print(f"  fastest {fastest:.3f} s, slowest {slowest:.3f} s")
    for label, key in [
        ("transcription (batch)", "stt_s"),
        ("model first token", "first_token_s"),
        ("speech first byte", "speech_first_byte_s"),
    ]:
        if s.get(key) is not None:
            print(f"  {label:<24}{s[key]:.3f} s median")
    if s["model_calls"]:
        print(f"model calls: {s['model_calls']} in {s['joined']} calls")
    for text, count in s["transcripts"].most_common():
        print(f"heard {count} times:")
        print(textwrap.fill(text, width=74, initial_indent="  ",
                            subsequent_indent="  "))


if __name__ == "__main__":
    for run in sys.argv[1:]:
        print_summary(summarize(run))
