"""Chapter 29: what happens to the calls already in flight when
several more land on the same worker at once.

    uv run load_test.py --agent tools --calls 5 --run runs/mine

Reuses caller.py's own `one_call` unchanged; the only difference
from `caller.py` itself is that every call starts at the same time,
via `asyncio.gather`, instead of one after another.
"""

import argparse
import asyncio
import json
import sys

from caller import one_call
from voicelab import runlog


async def run(agent: str, n: int, run_dir: str, question: str) -> list[dict]:
    return await asyncio.gather(*(
        one_call(i, agent, run_dir, question) for i in range(1, n + 1)
    ))


def main(agent: str, n: int, run_dir: str, question: str) -> None:
    results = asyncio.run(run(agent, n, run_dir, question))
    for result in results:
        print(json.dumps(result))
        runlog.append(f"{run_dir}/trials.jsonl", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True)
    parser.add_argument("--calls", type=int, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--question", default="audio/ch09/plain.wav")
    args = parser.parse_args()
    main(args.agent, args.calls, args.run, args.question)
