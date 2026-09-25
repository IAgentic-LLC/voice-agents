"""Chapter 34: which organization a caller belongs to, and what
they are allowed to do there. An organization and a membership are
each written once, the same discipline `AgentVersion` and
`Deployment` already established; a role change is a new
membership row, not an edit to an old one.
"""

import sqlite3
import time
from dataclasses import dataclass

ROLES = ("owner", "editor", "viewer")


class OrgExistsError(Exception):
    """Raised when `create_org` is called with an `org_id` that is
    already taken. There is no `rename_org`; an organization's id
    is fixed for its whole life."""


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    created_at: float


@dataclass(frozen=True)
class Membership:
    org_id: str
    subject: str
    role: str
    created_at: float


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def create_org(db_path: str, org_id: str, name: str) -> Organization:
    created_at = time.time()
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO organizations (org_id, name, created_at) "
            "VALUES (?, ?, ?)",
            (org_id, name, created_at),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise OrgExistsError(f"organization {org_id!r} already exists")
    finally:
        conn.close()
    return Organization(org_id, name, created_at)


def get_org(db_path: str, org_id: str) -> Organization | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT org_id, name, created_at FROM organizations "
            "WHERE org_id = ?",
            (org_id,),
        ).fetchone()
    finally:
        conn.close()
    return Organization(*row) if row else None


def add_member(db_path: str, org_id: str, subject: str, role: str
              ) -> Membership:
    """Write a new membership row. The most recent row for a given
    `(org_id, subject)` pair is that member's current role; there is
    no `update_membership`, a role change is just another row."""
    if role not in ROLES:
        raise ValueError(f"no such role {role!r}, must be one of {ROLES}")
    created_at = time.time()
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO memberships (org_id, subject, role, created_at) "
            "VALUES (?, ?, ?, ?)",
            (org_id, subject, role, created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return Membership(org_id, subject, role, created_at)


def get_role(db_path: str, org_id: str, subject: str) -> str | None:
    """The subject's current role in this org, or `None` if they
    are not a member of it at all."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT role FROM memberships "
            "WHERE org_id = ? AND subject = ? "
            "ORDER BY id DESC LIMIT 1",
            (org_id, subject),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def list_orgs_for_subject(db_path: str, subject: str) -> list[Membership]:
    """Every organization this subject currently has any role in,
    one row per org at their most recent role there."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT org_id, subject, role, created_at FROM memberships "
            "WHERE subject = ? AND id IN ("
            "  SELECT MAX(id) FROM memberships "
            "  WHERE subject = ? GROUP BY org_id"
            ") ORDER BY org_id ASC",
            (subject, subject),
        ).fetchall()
    finally:
        conn.close()
    return [Membership(*row) for row in rows]


def list_members(db_path: str, org_id: str) -> list[Membership]:
    """One row per subject: each member's most recent role."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT org_id, subject, role, created_at FROM memberships "
            "WHERE org_id = ? AND id IN ("
            "  SELECT MAX(id) FROM memberships "
            "  WHERE org_id = ? GROUP BY subject"
            ") ORDER BY subject ASC",
            (org_id, org_id),
        ).fetchall()
    finally:
        conn.close()
    return [Membership(*row) for row in rows]
