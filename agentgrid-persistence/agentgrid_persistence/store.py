from __future__ import annotations

import json, sqlite3
from pathlib import Path
from time import time


class DocumentStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "persistence.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def put(self, namespace: str, key: str, value: dict[str, object]) -> None:
        now = time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO documents(namespace, key, updated_at, data) VALUES(?, ?, ?, ?) ON CONFLICT(namespace, key) DO UPDATE SET updated_at = excluded.updated_at, data = excluded.data", (namespace, key, now, json.dumps(value, sort_keys=True)))

    def get(self, namespace: str, key: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM documents WHERE namespace = ? AND key = ?", (namespace, key)).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, namespace: str, key: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM documents WHERE namespace = ? AND key = ?", (namespace, key))

    def list(self, namespace: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT key, updated_at, data FROM documents WHERE namespace = ? ORDER BY key", (namespace,)).fetchall()
        return [{"key": row[0], "updated_at": row[1], "value": json.loads(row[2])} for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS documents(namespace TEXT NOT NULL, key TEXT NOT NULL, updated_at REAL NOT NULL, data TEXT NOT NULL, PRIMARY KEY(namespace, key))")
