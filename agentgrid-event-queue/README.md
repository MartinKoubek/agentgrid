# agentgrid-event-queue

`agentgrid-event-queue` is the standalone persistent Event Queue for AgentGrid.

It stores normalized events until another component can process them. It does not observe runtimes, dispatch to the Master, or decide how an event should be handled.

## Scope

- Persist events in SQLite.
- Return pending events by priority and insertion order.
- Support deduplication with optional `dedupe_key`.
- Support `PENDING`, `IN_PROGRESS`, `PARKED`, and `ACKED` states.
- Allow events to be acknowledged, parked, and unparked.

## CLI

```sh
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 enqueue AGENT_STARTED --agent-id ag-001 --priority 60 --json
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 next --json
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 ack ev-001
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 park ev-002
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 unpark ev-002
./bin/agentgrid-event-queue --store /tmp/events.sqlite3 list --json
```

## Python API

```python
from agentgrid_event_queue import EventQueue

queue = EventQueue("/tmp/events.sqlite3")
event = queue.enqueue("AGENT_STARTED", agent_id="ag-001", priority=60)
next_event = queue.next()
queue.ack(next_event.id)
```
