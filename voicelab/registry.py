"""Chapter 31: agent definitions this book has hardcoded into a
`.py` file since Chapter 9, persisted instead, and versioned the
way code itself is: never edited in place, only ever added to.

Every version is a real row, written once and never updated. A
`based_on` check makes that immutability hold even against two
writers racing each other, not just against a single careless one.
"""

import json
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
