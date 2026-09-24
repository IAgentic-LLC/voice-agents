"""Chapter 30: the audit's own logic, checked against constructed
data and mocked subprocesses; the real audit run itself, against
real workers and a real worktree, is what the chapter quotes.

`check_detect` and `check_regression_case` are tested against a
constructed run, never against the real `runs/ch30-audit-break`,
so these tests can never write synthetic evidence into the same
directory this chapter's real live call is the evidence for."""

import asyncio
import subprocess

import audit
from voicelab import runlog


def test_check_build_reads_the_real_subprocess_result(monkeypatch):
    monkeypatch.setattr(audit, "sh", lambda cmd, **kw:
        subprocess.CompletedProcess(cmd, 0))
    ok, detail = audit.check_build()
    assert ok is True
    assert detail == "voicelab imports cleanly"


def test_check_build_fails_on_a_nonzero_exit(monkeypatch):
    monkeypatch.setattr(audit, "sh", lambda cmd, **kw:
        subprocess.CompletedProcess(cmd, 1))
    ok, _ = audit.check_build()
    assert ok is False


def test_check_evaluate_reports_the_real_last_line(monkeypatch):
    monkeypatch.setattr(audit, "sh", lambda cmd, **kw:
        subprocess.CompletedProcess(cmd, 0, stdout="...\n5 passed in 0.1s\n"))
    ok, detail = audit.check_evaluate()
    assert ok is True
    assert detail == "5 passed in 0.1s"


def test_check_handoff_reads_the_real_ch21_fixed_run():
    ok, detail = audit.check_handoff()
    assert ok is True
    assert "2 handoff(s)" in detail


def test_check_transfer_reads_the_real_ch17_run():
    ok, detail = audit.check_transfer()
    assert ok is True
    assert "ok=True" in detail
    line = f"{'PASS':<5} {'transfer':<16} {detail}"
    assert len(line) <= 78, line


def test_check_detect_finds_a_generic_error_without_touching_real_evidence(
    tmp_path,
):
    run = tmp_path / "fake-break"
    runlog.append(run / "stages.jsonl", {
        "event": "assistant said",
        "text": "an internal error occurred while trying to book this",
    })

    ok, detail = audit.check_detect(run=str(run))

    assert ok is True
    assert "1 generic error(s)" in detail


def test_check_regression_case_flags_a_fresh_break_without_touching_real_evidence(
    monkeypatch, tmp_path,
):
    monkeypatch.chdir(tmp_path)
    run = tmp_path / "runs" / "fake-break"
    runlog.append(run / "stages.jsonl", {
        "event": "assistant said",
        "text": "an internal error occurred while trying to book this",
    })

    ok, detail = audit.check_regression_case()

    assert ok is True
    assert "runs/fake-break" in detail
    assert "generic error" in detail


def test_check_rollback_reports_the_real_last_line(monkeypatch, tmp_path):
    calls = []

    def fake_sh(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "worktree"] and cmd[2] == "add":
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[:2] == ["uv", "run"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="...\n184 passed in 24.78s\n"
            )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(audit, "sh", fake_sh)

    ok, detail = audit.check_rollback()

    assert ok is True
    assert "184 passed in 24.78s" in detail
    assert any(c[:3] == ["git", "worktree", "add"] for c in calls)
    assert any(c[:3] == ["git", "worktree", "remove"] for c in calls)


def test_main_reports_every_step_and_a_final_tally(monkeypatch, capsys):
    async def ok_true():
        return True, "fine"

    def ok_true_sync():
        return True, "fine"

    monkeypatch.setattr(audit, "STEPS", [
        ("a", ok_true_sync), ("b", ok_true),
    ])

    asyncio.run(audit.main())

    out = capsys.readouterr().out
    assert "PASS  a" in out
    assert "PASS  b" in out
    assert "2 of 2 checks passed" in out
