"""Chapter 31: seeding v1 then v2 produces the exact two versions
the chapter's own live calls were placed against."""

import version_demo


def test_seed_v1_has_only_the_booking_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(version_demo, "DB", str(tmp_path / "registry.db"))

    v1 = version_demo.seed_v1()

    assert v1.version == 1
    assert v1.tools == ["book_callback"]


def test_seed_v2_adds_the_refund_tool_on_top_of_v1(monkeypatch, tmp_path):
    monkeypatch.setattr(version_demo, "DB", str(tmp_path / "registry.db"))
    version_demo.seed_v1()

    v2 = version_demo.seed_v2()

    assert v2.version == 2
    assert v2.tools == ["book_callback", "issue_refund"]
