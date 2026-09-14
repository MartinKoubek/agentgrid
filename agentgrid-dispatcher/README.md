# agentgrid-dispatcher

`agentgrid-dispatcher` is the standalone Dispatcher for AgentGrid.

It claims events from `agentgrid-event-queue` and delivers one event at a time to a consumer. It does not implement the Master, interpret events, observe runtimes, or manage projects.

## Scope

- Claim the next pending event.
- Deliver it to an injected Python handler.
- Acknowledge, park, or requeue the event based on the handler result.
- Provide a CLI for inspecting and dispatching events independently.

## CLI

From the repository root:

```sh
./bin/agentgrid-dispatcher --help
```

Claim and print the next event without acknowledging it:

```sh
./bin/agentgrid-dispatcher --queue /tmp/events.sqlite3 next --json
```

Dispatch to a shell command. The event JSON is passed on stdin:

```sh
./bin/agentgrid-dispatcher --queue /tmp/events.sqlite3 dispatch --handler-command "python handle_event.py"
```

If the handler exits with code `0`, the event is acknowledged. If it exits with code `75`, the event is parked. Any other exit code requeues the event.

## Python API

```python
from agentgrid_dispatcher import Dispatcher, DispatchDecision
from agentgrid_event_queue import EventQueue

queue = EventQueue("/tmp/events.sqlite3")
dispatcher = Dispatcher(queue)

def handle(event):
    print(event.type)
    return DispatchDecision.ACK

dispatcher.dispatch_next(handle)
```

## Boundary

The Dispatcher controls delivery only. It does not decide what an event means or what work should happen next.
