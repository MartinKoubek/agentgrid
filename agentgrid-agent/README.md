# agentgrid-agent

`agentgrid-agent` is the standalone AgentGrid runtime manager for interactive worker processes.

It turns a generic tmux pane managed by `agentgrid-tmux` into an AgentGrid agent with a stable `agent_id`, lifecycle state, bidirectional input and output, and adapter-based behavior. It knows nothing about projects, queues, Master, memory, event routing, or provider-specific protocols.

## Scope

- Start an agent in a new pane or an existing pane.
- Assign stable IDs such as `ag-001`.
- Persist the mapping from `agent_id` to tmux `pane_id`.
- Track `runtime_pid` separately from the tmux pane so an agent can stop while an existing shell pane stays alive.
- Send input through `agentgrid-tmux`.
- Read output through `agentgrid-tmux`.
- Track lifecycle states: `STARTING`, `RUNNING`, `STOPPED`, and `FAILED`.
- Expose `is_alive()`, `stop()`, `restart()`, and `inspect()`.
- Keep provider-specific behavior behind `AgentAdapter` implementations.
- Store agent registry state in SQLite for concurrent ID allocation and writes.

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

Start a Codex-backed agent in a project repository:

```sh
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 start --adapter codex --cwd /path/to/repo
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
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.sqlite3 start --adapter fake
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.sqlite3 send ag-001 "hello"
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.sqlite3 read ag-001
./agentgrid-agent/bin/agentgrid-agent --socket-name agentgrid-demo --registry /tmp/agentgrid-agents.sqlite3 stop ag-001
tmux -L agentgrid-demo kill-server
```

## Python API

Python package description: `agentgrid_agent` manages interactive runtime agents by storing agent metadata, delegating pane IO to `tmuxio`, and dispatching behavior through adapter interfaces.

```python
from agentgrid_agent import AgentManager
from agentgrid_agent.adapters import default_adapters
from tmuxio import TmuxClient

tmux = TmuxClient()
manager = AgentManager(tmux=tmux, adapters=default_adapters(tmux))
agent = manager.start(adapter="fake")

manager.send(agent.id, "hello")
print(manager.read(agent.id))
manager.stop(agent.id)
```

`AgentManager` accepts an injected adapter map. Keep provider adapters registered outside the manager:

```python
manager = AgentManager(
    tmux=tmux,
    adapters={
        "fake": fake_adapter,
    },
)
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

The included `codex` adapter is an MVP provider adapter for the local Codex CLI. It launches `codex --no-alt-screen --ask-for-approval on-request --sandbox workspace-write` inside a tmux pane through `agentgrid-tmux`, reuses the user's existing Codex CLI authentication and configuration, waits for conservative input readiness, submits prompts through tmux bracketed paste plus one Enter, reads terminal output through pane capture, and uses the shared endpoint/runtime PID handshake for liveness.

Startup readiness is intentionally conservative. The installed `codex` CLI exposes no stable machine-readable readiness signal in `codex --help`, so the adapter waits for live process output to settle and fails clearly on known blocking startup prompts such as update, local data repair, and login/authentication prompts. If startup fails, the agent is marked `FAILED` and the manager attempts best-effort cleanup instead of silently sending a task into an unknown UI state.

Manual Codex smoke test:

```sh
tmux -L agentgrid-codex start-server
./bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 start --adapter codex --cwd /path/to/repo --json
./bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 send ag-001 "Read README.md and tell me the project name."
./bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 read ag-001
./bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 send ag-001 "Now summarize the test command."
./bin/agentgrid-agent --socket-name agentgrid-codex --registry /tmp/agentgrid-codex-agents.sqlite3 stop ag-001
tmux -L agentgrid-codex kill-server
```

Optional real Codex E2E smoke test:

```sh
AGENTGRID_TEST_REAL_CODEX=1 python3.11 -m pytest agentgrid-agent/tests/e2e/test_codex_adapter_runtime.py -q
```

This test is opt-in because it requires local `codex` credentials, network/model access, and quota. It checks response-only markers that are not present verbatim in the prompts and sends a second related request to the same worker.

Known Codex adapter limitations for V1:

- No semantic task completion detection.
- No Codex approval or waiting-input detection.
- No automatic task result extraction.
- No autonomous build, test, or repair loop.
- Input readiness uses conservative output quiescence until a Codex protocol adapter exists.

## Liveness

Agent liveness is not the same as pane liveness:

- `pane_id` identifies the tmux pane.
- `runtime_pid` identifies the controlled worker process.
- `endpoint_id` identifies the expected controlled endpoint.

An agent is alive only when the pane exists, the runtime process exists, and the endpoint ID matches. If a worker exits inside an existing shell pane, the pane can remain alive while the agent state becomes `STOPPED`.
