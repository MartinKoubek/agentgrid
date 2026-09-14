from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agentgrid_monitor.models import AgentSnapshot


class MonitorStateStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "monitor.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_snapshot(self, agent_id: str) -> AgentSnapshot | None:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM agent_snapshots WHERE agent_id = ?", (agent_id,)).fetchone()
        if row is None:
            return None
        return AgentSnapshot.from_dict(json.loads(row[0]))

    def save_snapshot(self, snapshot: AgentSnapshot) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO agent_snapshots(agent_id, data) VALUES(?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET data = excluded.data",
                (snapshot.agent_id, json.dumps(snapshot.to_dict(), sort_keys=True)),
            )

    def reset(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM agent_snapshots")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS agent_snapshots ("
                "agent_id TEXT PRIMARY KEY, "
                "data TEXT NOT NULL"
                ")"
            )
