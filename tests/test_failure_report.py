"""Chapter 28: the failure report reads three real calls against the
same tool and prints exactly what each caller heard."""

import failure_report


def test_the_three_real_calls_show_three_different_replies(capsys):
    failure_report.main(
        ["runs/ch28-off", "runs/ch28-plain", "runs/ch28-tool-error"]
    )

    out = capsys.readouterr().out
    assert "fail_mode=off" in out
    assert "I have successfully booked your callback" in out
    assert "fail_mode=plain" in out
    assert "an internal error occurred while trying to book your callback" \
        in out
    assert "fail_mode=tool_error" in out
    assert "I couldn't reach the booking system" in out
    for line in out.splitlines():
        assert len(line) <= 78, line


def test_a_run_with_no_reply_says_so(tmp_path, capsys):
    run = tmp_path / "empty"
    run.mkdir()
    (run / "stages.jsonl").write_text(
        '{"stage": "config", "fail_mode": "off"}\n', encoding="utf8"
    )

    failure_report.main([str(run)])

    assert "agent said: nothing" in capsys.readouterr().out
