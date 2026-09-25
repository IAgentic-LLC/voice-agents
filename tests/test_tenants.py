"""Chapter 34: organizations and memberships are each written once;
a role change is a new row, not an edit to an old one."""

import pytest

from voicelab.tenants import (
    OrgExistsError, add_member, create_org, get_org, get_role, list_members,
)


def test_a_new_org_can_be_read_back(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")

    org = get_org(db, "acme")
    assert org.org_id == "acme"
    assert org.name == "Acme Corp"


def test_an_unknown_org_is_none(tmp_path):
    db = str(tmp_path / "tenants.db")
    assert get_org(db, "nobody") is None


def test_creating_the_same_org_id_twice_is_refused(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")

    with pytest.raises(OrgExistsError):
        create_org(db, "acme", "A different name entirely")


def test_a_non_member_has_no_role(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")
    assert get_role(db, "acme", "auth0|nobody") is None


def test_an_unknown_role_name_is_refused(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")
    with pytest.raises(ValueError):
        add_member(db, "acme", "auth0|abc", "superuser")


def test_the_most_recent_membership_row_wins(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")
    add_member(db, "acme", "auth0|abc", "viewer")
    add_member(db, "acme", "auth0|abc", "owner")

    assert get_role(db, "acme", "auth0|abc") == "owner"

    import voicelab.tenants as tenants_module
    assert not hasattr(tenants_module, "update_membership")


def test_a_role_in_one_org_does_not_leak_into_another(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")
    create_org(db, "globex", "Globex Inc")
    add_member(db, "acme", "auth0|abc", "owner")

    assert get_role(db, "acme", "auth0|abc") == "owner"
    assert get_role(db, "globex", "auth0|abc") is None


def test_list_members_is_one_row_per_subject_at_their_latest_role(tmp_path):
    db = str(tmp_path / "tenants.db")
    create_org(db, "acme", "Acme Corp")
    add_member(db, "acme", "auth0|abc", "viewer")
    add_member(db, "acme", "auth0|abc", "editor")
    add_member(db, "acme", "auth0|def", "owner")

    members = list_members(db, "acme")
    roles = {m.subject: m.role for m in members}
    assert roles == {"auth0|abc": "editor", "auth0|def": "owner"}
