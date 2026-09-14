from __future__ import annotations

import sqlite3
from pathlib import Path

from agentgrid_shell_logger.models import CommandRecord


class ShellLogStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "shell-log.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def allocate_id(self) -> str:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT next_value FROM command_sequence WHERE name = 'command'").fetchone()
            next_value = int(row[0]) if row else 1
            connection.execute(
                "INSERT INTO command_sequence(name, next_value) VALUES('command', ?) "
                "ON CONFLICT(name) DO UPDATE SET next_value = excluded.next_value",
                (next_value + 1,),
            )
            return f"cmd-{next_value:03d}"

    def save(self, record: CommandRecord) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO command_records(id, started_at, data) VALUES(?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET started_at = excluded.started_at, data = excluded.data",
                (record.id, record.started_at, record.to_json()),
            )

    def get(self, record_id: str) -> CommandRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM command_records WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(f"command record not found: {record_id}")
        return CommandRecord.from_json(row[0])

    def list(self, limit: int = 50) -> list[CommandRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM command_records ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [CommandRecord.from_json(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS command_records ("
                "id TEXT PRIMARY KEY, "
                "started_at REAL NOT NULL, "
                "data TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS command_sequence ("
                "name TEXT PRIMARY KEY, "
                "next_value INTEGER NOT NULL"
                ")"
            )
            connection.execute("INSERT OR IGNORE INTO command_sequence(name, next_value) VALUES('command', 1)")
