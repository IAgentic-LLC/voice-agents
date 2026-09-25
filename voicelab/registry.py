"""Chapter 31: agent definitions this book has hardcoded into a
`.py` file since Chapter 9, persisted instead, and versioned the
way code itself is: never edited in place, only ever added to.

Every version is a real row, written once and never updated. A
`based_on` check makes that immutability hold even against two
writers racing each other, not just against a single careless one.
"""

import json
import random
import sqlite3
import time
from dataclasses import dataclass


class StaleVersionError(Exception):
    """Raised when `based_on` is not the real current version, the
    same shape of conflict a compare-and-swap write refuses."""


@dataclass(frozen=True)
class AgentVersion:
    agent_name: str
    version: int
    instructions: str
    model: str
    tools: list[str]
    created_at: float


@dataclass(frozen=True)
class Deployment:
    """Which version answers a call. A deployment row is written
    once and never edited, the same discipline as `AgentVersion`
    itself; rolling back is calling `deploy` again, not a second
    code path that has to stay correct alongside the first."""
    agent_name: str
    id: int
    stable_version: int
    canary_version: int | None
    canary_percent: float
    created_at: float


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            version INTEGER NOT NULL,
            instructions TEXT NOT NULL,
            model TEXT NOT NULL,
            tools TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(agent_name, version)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            stable_version INTEGER NOT NULL,
            canary_version INTEGER,
            canary_percent REAL NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def current_version(db_path: str, agent_name: str) -> int:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM agent_versions WHERE agent_name = ?",
            (agent_name,),
        ).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def create_version(db_path: str, agent_name: str, *, instructions: str,
                   model: str, tools: list[str], based_on: int
                   ) -> AgentVersion:
    """Write the next version, but only if `based_on` is still the
    real current one. Two callers racing on the same `based_on`
    both try to insert the same version number; the table's own
    UNIQUE constraint lets exactly one of them win."""
    next_version = based_on + 1
    created_at = time.time()
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO agent_versions "
            "(agent_name, version, instructions, model, tools, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (agent_name, next_version, instructions, model,
             json.dumps(tools), created_at),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise StaleVersionError(
            f"{agent_name} is no longer at version {based_on}"
        )
    finally:
        conn.close()
    return AgentVersion(agent_name, next_version, instructions, model,
                       tools, created_at)


def get_version(db_path: str, agent_name: str, version: int | None = None
               ) -> AgentVersion | None:
    conn = connect(db_path)
    try:
        if version is None:
            row = conn.execute(
                "SELECT * FROM agent_versions WHERE agent_name = ? "
                "ORDER BY version DESC LIMIT 1",
                (agent_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM agent_versions "
                "WHERE agent_name = ? AND version = ?",
                (agent_name, version),
            ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    _, name, ver, instructions, model, tools, created_at = row
    return AgentVersion(name, ver, instructions, model,
                       json.loads(tools), created_at)


def list_versions(db_path: str, agent_name: str) -> list[AgentVersion]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM agent_versions WHERE agent_name = ? "
            "ORDER BY version ASC",
            (agent_name,),
        ).fetchall()
    finally:
        conn.close()
    return [
        AgentVersion(name, ver, instructions, model, json.loads(tools),
                    created_at)
        for _, name, ver, instructions, model, tools, created_at in rows
    ]


def deploy(db_path: str, agent_name: str, *, stable_version: int,
          canary_version: int | None = None, canary_percent: float = 0.0
          ) -> Deployment:
    """Write a new deployment record. There is no `update_deployment`
    and no separate `rollback`: pointing `stable_version` back at an
    earlier version, with no canary, is the whole rollback."""
    if get_version(db_path, agent_name, stable_version) is None:
        raise ValueError(f"{agent_name} has no version {stable_version}")
    if (canary_version is not None
            and get_version(db_path, agent_name, canary_version) is None):
        raise ValueError(f"{agent_name} has no version {canary_version}")
    created_at = time.time()
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO deployments "
            "(agent_name, stable_version, canary_version, canary_percent, "
            "created_at) VALUES (?, ?, ?, ?, ?)",
            (agent_name, stable_version, canary_version, canary_percent,
             created_at),
        )
        conn.commit()
        deployment_id = cur.lastrowid
    finally:
        conn.close()
    return Deployment(agent_name, deployment_id, stable_version,
                      canary_version, canary_percent, created_at)


def current_deployment(db_path: str, agent_name: str) -> Deployment | None:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT id, stable_version, canary_version, canary_percent, "
            "created_at FROM deployments WHERE agent_name = ? "
            "ORDER BY id DESC LIMIT 1",
            (agent_name,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    deployment_id, stable, canary, percent, created_at = row
    return Deployment(agent_name, deployment_id, stable, canary, percent,
                      created_at)


def choose_version(deployment: Deployment, rng=random) -> tuple[int, str]:
    """Which version answers one call under this deployment, and
    which lane it came from. `rng` takes any object with a `random()`
    method, so a test can hand it a fixed sequence instead of the
    real generator."""
    if (deployment.canary_version is not None
            and rng.random() * 100 < deployment.canary_percent):
        return deployment.canary_version, "canary"
    return deployment.stable_version, "stable"
