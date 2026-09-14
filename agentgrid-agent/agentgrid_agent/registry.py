from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from agentgrid_agent.models import Agent


class SQLiteAgentRegistry:
    _init_lock = threading.Lock()

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "agents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def allocate_id(self) -> str:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT next_value FROM agent_sequence WHERE name = 'agent'").fetchone()
            next_value = int(row[0]) if row else 1
            connection.execute(
                "INSERT INTO agent_sequence(name, next_value) VALUES('agent', ?) "
                "ON CONFLICT(name) DO UPDATE SET next_value = excluded.next_value",
                (next_value + 1,),
            )
            return f"ag-{next_value:03d}"

    def list(self) -> list[Agent]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM agents ORDER BY id").fetchall()
        return [Agent.from_json(row[0]) for row in rows]

    def get(self, agent_id: str) -> Agent:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            raise KeyError(f"agent not found: {agent_id}")
        return Agent.from_json(row[0])

    def save(self, agent: Agent) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO agents(id, data) VALUES(?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                (agent.id, agent.to_json()),
            )

    def delete(self, agent_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    def next_id(self) -> str:
        return self.allocate_id()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._init_lock:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS agents ("
                    "id TEXT PRIMARY KEY, "
                    "data TEXT NOT NULL"
                    ")"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS agent_sequence ("
                    "name TEXT PRIMARY KEY, "
                    "next_value INTEGER NOT NULL"
                    ")"
                )
                connection.execute(
                    "INSERT OR IGNORE INTO agent_sequence(name, next_value) VALUES('agent', 1)"
                )


FileAgentRegistry = SQLiteAgentRegistry
