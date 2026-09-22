"""Chapter 8: cascaded against realtime, on the same five tasks.

    uv run compare.py runs/ch08-cascaded runs/ch08-realtime
    uv run compare.py --answers runs/ch08-realtime
    uv run compare.py --bill runs/ch08-cascaded

Reports, for each run, how many tasks were answered correctly, the median
time to first audio, and what the call cost in the tokens the agent
counted. --answers prints every answer so the scoring can be read rather
than trusted. --bill shows which stages the counters price and which they
do not. Needs no key.
"""

import statistics
import sys

from report import summarize
from voicelab import runlog
from voicelab.policy import task_of

# Google's list prices, dollars per million tokens, from the Gemini API
# pricing page at the time of writing. Prices change; this is the only
# place in the repository that holds them.
PRICES = {
    "gemini-3.8-live": {
        "input_text_tokens": 0.75, "input_audio_tokens": 3.00,
        "output_text_tokens": 4.50, "output_audio_tokens": 12.00,
    },
    "gemini-3.5-flash-lite": {
        # One input price covers text, image, video and audio.
        "input_tokens": 0.30, "output_tokens": 2.50,
    },
    "gemini-2.5-flash-preview-tts": {
        "input_tokens": 0.50, "output_tokens": 10.00,
    },
}


def usage_of(run: str) -> list[list[dict]]:
    return [u["models"] for u in runlog.read(f"{run}/stages.jsonl")
            if u["stage"] == "usage"]


def stages_of(run: str) -> list[str]:
    """The services a call in this run used, from what the agent logged.

    A cascaded call has three and reports two: the transcriber does not
    appear in the usage record at all.
    """
    for row in runlog.read(f"{run}/stages.jsonl"):
        if row["stage"] == "config":
            named = [row[k] for k in ("stt", "llm", "tts", "model")
                     if row.get(k)]
            if named:
                return named
    return []


def priced(models: list[dict]) -> tuple[float, list[str]]:
    """What one call cost, and the stages whose price could not be found.

    A stage is unpriced when its plugin reports no tokens. The speech
    plugins report seconds of audio and a character count instead, and
    Google bills them by the token, so their part of the bill cannot be
    worked out from what the agent counted.
    """
    total, missing = 0.0, []
    for one in models:
        model = one.get("model", "?")
        prices = PRICES.get(model, {})
        counted = sum(one.get(field, 0) or 0 for field in prices)
        if not counted:
            missing.append(model)
            continue
        for field, price in prices.items():
            total += (one.get(field, 0) or 0) * price / 1_000_000
    return total, missing


def answers(run: str) -> list[tuple[str, str, bool]]:
    """(task, what the agent said, whether it was right) for each call."""
    traces = [s for s in runlog.read(f"{run}/stages.jsonl")
              if s["stage"] == "trace"]
    out = []
    for call in runlog.read(f"{run}/trials.jsonl"):
        task = task_of(call.get("question", ""))
        if task is None:
            continue
        said = [t["text"] for t in traces
                if t["room"] == call["room"]
                and t["event"] == "assistant said"]
        answer = " ".join(said)
        out.append((task.name, answer, task.passed(answer)))
    return out


def main(runs: list[str]) -> None:
    print(f"{'run':<18}{'calls':>6}{'right':>9}{'wait, median':>14}"
          f"{'counted cost':>14}{'unpriced':>12}")
    for run in runs:
        scored = answers(run)
        right = sum(ok for _, _, ok in scored)
        waits = summarize(run)["ttfa"]
        costs, worked = [], set()
        for models in usage_of(run):
            money, missing = priced(models)
            costs.append(money)
            worked.update(m["model"] for m in models
                          if m["model"] not in missing)
        stages = stages_of(run)
        unpriced = [s for s in stages if s not in worked]
        wait = f"{statistics.median(waits):.3f} s" if waits else "-"
        cost = f"${statistics.median(costs):.5f}" if costs else "-"
        print(f"{run.split('/')[-1]:<18}{len(scored):>6}"
              f"{right:>6} of {len(scored)}{wait:>14}{cost:>14}"
              f"{len(unpriced):>7} of {len(stages)}")


def show(run: str) -> None:
    for task, answer, ok in answers(run):
        mark = "right" if ok else "WRONG"
        print(f"[{mark}] {task}: {answer or '(nothing was said)'}")


def bill(run: str) -> None:
    """Every stage of the run's first call, and whether it can be priced.

    The first call, not the median one: a run's cheapest and dearest
    calls differ, and this is here to show which fields exist.
    """
    named = stages_of(run)
    models = usage_of(run)[0]
    for missing in [s for s in named
                    if s not in {m["model"] for m in models}]:
        print(f"{missing:<30}{'not reported':>14}  {{}}")
    for one in models:
        model = one.get("model", "?")
        prices = PRICES.get(model, {})
        counted = {field: one.get(field, 0) for field in prices
                   if one.get(field, 0)}
        if counted:
            money = sum(one[f] * prices[f] for f in counted) / 1_000_000
            print(f"{model:<30}{money:>14.5f}  {counted}")
        else:
            other = {k: round(v, 2) if isinstance(v, float) else v
                     for k, v in one.items()
                     if isinstance(v, (int, float)) and v}
            print(f"{model:<30}{'no tokens':>14}  {other}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--answers"]:
        show(sys.argv[2])
    elif sys.argv[1:2] == ["--bill"]:
        bill(sys.argv[2])
    else:
        main(sys.argv[1:])
