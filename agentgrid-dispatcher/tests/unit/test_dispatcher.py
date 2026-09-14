from __future__ import annotations

from agentgrid_dispatcher import DispatchDecision, Dispatcher
from agentgrid_event_queue import EventQueue, EventStatus


def test_dispatcher_acknowledges_successful_delivery(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("AGENT_STARTED")
    dispatcher = Dispatcher(queue)

    result = dispatcher.dispatch_next(lambda _: DispatchDecision.ACK)

    assert result.delivered is True
    assert result.event_id == event.id
    assert result.decision == DispatchDecision.ACK
    assert queue.get(event.id).status == EventStatus.ACKED


def test_dispatcher_parks_event(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("WAITING_USER")
    dispatcher = Dispatcher(queue)

    result = dispatcher.dispatch_next(lambda _: DispatchDecision.PARK)

    assert result.decision == DispatchDecision.PARK
    assert queue.get(event.id).status == EventStatus.PARKED


def test_dispatcher_requeues_failed_handler(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("AGENT_OUTPUT_CHANGED")
    dispatcher = Dispatcher(queue)

    def failing_handler(_):
        raise RuntimeError("boom")

    result = dispatcher.dispatch_next(failing_handler)

    assert result.decision == DispatchDecision.REQUEUE
    assert result.error == "boom"
    assert queue.get(event.id).status == EventStatus.PENDING


def test_dispatcher_requeues_unknown_handler_decision(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("AGENT_OUTPUT_CHANGED")
    dispatcher = Dispatcher(queue)

    result = dispatcher.dispatch_next(lambda _: "UNKNOWN")

    assert result.decision == DispatchDecision.REQUEUE
    assert result.error == "unknown dispatch decision: UNKNOWN"
    assert queue.get(event.id).status == EventStatus.PENDING


def test_dispatcher_handles_empty_queue(tmp_path) -> None:
    dispatcher = Dispatcher(EventQueue(tmp_path / "events.sqlite3"))

    result = dispatcher.dispatch_next(lambda _: DispatchDecision.ACK)

    assert result.delivered is False
    assert result.decision is None
