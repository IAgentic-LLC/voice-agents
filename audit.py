"""Chapter 30: one clean-environment run through this book's whole
production checklist, reusing everything already built rather than
re-inventing a single piece of it.

    uv run audit.py

Every check here is real: a real subprocess, a real live call, or a
real fact read from this book's own already-recorded history.
Nothing is narrated without something underneath it.
"""

import asyncio
import contextlib
import io
import os
import subprocess
import sys
import tempfile

from caller import one_call
from gate_report import main as run_gate
from kill_mid_call import kill_worker
from voicelab import runlog
from voicelab.invariants import no_generic_error_reaches_the_caller

REGISTER_WAIT_S = 15.0


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def start_worker(script: str, agent_name: str, **env) -> subprocess.Popen:
    return subprocess.Popen(
        ["uv", "run", script, "start"],
        env={**os.environ, "AGENT_NAME": agent_name, **env},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def stop_worker(worker: subprocess.Popen) -> None:
    # Chapter 29's own finding: killing the `uv run` PID alone leaves
    # the real worker running. This kills the whole real tree.
    kill_worker(worker, "tree")
    try:
        worker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def check_build() -> tuple[bool, str]:
    result = sh(["uv", "run", "python", "-c", "import voicelab"])
    return result.returncode == 0, "voicelab imports cleanly"


def check_evaluate() -> tuple[bool, str]:
    result = sh(["uv", "run", "pytest", "-q"])
    last = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "no output"
    return result.returncode == 0, last


async def check_deploy_and_call() -> tuple[bool, str]:
    worker = start_worker("tools_agent.py", "audit30")
    try:
        await asyncio.sleep(REGISTER_WAIT_S)
        result = await one_call(
            1, "audit30", "runs/ch30-audit-call", "audio/ch09/plain.wav"
        )
    finally:
        stop_worker(worker)
    ok = result.get("ok", False)
    return ok, f"join {result.get('join_s')}s, ttfa {result.get('ttfa_s')}s"


async def check_interrupt() -> tuple[bool, str]:
    worker = start_worker("talker_agent.py", "audit30-talk")
    try:
        await asyncio.sleep(REGISTER_WAIT_S)
        result = await one_call(
            1, "audit30-talk", "runs/ch30-audit-interrupt",
            interrupt="audio/interruption.wav",
        )
    finally:
        stop_worker(worker)
    stop_s = result.get("stop_s")
    return stop_s is not None, f"stopped speaking {stop_s}s after being cut in on"


def check_handoff() -> tuple[bool, str]:
    rows = runlog.read("runs/ch21-fixed/stages.jsonl")
    handoffs = [r for r in rows if r.get("event") == "handoff requested"]
    ok = 0 < len(handoffs) <= 2
    return ok, f"{len(handoffs)} handoff(s) in runs/ch21-fixed, Chapter 21's fix"


def check_transfer() -> tuple[bool, str]:
    rows = runlog.read("runs/ch17-warm-transfer/stages.jsonl")
    result_row = next(
        (r for r in rows if r.get("stage") == "transfer"
        and r.get("event") == "result"), None
    )
    ok = bool(result_row and result_row["result"]["ok"])
    call_id = result_row["result"]["call_id"] if result_row else "none"
    return ok, f"ch17-warm-transfer: ok={ok}, call_id={call_id}"


async def check_break() -> tuple[bool, str]:
    worker = start_worker(
        "failure_agent.py", "audit30-fail", FAIL_MODE="plain"
    )
    try:
        await asyncio.sleep(REGISTER_WAIT_S)
        result = await one_call(
            1, "audit30-fail", "runs/ch30-audit-break",
            "audio/ch09/plain.wav", listen_s=20,
        )
    finally:
        stop_worker(worker)
    return result.get("ok", False), "a fresh plain exception, placed live, just now"


def check_detect(run: str = "runs/ch30-audit-break") -> tuple[bool, str]:
    hits = no_generic_error_reaches_the_caller(f"{run}/stages.jsonl")
    return len(hits) > 0, f"{len(hits)} generic error(s) caught in the fresh break"


def check_rollback() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        added = sh(["git", "worktree", "add", "--detach", tmp, "ch27-end"])
        if added.returncode != 0:
            return False, "could not check out ch27-end"
        try:
            result = sh(["uv", "run", "pytest", "-q"], cwd=tmp)
            last = (result.stdout.strip().splitlines()[-1]
                   if result.stdout.strip() else "no output")
            return result.returncode == 0, f"ch27-end's own suite: {last}"
        finally:
            sh(["git", "worktree", "remove", "--force", tmp])


def check_regression_case() -> tuple[bool, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_gate()
    out = buf.getvalue()
    lines = [l for l in out.splitlines() if "generic error" in l]
    return len(lines) >= 1, (lines[-1] if lines else "no line matched")


STEPS = [
    ("build", check_build),
    ("evaluate", check_evaluate),
    ("deploy + call", check_deploy_and_call),
    ("interrupt", check_interrupt),
    ("hand off", check_handoff),
    ("transfer", check_transfer),
    ("break", check_break),
    ("detect", check_detect),
    ("roll back", check_rollback),
    ("regression case", check_regression_case),
]


async def main() -> None:
    passed = 0
    for name, fn in STEPS:
        ok, detail = await fn() if asyncio.iscoroutinefunction(fn) else fn()
        passed += ok
        print(f"{'PASS' if ok else 'FAIL':<5} {name:<16} {detail}")
    print()
    print(f"{passed} of {len(STEPS)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
