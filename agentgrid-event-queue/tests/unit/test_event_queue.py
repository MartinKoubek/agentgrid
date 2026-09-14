from __future__ import annotations

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
