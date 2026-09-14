from __future__ import annotations

from collections.abc import Callable

from agentgrid_dispatcher.models import DispatchDecision, DispatchResult
from agentgrid_event_queue import EventQueue, EventRecord, EventStatus


EventHandler = Callable[[EventRecord], DispatchDecision]


class Dispatcher:
    def __init__(self, queue: EventQueue) -> None:
        self.queue = queue

    def next(self) -> EventRecord | None:
        return self.queue.next()

    def dispatch_next(self, handler: EventHandler) -> DispatchResult:
        event = self.queue.next()
        if event is None:
            return DispatchResult(delivered=False)
        try:
            decision = handler(event)
        except Exception as exc:
            self.queue.unpark(event.id) if event.status == EventStatus.PARKED else self._requeue(event.id)
            return DispatchResult(delivered=True, decision=DispatchDecision.REQUEUE, event_id=event.id, error=str(exc))

        if decision == DispatchDecision.ACK:
            self.queue.ack(event.id)
        elif decision == DispatchDecision.PARK:
            self.queue.park(event.id)
        elif decision == DispatchDecision.REQUEUE:
            self._requeue(event.id)
        else:
            self._requeue(event.id)
            return DispatchResult(
                delivered=True,
                decision=DispatchDecision.REQUEUE,
                event_id=event.id,
                error=f"unknown dispatch decision: {decision}",
            )
        return DispatchResult(delivered=True, decision=decision, event_id=event.id)

    def _requeue(self, event_id: str) -> EventRecord:
        return self.queue.unpark(event_id)
