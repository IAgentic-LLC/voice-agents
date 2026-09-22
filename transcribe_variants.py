"""Chapter 2: can a speech model still understand each version of it?

    uv run transcribe_variants.py --repeats 5 --run runs/mine-transcripts
    uv run transcribe_variants.py --report runs/ch02-transcripts

Each version in audio/ch02/ is sent, as a WAV file, to the same Gemini model
the cascaded agent uses for transcription. The transcript is scored against
the words the caller really said. --report reads a recorded run and needs
no key.
"""

import argparse
import statistics
import time
from pathlib import Path

from google import genai
from google.genai import types

from voicelab import config, runlog
from voicelab.stats import wilson_interval
from voicelab.wer import word_error_rate

MODEL = "gemini-3.5-flash-lite"
PROMPT = "Transcribe this audio word for word. Output only the words."
SAID = (
    "Hi, I was charged twice for my last invoice. "
    "Can you tell me how a refund works?"
)
VERSIONS = [
    "audio/refund_question.wav",
    "audio/ch02/question-8k-resampled.wav",
    "audio/ch02/question-8k-naive.wav",
    "audio/ch02/question-8k-mulaw.wav",
    "audio/ch02/question-labelled-24k.wav",
    "audio/ch02/question-labelled-8k.wav",
]


def record(repeats: int, run_dir: str) -> None:
    client = genai.Client(api_key=config.gemini_key())
    for version in VERSIONS:
        audio = Path(version).read_bytes()
        for n in range(1, repeats + 1):
            started = time.monotonic()
            resp = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=audio, mime_type="audio/wav"),
                    PROMPT,
                ],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                ),
            )
            text = (resp.text or "").strip()
            rec = {
                "version": Path(version).name,
                "repeat": n,
                "model": MODEL,
                "text": text,
                "wer": round(word_error_rate(SAID, text), 4),
                "seconds": round(time.monotonic() - started, 3),
            }
            runlog.append(f"{run_dir}/transcripts.jsonl", rec)
            print(f"{rec['version']:<28} wer {rec['wer']:.2f}  {text}")


def report(run_dir: str) -> None:
    rows = runlog.read(f"{run_dir}/transcripts.jsonl")
    print(f"{'version':<28}{'tries':>6}{'perfect':>9}{'mean WER':>10}")
    for version in dict.fromkeys(r["version"] for r in rows):
        mine = [r for r in rows if r["version"] == version]
        perfect = sum(r["wer"] == 0 for r in mine)
        mean = statistics.mean(r["wer"] for r in mine)
        print(f"{version:<28}{len(mine):>6}{perfect:>9}{mean:>10.3f}")
    worst = max(rows, key=lambda r: r["wer"])
    low, high = wilson_interval(
        sum(r["wer"] == 0 for r in rows), len(rows)
    )
    print(f"perfect overall: {100 * low:.1f}% to {100 * high:.1f}% (95%)")
    print(f"worst ({worst['version']}, wer {worst['wer']:.2f}):")
    print(f"  {worst['text']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--run", help="where to record a new run")
    parser.add_argument("--report", help="summarize a recorded run")
    args = parser.parse_args()
    if args.report:
        report(args.report)
    else:
        record(args.repeats, args.run or "runs/mine-transcripts")
