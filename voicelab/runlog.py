"""Append-only JSON Lines records for one run.

The caller names the run directory and passes it to the agent in the
dispatch metadata, so the caller's trials and the agent's stage records
land side by side: runs/<name>/trials.jsonl and runs/<name>/stages.jsonl.
"""

import json
import time
from pathlib import Path


def append(path: str | Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"t": time.time(), **record}
    with path.open("a", encoding="utf8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def read(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
