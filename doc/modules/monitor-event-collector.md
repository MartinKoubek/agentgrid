# Monitor / Event Collector

## Responsibility

Continuously observes runtime changes and converts them into normalized events. The Master should not continuously poll dozens of terminal panes itself.

## Possible conditions

- worker process exited
- worker output changed
- worker appears to wait for input
- shell command failed
- SSH session disconnected
- test or build completed/failed

## Example event types

```text
AGENT_STARTED
AGENT_OUTPUT_CHANGED
AGENT_WAITING_INPUT
AGENT_FINISHED
AGENT_FAILED
PROCESS_EXITED
SSH_DISCONNECTED
COMMAND_FAILED
TEST_FINISHED
```

## Example event

```json
{
  "type": "AGENT_WAITING_INPUT",
  "project_id": "android-app",
  "agent_id": "ag-17",
  "priority": 80
}
```

The collector observes and normalizes. It does not decide how the event should be handled.
