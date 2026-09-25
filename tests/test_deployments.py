"""Chapter 33: deployments are written once, never edited; a
rollback is just another deploy, pointed backward; and which lane
a call lands in is a plain, seedable die roll."""

import pytest

from voicelab.registry import (
    Deployment, choose_version, create_version, current_deployment, deploy,
)


class FixedRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def _seed_two_versions(db, agent="booker"):
    v1 = create_version(db, agent, instructions="v1",
                        model="gemini-3.5-flash-lite",
                        tools=["book_callback"], based_on=0)
    v2 = create_version(db, agent, instructions="v2",
                        model="gemini-3.5-flash-lite",
                        tools=["book_callback", "issue_refund"],
                        based_on=1)
    return v1.version, v2.version


def test_a_new_agent_has_no_deployment(tmp_path):
    db = str(tmp_path / "registry.db")
    assert current_deployment(db, "booker") is None


def test_deploying_an_unknown_stable_version_is_refused(tmp_path):
    db = str(tmp_path / "registry.db")
    with pytest.raises(ValueError):
        deploy(db, "booker", stable_version=1)


def test_deploying_an_unknown_canary_version_is_refused(tmp_path):
    db = str(tmp_path / "registry.db")
    v1, _ = _seed_two_versions(db)
    with pytest.raises(ValueError):
        deploy(db, "booker", stable_version=v1, canary_version=99,
              canary_percent=10.0)


def test_current_deployment_is_the_most_recently_written_one(tmp_path):
    db = str(tmp_path / "registry.db")
    v1, v2 = _seed_two_versions(db)
    deploy(db, "booker", stable_version=v1)
    deploy(db, "booker", stable_version=v1, canary_version=v2,
          canary_percent=25.0)

    d = current_deployment(db, "booker")
    assert d.stable_version == v1
    assert d.canary_version == v2
    assert d.canary_percent == 25.0


def test_rollback_is_a_third_deployment_row_not_an_edit(tmp_path):
    db = str(tmp_path / "registry.db")
    v1, v2 = _seed_two_versions(db)
    deploy(db, "booker", stable_version=v1)
    deploy(db, "booker", stable_version=v1, canary_version=v2,
          canary_percent=50.0)
    deploy(db, "booker", stable_version=v1)

    import voicelab.registry as registry_module
    assert not hasattr(registry_module, "rollback")
    assert not hasattr(registry_module, "update_deployment")

    d = current_deployment(db, "booker")
    assert d.stable_version == v1
    assert d.canary_version is None
    assert d.canary_percent == 0.0


def test_choose_version_with_no_canary_is_always_stable():
    d = Deployment("booker", 1, stable_version=1, canary_version=None,
                   canary_percent=0.0, created_at=0.0)
    version, lane = choose_version(d, rng=FixedRng(0.0))
    assert (version, lane) == (1, "stable")


def test_choose_version_below_the_canary_threshold_is_canary():
    d = Deployment("booker", 1, stable_version=1, canary_version=2,
                   canary_percent=30.0, created_at=0.0)
    version, lane = choose_version(d, rng=FixedRng(0.1))
    assert (version, lane) == (2, "canary")


def test_choose_version_above_the_canary_threshold_is_stable():
    d = Deployment("booker", 1, stable_version=1, canary_version=2,
                   canary_percent=30.0, created_at=0.0)
    version, lane = choose_version(d, rng=FixedRng(0.9))
    assert (version, lane) == (1, "stable")
