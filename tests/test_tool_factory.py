"""Chapter 31: a version's tool names build the real tool objects
this book has used since Chapters 9 and 18, or refuse to."""

import pytest

from voicelab.tool_factory import TOOL_FACTORIES, build_tools


def test_every_known_tool_builds_a_real_function_tool(tmp_path):
    tools = build_tools(
        ["book_callback", "issue_refund"], str(tmp_path / "ledger.jsonl"),
        "room-1", str(tmp_path / "stages.jsonl"),
    )
    assert len(tools) == 2
    assert {t.info.name for t in tools} == {"book_callback", "issue_refund"}


def test_an_empty_list_builds_no_tools(tmp_path):
    tools = build_tools(
        [], str(tmp_path / "ledger.jsonl"), "room-1",
        str(tmp_path / "stages.jsonl"),
    )
    assert tools == []


def test_an_unknown_tool_name_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no such tool"):
        build_tools(
            ["book_callback", "delete_everything"],
            str(tmp_path / "ledger.jsonl"), "room-1",
            str(tmp_path / "stages.jsonl"),
        )


def test_the_factory_registry_names_match_the_real_tool_they_build(
    tmp_path,
):
    for name, factory in TOOL_FACTORIES.items():
        tool = factory(
            str(tmp_path / "ledger.jsonl"), "room-1",
            str(tmp_path / "stages.jsonl"),
        )
        assert tool.info.name == name
