# agentgrid-monitor

`agentgrid-monitor` is the standalone Monitor / Event Collector for AgentGrid.

It observes existing agent runtime state and terminal output, then emits normalized events. It does not decide how events should be handled, does not queue events, and does not implement Master, memory, routing, or prompt interpretation.

## Scope

- Observe agents registered by `agentgrid-agent`.
- Detect first-seen running agents as `AGENT_STARTED`.
- Detect output changes as `AGENT_OUTPUT_CHANGED`.
- Detect stopped agents as `AGENT_EXITED`.
- Detect failed agents as `AGENT_FAILED`.
- Store compact monitor snapshots in SQLite so scans can be repeated safely.

## CLI

From the repository root:

```sh
./bin/agentgrid-monitor --help
```

Scan registered agents and print normalized events:

```sh
./bin/agentgrid-monitor --registry /tmp/agentgrid-agents.sqlite3 --state /tmp/agentgrid-monitor.sqlite3 scan --json
```

Use an isolated tmux server:

```sh
./bin/agentgrid-monitor --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.sqlite3 --state /tmp/agentgrid-monitor.sqlite3 scan --json
```

Reset monitor state:

```sh
./bin/agentgrid-monitor --state /tmp/agentgrid-monitor.sqlite3 reset
```

## Python API

```python
from agentgrid_agent import AgentManager, FileAgentRegistry
from agentgrid_agent.adapters import default_adapters
from agentgrid_monitor import Monitor
from tmuxio import TmuxClient

tmux = TmuxClient()
manager = AgentManager(
    tmux=tmux,
    registry=FileAgentRegistry("/tmp/agents.sqlite3"),
    adapters=default_adapters(tmux),
)
monitor = Monitor(agent_manager=manager, state_path="/tmp/monitor.sqlite3")

events = monitor.scan()
```

## Boundary

`agentgrid-monitor` only observes and normalizes events. Event ordering, priority, deduplication, acknowledgment, parking, and delivery belong to the later Event Queue and Dispatcher modules.
