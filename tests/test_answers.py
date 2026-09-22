"""Pin the Chapter 11 results, and the scorer behind them."""

import statistics

from answers import ID, scored
from voicelab import knowledge, runlog


def words(run):
    return [r["words"] for r in scored(f"runs/{run}")]


def test_telling_it_to_speak_shortens_the_answer():
    plain, spoken = words("ch11-plain"), words("ch11-spoken")
    assert len(plain) == len(spoken) == 5
    assert statistics.median(plain) == 19
    assert statistics.median(spoken) == 11
    assert max(plain) == 31 and max(spoken) == 22


def test_the_spoken_agent_got_every_question_right():
    rows = scored("runs/ch11-spoken")
    assert all(r["right"] for r in rows)


def test_no_agent_said_a_passage_id_aloud():
    for run in ("ch11-plain", "ch11-spoken", "ch11-one"):
        assert not any(r["leaked"] for r in scored(f"runs/{run}"))


def test_the_leak_detector_does_not_fire_on_ordinary_english():
    """The bug this chapter reports: `cancelling` is a passage id."""
    assert "cancelling" in knowledge.PASSAGES
    assert not ID.search("There is no fee for cancelling a subscription.")
    assert ID.search("According to refund-timing, five to ten days.")
    assert ID.search("See [cancelling] for details.")


def test_the_lost_words_did_not_change_the_retrieval():
    """The chapter's corrected causal story."""
    full = knowledge.search("How long do I have to return something "
                            "I bought?", limit=5)
    cut = knowledge.search("Do I have to return something I bought?",
                           limit=5)
    assert ([(h.passage_id, h.score) for h in full]
            == [(h.passage_id, h.score) for h in cut])


def test_the_right_passage_was_second_by_a_tie():
    """And the tie is broken by dictionary order, not by score."""
    hits = knowledge.search("How long do I have to return something "
                            "I bought?", limit=3)
    assert hits[1].passage_id == "returns-window"
    assert hits[2].passage_id == "returns-postage"
    assert hits[1].score == hits[2].score
    ids = list(knowledge.PASSAGES)
    assert ids.index("returns-window") < ids.index("returns-postage")


def test_only_one_arm_was_never_told_about_ids():
    styles = {}
    for run in ("ch11-plain", "ch11-spoken", "ch11-one"):
        config = [r for r in runlog.read(f"runs/{run}/stages.jsonl")
                  if r["stage"] == "config"][0]
        styles[run] = config["style"]
    assert styles == {"ch11-plain": "plain", "ch11-spoken": "spoken",
                      "ch11-one": "spoken"}


def test_one_question_went_three_ways():
    """The same recording, three arms, three different retrievals."""
    got = {}
    for run in ("ch11-plain", "ch11-spoken", "ch11-one"):
        row = [r for r in scored(f"runs/{run}") if r["task"] == "return"][0]
        got[run] = row
    # plain searched its own paraphrase and got two wrong passages
    assert got["ch11-plain"]["passages"] == ["returns-postage",
                                             "refund-timing"]
    assert not got["ch11-plain"]["right"]
    # spoken got the right passage, second
    assert got["ch11-spoken"]["passages"] == ["shipping-address",
                                              "returns-window"]
    assert got["ch11-spoken"]["right"]
    # one got a single wrong passage and answered anyway
    assert got["ch11-one"]["passages"] == ["shipping-address"]
    assert not got["ch11-one"]["right"]


def test_the_scorer_ranks_the_wrong_passage_first_for_returns():
    """Which is why the second result matters."""
    hits = knowledge.search("How long do I have to return something "
                            "I bought?", limit=2)
    assert [h.passage_id for h in hits] == ["shipping-address",
                                            "returns-window"]


def test_every_search_is_recorded_with_its_passages():
    for run in ("ch11-plain", "ch11-spoken", "ch11-one"):
        for row in scored(f"runs/{run}"):
            assert row["searched"] >= 1
            assert row["passages"]
