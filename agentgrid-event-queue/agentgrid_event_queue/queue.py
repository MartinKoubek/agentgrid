from __future__ import annotations

import sqlite3
from pathlib import Path
from time import time

from agentgrid_event_queue.models import EventRecord, EventStatus


class EventQueue:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "events.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def enqueue(
        self,
        event_type: str,
        priority: int = 50,
        payload: dict[str, object] | None = None,
        dedupe_key: str | None = None,
        agent_id: str | None = None,
        pane_id: str | None = None,
        project_id: str | None = None,
    ) -> EventRecord:
        event_payload = dict(payload or {})
        if project_id is not None:
            event_payload["project_id"] = project_id
        if agent_id is not None:
            event_payload["agent_id"] = agent_id
        if pane_id is not None:
            event_payload["pane_id"] = pane_id
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if dedupe_key:
                row = connection.execute(
                    "SELECT data FROM events WHERE dedupe_key = ? AND status IN (?, ?, ?)",
                    (dedupe_key, EventStatus.PENDING.value, EventStatus.IN_PROGRESS.value, EventStatus.PARKED.value),
                ).fetchone()
                if row is not None:
                    return EventRecord.from_json(row[0])
            event_id = self._allocate_id(connection)
            event = EventRecord(
                id=event_id,
                type=event_type,
                priority=priority,
                payload=event_payload,
                dedupe_key=dedupe_key,
            )
            self._upsert(connection, event)
            return event

    def next(self) -> EventRecord | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, data FROM events WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT 1",
                (EventStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                return None
            event = EventRecord.from_json(row[1])
            event.mark(EventStatus.IN_PROGRESS)
            self._upsert(connection, event)
            return event

    def ack(self, event_id: str) -> EventRecord:
        return self._mark(event_id, EventStatus.ACKED)

    def park(self, event_id: str) -> EventRecord:
        return self._mark(event_id, EventStatus.PARKED)

    def unpark(self, event_id: str) -> EventRecord:
        return self._mark(event_id, EventStatus.PENDING)

    def get(self, event_id: str) -> EventRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise KeyError(f"event not found: {event_id}")
        return EventRecord.from_json(row[0])

    def list(
        self,
        status: str | None = None,
        limit: int = 100,
        project_id: str | None = None,
    ) -> list[EventRecord]:
        sql = "SELECT data FROM events"
        where = []
        params: list[object] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [EventRecord.from_json(row[0]) for row in rows]

    def _mark(self, event_id: str, status: EventStatus) -> EventRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(f"event not found: {event_id}")
            event = EventRecord.from_json(row[0])
            event.mark(status)
            self._upsert(connection, event)
            return event

    def _allocate_id(self, connection: sqlite3.Connection) -> str:
        row = connection.execute("SELECT next_value FROM event_sequence WHERE name = 'event'").fetchone()
        next_value = int(row[0]) if row else 1
        connection.execute(
            "INSERT INTO event_sequence(name, next_value) VALUES('event', ?) "
            "ON CONFLICT(name) DO UPDATE SET next_value = excluded.next_value",
            (next_value + 1,),
        )
        return f"ev-{next_value:03d}"

    def _upsert(self, connection: sqlite3.Connection, event: EventRecord) -> None:
        project_id = event.payload.get("project_id")
        project_id_value = str(project_id) if project_id is not None else None
        connection.execute(
            "INSERT INTO events(id, type, priority, status, dedupe_key, project_id, created_at, updated_at, data) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "type = excluded.type, priority = excluded.priority, status = excluded.status, "
            "dedupe_key = excluded.dedupe_key, project_id = excluded.project_id, "
            "updated_at = excluded.updated_at, data = excluded.data",
            (
                event.id,
                event.type,
                event.priority,
                event.status.value,
                event.dedupe_key,
                project_id_value,
                event.created_at,
                event.updated_at,
                event.to_json(),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "id TEXT PRIMARY KEY, type TEXT NOT NULL, priority INTEGER NOT NULL, "
                "status TEXT NOT NULL, dedupe_key TEXT, project_id TEXT, created_at REAL NOT NULL, "
                "updated_at REAL NOT NULL, data TEXT NOT NULL)"
            )
            self._ensure_project_id_column(connection)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_next ON events(status, priority, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_dedupe ON events(dedupe_key, status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_project ON events(project_id, priority, created_at)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS event_sequence (name TEXT PRIMARY KEY, next_value INTEGER NOT NULL)"
            )
            connection.execute("INSERT OR IGNORE INTO event_sequence(name, next_value) VALUES('event', 1)")

    def _ensure_project_id_column(self, connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(events)").fetchall()}
        if "project_id" in columns:
            return
        connection.execute("ALTER TABLE events ADD COLUMN project_id TEXT")
        self._backfill_project_ids(connection)

    def _backfill_project_ids(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute("SELECT id, data FROM events WHERE project_id IS NULL").fetchall()
        for event_id, data in rows:
            event = EventRecord.from_json(data)
            project_id = event.payload.get("project_id")
            if project_id is not None:
                connection.execute("UPDATE events SET project_id = ? WHERE id = ?", (str(project_id), event_id))
