"""Chapter 31: agent versions are written once, never edited, and
a real race between two writers still lets exactly one of them
win. Chapter 34: an agent name is only unique within its own
organization."""

import threading

import pytest

from voicelab.registry import (
    StaleVersionError, connect, create_version, current_version,
    get_version, list_versions,
)

ORG = "acme"


def test_current_version_of_an_unknown_agent_is_zero(tmp_path):
    db = str(tmp_path / "registry.db")
    assert current_version(db, ORG, "booker") == 0


def test_a_first_version_is_numbered_one(tmp_path):
    db = str(tmp_path / "registry.db")
    v = create_version(db, ORG, "booker", instructions="Book callbacks.",
                       model="gemini-3.5-flash-lite",
                       tools=["book_callback"], based_on=0)
    assert v.version == 1
    assert current_version(db, ORG, "booker") == 1


def test_a_stale_based_on_is_refused(tmp_path):
    db = str(tmp_path / "registry.db")
    create_version(db, ORG, "booker", instructions="v1",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=0)

    with pytest.raises(StaleVersionError):
        create_version(db, ORG, "booker",
                       instructions="v2 written on stale data",
                       model="gemini-3.5-flash-lite",
                       tools=["book_callback"], based_on=0)


def test_get_version_with_no_number_returns_the_latest(tmp_path):
    db = str(tmp_path / "registry.db")
    create_version(db, ORG, "booker", instructions="v1",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=0)
    create_version(db, ORG, "booker", instructions="v2",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=1)

    assert get_version(db, ORG, "booker").instructions == "v2"
    assert get_version(db, ORG, "booker", version=1).instructions == "v1"


def test_an_unknown_version_returns_none(tmp_path):
    db = str(tmp_path / "registry.db")
    assert get_version(db, ORG, "booker", version=5) is None


def test_list_versions_is_every_row_oldest_first(tmp_path):
    db = str(tmp_path / "registry.db")
    create_version(db, ORG, "booker", instructions="v1",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=0)
    create_version(db, ORG, "booker", instructions="v2",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=1)

    versions = list_versions(db, ORG, "booker")
    assert [v.version for v in versions] == [1, 2]
    assert [v.instructions for v in versions] == ["v1", "v2"]


def test_two_writers_racing_on_the_same_based_on_only_one_wins(tmp_path):
    db = str(tmp_path / "registry.db")
    create_version(db, ORG, "booker", instructions="v1",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=0)

    results = []

    def try_write(label):
        try:
            create_version(db, ORG, "booker", instructions=label,
                           model="gemini-3.5-flash-lite",
                           tools=["book_callback"], based_on=1)
            results.append(("won", label))
        except StaleVersionError:
            results.append(("lost", label))

    threads = [threading.Thread(target=try_write, args=(f"writer-{i}",))
              for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    wins = [r for r in results if r[0] == "won"]
    assert len(wins) == 1
    assert current_version(db, ORG, "booker") == 2
    assert len(list_versions(db, ORG, "booker")) == 2


def test_an_agent_version_is_never_updated_in_place(tmp_path):
    """There is no update function in this module at all: the only
    way to change what an agent does is to write a new version."""
    import voicelab.registry as registry_module
    assert not hasattr(registry_module, "update_version")


def test_the_same_agent_name_in_two_orgs_is_two_separate_histories(
    tmp_path,
):
    db = str(tmp_path / "registry.db")
    create_version(db, "acme", "booker", instructions="acme's own booker",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback"], based_on=0)
    create_version(db, "globex", "booker", instructions="globex's own booker",
                   model="gemini-3.5-flash-lite",
                   tools=["book_callback", "issue_refund"], based_on=0)

    acme_v1 = get_version(db, "acme", "booker", version=1)
    globex_v1 = get_version(db, "globex", "booker", version=1)

    assert acme_v1.instructions == "acme's own booker"
    assert acme_v1.tools == ["book_callback"]
    assert globex_v1.instructions == "globex's own booker"
    assert globex_v1.tools == ["book_callback", "issue_refund"]
    assert current_version(db, "acme", "booker") == 1
    assert current_version(db, "globex", "booker") == 1
