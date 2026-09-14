# agentgrid-agent

`agentgrid-agent` is the standalone AgentGrid runtime manager for interactive worker processes.

It turns a generic tmux pane managed by `agentgrid-tmux` into an AgentGrid agent with a stable `agent_id`, lifecycle state, bidirectional input and output, and adapter-based behavior. It knows nothing about projects, queues, Master, memory, event routing, or provider-specific protocols.

## Scope

- Start an agent in a new pane or an existing pane.
- Assign stable IDs such as `ag-001`.
- Persist the mapping from `agent_id` to tmux `pane_id`.
- Send input through `agentgrid-tmux`.
- Read output through `agentgrid-tmux`.
- Track lifecycle states: `STARTING`, `RUNNING`, `STOPPED`, and `FAILED`.
- Expose `is_alive()`, `stop()`, `restart()`, and `inspect()`.
- Keep provider-specific behavior behind `AgentAdapter` implementations.

## Architecture Rule

`agentgrid-agent` must never execute tmux commands directly. All tmux access goes through the Python API exposed by `agentgrid-tmux`.

```text
agentgrid-agent
  |
  v
agentgrid-tmux
  |
  v
tmux
```

## CLI

From the repository root:

```sh
./agentgrid-agent/bin/agentgrid-agent --help
```

Start a fake deterministic agent:

```sh
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo start --adapter fake
```

List and inspect agents:

```sh
./agentgrid-agent/bin/agentgrid-agent list --json
./agentgrid-agent/bin/agentgrid-agent inspect ag-001 --json
```

Send input and read output:

```sh
./agentgrid-agent/bin/agentgrid-agent send ag-001 "hello"
./agentgrid-agent/bin/agentgrid-agent read ag-001
```

Stop an agent:

```sh
./agentgrid-agent/bin/agentgrid-agent stop ag-001
```

Use an isolated tmux server and registry for tests or demos:

```sh
tmux -L agentgrid-demo start-server
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.json start --adapter fake
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.json send ag-001 "hello"
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.json read ag-001
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.json stop ag-001
tmux -L agentgrid-demo kill-server
```

## Python API

Python package description: `agentgrid_agent` manages interactive runtime agents by storing agent metadata, delegating pane IO to `tmuxio`, and dispatching behavior through adapter interfaces.

```python
from agentgrid_agent import AgentManager

manager = AgentManager()
agent = manager.start(adapter="fake")

manager.send(agent.id, "hello")
print(manager.read(agent.id))
manager.stop(agent.id)
```

## Adapter Interface

Adapters implement:

```python
class AgentAdapter:
    def start(self, pane, config): ...
    def send(self, agent, text): ...
    def read(self, agent): ...
    def is_alive(self, agent): ...
    def stop(self, agent): ...
```

The included `fake` adapter is deterministic and intended for local tests. It responds to input with `ACK: <input>` and exits when it receives `exit`.
