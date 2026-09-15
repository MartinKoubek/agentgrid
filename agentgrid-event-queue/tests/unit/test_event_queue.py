from __future__ import annotations

import json
import sqlite3

from agentgrid_event_queue import EventQueue, EventStatus


def test_queue_claims_highest_priority_first(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")

    low = queue.enqueue("LOW", priority=10)
    high = queue.enqueue("HIGH", priority=90)

    claimed = queue.next()


    assert claimed is not None
    assert claimed.id == high.id
    assert queue.get(high.id).status == EventStatus.IN_PROGRESS
    assert queue.get(low.id).status == EventStatus.PENDING


def test_queue_deduplicates_pending_events(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")

    first = queue.enqueue("AGENT_OUTPUT_CHANGED", dedupe_key="agent:ag-001:output")
    second = queue.enqueue("AGENT_OUTPUT_CHANGED", dedupe_key="agent:ag-001:output")

    assert second.id == first.id
    assert len(queue.list()) == 1


def test_queue_ack_park_and_unpark(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("WAITING_USER", priority=80)

    claimed = queue.next()
    assert claimed is not None

    parked = queue.park(claimed.id)
    assert parked.status == EventStatus.PARKED

    unparked = queue.unpark(claimed.id)
    assert unparked.status == EventStatus.PENDING

    acknowledged = queue.ack(claimed.id)
    assert acknowledged.status == EventStatus.ACKED


def test_queue_preserves_payload_fields(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")

    event = queue.enqueue("AGENT_STARTED", agent_id="ag-001", pane_id="%1", payload={"extra": True})

    loaded = queue.get(event.id)
    assert loaded.payload == {"agent_id": "ag-001", "pane_id": "%1", "extra": True}


def test_queue_filters_project_before_limit(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")

    for index in range(3):
        queue.enqueue("PROJECT_A_EVENT", priority=10, project_id="project-a", payload={"index": index})
    for index in range(20):
        queue.enqueue("OTHER_EVENT", priority=90, project_id=f"project-{index}")

    records = queue.list(limit=10, project_id="project-a")

    assert len(records) == 3
    assert {record.payload["project_id"] for record in records} == {"project-a"}


def test_queue_migrates_legacy_project_id_once(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.sqlite3"
    legacy_event = {
        "id": "ev-001",
        "type": "AGENT_STARTED",
        "priority": 50,
        "status": "PENDING",
        "payload": {"project_id": "project-a", "agent_id": "ag-001"},
        "dedupe_key": None,
        "created_at": 1.0,
        "updated_at": 1.0,
    }
    global_event = {
        "id": "ev-002",
        "type": "GLOBAL",
        "priority": 50,
        "status": "PENDING",
        "payload": {},
        "dedupe_key": None,
        "created_at": 2.0,
        "updated_at": 2.0,
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE events ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, priority INTEGER NOT NULL, "
            "status TEXT NOT NULL, dedupe_key TEXT, created_at REAL NOT NULL, "
            "updated_at REAL NOT NULL, data TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO events(id, type, priority, status, dedupe_key, created_at, updated_at, data) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            ("ev-001", "AGENT_STARTED", 50, "PENDING", None, 1.0, 1.0, json.dumps(legacy_event)),
        )
        connection.execute(
            "INSERT INTO events(id, type, priority, status, dedupe_key, created_at, updated_at, data) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            ("ev-002", "GLOBAL", 50, "PENDING", None, 2.0, 2.0, json.dumps(global_event)),
        )

    queue = EventQueue(path)
    assert [event.id for event in queue.list(project_id="project-a")] == ["ev-001"]

    def fail_backfill(*args, **kwargs):
        raise AssertionError("backfill should not run after migration")

    monkeypatch.setattr(EventQueue, "_backfill_project_ids", fail_backfill)
    EventQueue(path)
