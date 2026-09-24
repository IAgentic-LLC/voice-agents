"""Chapter 17: the transfer trace printer stays inside 78 columns."""

from voicelab import runlog
import transfer_report


def test_no_printed_line_exceeds_the_books_column_limit(tmp_path, capsys):
    path = tmp_path / "stages.jsonl"
    runlog.append(str(path), {
        "stage": "trace", "event": "assistant said",
        "text": "Hi, this is a test call from the book. Say let me "
                "talk to a person when you're ready.",
    })
    runlog.append(str(path), {
        "stage": "sip", "identity": "warm-transfer-168681359",
        "facts": {"sip.phoneNumber": "+2547XXXXXXXX"},
    })

    transfer_report.main(str(tmp_path))

    for line in capsys.readouterr().out.splitlines():
        assert len(line) <= 78, line
