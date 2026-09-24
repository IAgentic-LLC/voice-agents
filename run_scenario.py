"""Chapter 23: run one named scenario from voicelab/scenarios.py
against a real agent, the same way any other chapter's caller.py
invocation would, with the scenario's own recording standing in for
a line written out by hand each time.

    uv run run_scenario.py wrong_identity --agent overpowered \
      --run runs/ch23-wrong-identity
    uv run run_scenario.py injection --agent overpowered \
      --run runs/ch23-injection

A scenario is a fixed set of arguments to caller.py's own one_call,
not a separate call path; whatever caller.py measures, a scenario
measures the same way.
"""

import argparse
import asyncio
import json

from caller import one_call
from voicelab import runlog
from voicelab.scenarios import SCENARIOS


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()

    s = SCENARIOS[args.scenario]
    result = await one_call(1, args.agent, args.run, s.question,
                            s.interrupt, s.after, s.listen_s)
    print(json.dumps(result))
    runlog.append(f"{args.run}/trials.jsonl", result)


if __name__ == "__main__":
    asyncio.run(main())
