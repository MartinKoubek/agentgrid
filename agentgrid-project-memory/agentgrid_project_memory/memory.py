from __future__ import annotations

import sqlite3
from pathlib import Path

from agentgrid_project_memory.models import MemoryEntry


class ProjectMemory:
    PROJECT_STATE = "Project State"
    DECISION_LOG = "Decision Log"
    LESSONS_LEARNED = "Lessons Learned"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "project-memory.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def add(self, project_id: str, category: str, content: str, metadata: dict[str, object] | None = None) -> MemoryEntry:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            entry_id = self._allocate_id(connection)
            entry = MemoryEntry(entry_id, project_id, category, content, metadata or {})
            connection.execute(
                "INSERT INTO memory_entries(id, project_id, category, content, created_at, data) VALUES(?, ?, ?, ?, ?, ?)",
                (entry.id, project_id, category, content, entry.created_at, entry.to_json()),
            )
            return entry

    def list(self, project_id: str, category: str | None = None, limit: int = 50) -> list[MemoryEntry]:
        sql = "SELECT data FROM memory_entries WHERE project_id = ?"
        params: list[object] = [project_id]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [MemoryEntry.from_json(row[0]) for row in rows]

    def search(self, project_id: str, query: str, limit: int = 20) -> list[MemoryEntry]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM memory_entries WHERE project_id = ? AND content LIKE ? ORDER BY created_at DESC LIMIT ?", (project_id, f"%{query}%", limit)).fetchall()
        return [MemoryEntry.from_json(row[0]) for row in rows]

    def _allocate_id(self, connection: sqlite3.Connection) -> str:
        row = connection.execute("SELECT next_value FROM memory_sequence WHERE name = 'memory'").fetchone()
        next_value = int(row[0]) if row else 1
        connection.execute("INSERT INTO memory_sequence(name, next_value) VALUES('memory', ?) ON CONFLICT(name) DO UPDATE SET next_value = excluded.next_value", (next_value + 1,))
        return f"mem-{next_value:03d}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS memory_entries(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, data TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id, category, created_at)")
            connection.execute("CREATE TABLE IF NOT EXISTS memory_sequence(name TEXT PRIMARY KEY, next_value INTEGER NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO memory_sequence(name, next_value) VALUES('memory', 1)")
