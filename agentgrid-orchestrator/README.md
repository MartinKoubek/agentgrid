# agentgrid-orchestrator

`agentgrid-orchestrator` is the high-level coordination boundary for AgentGrid.

It receives user requests or dispatched events, asks injected context and routing services what should happen, checks policy, and delegates to injected agent/runtime services. It does not execute tmux commands, persist project memory itself, or implement provider-specific behavior.

## Runtime Composition

`AgentGridRuntime` is the V1 composition root for the deterministic vertical slice. It wires together concrete implementations of tmux, Agent Manager, Monitor, Event Queue, Dispatcher, Project Manager, Project Memory, Project Context Service, Context Router, Policy Engine, and Orchestrator.

The runtime uses the deterministic `fake` agent adapter by default. It can also select the MVP `codex` adapter without changing Orchestrator or Router logic. Claude Code and other providers are not implemented yet.

The Master workflow is an MVP planning layer on top of the same runtime. It asks a Master provider for a small validated routing decision, then executes that decision through the existing Orchestrator and Agent Manager. The deterministic `fake` Master provider is used for CI. The opt-in `codex` Master provider uses the local `codex exec` CLI with a JSON output schema and the versioned rules in `agentgrid_orchestrator/master_instructions.md`.

## CLI

```sh
./bin/agentgrid-orchestrator request "fix failing test" --json
./bin/agentgrid-orchestrator event '{"type":"AGENT_EXITED","agent_id":"ag-001"}' --json
```

Without `--runtime-root`, the standalone CLI uses safe no-op dependencies.

Run the integrated fake-agent runtime path with persistent temporary state:

```sh
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-runtime --socket-name agentgrid-demo open-project demo --path . --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-runtime --socket-name agentgrid-demo request "work on scheduler" --project-id demo --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-runtime --socket-name agentgrid-demo scan --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-runtime --socket-name agentgrid-demo dispatch --json
```

Run the same runtime path with a local Codex worker:

```sh
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-codex-runtime --socket-name agentgrid-codex --agent-adapter codex open-project demo --path /path/to/repo --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-codex-runtime --socket-name agentgrid-codex --agent-adapter codex request "Read README.md and tell me the project name." --project-id demo --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-codex-runtime --socket-name agentgrid-codex --agent-adapter codex scan --json
./bin/agentgrid-orchestrator --runtime-root /tmp/agentgrid-codex-runtime --socket-name agentgrid-codex --agent-adapter codex dispatch --json
```

Clean up the isolated tmux server when finished:

```sh
tmux -L agentgrid-demo kill-server
```

Codex adapter V1 limitations: no semantic completion detection, no approval or waiting-input interpretation, no result extraction, and no autonomous build/test repair loop.

## Master Codex MVP

Prerequisites for a real Master Codex smoke run:

- Local `codex` CLI is installed and authenticated.
- `tmux` can allocate panes on the machine.
- The target project is already registered with `open-project`.
- Use an isolated runtime root and socket for repeatable cleanup.

Register a disposable project:

```sh
runtime=/tmp/agentgrid-master-runtime
socket=agentgrid-master-demo
project=/path/to/repo

./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" --agent-adapter codex open-project demo --path "$project" --json
```

Ask the real Master Codex to plan and delegate the first request to a project Codex worker:

```sh
./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" --agent-adapter codex --master-provider codex master-request "Work on the scheduler tests" --project-id demo --request-id req-001 --json
```

Expected result shape:

```json
{
  "action": "START_AGENT",
  "agent_id": "ag-001",
  "project_id": "demo",
  "details": {
    "request_id": "req-001",
    "master_decision": {
      "action": "START_AGENT",
      "version": 1
    }
  }
}
```

Inspect the worker pane and output:

```sh
./bin/agentgrid-agent --registry "$runtime/agents.sqlite3" inspect ag-001 --json
./bin/tmuxio --socket-name "$socket" read %PANE_ID --lines 100
tmux -L "$socket" attach
```

Run a related follow-up. By default V1 parks continuation because Codex worker readiness is not semantically detected yet:

```sh
./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" --agent-adapter codex --master-provider codex master-request "Add a scheduler DST regression test" --project-id demo --request-id req-002 --json
```

If you have manually inspected the worker and confirmed it is ready, explicitly allow continuation:

```sh
./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" --agent-adapter codex --master-provider codex master-request "Add a scheduler DST regression test" --project-id demo --request-id req-003 --allow-continue --json
```

Run an unrelated request. A valid Master decision may create a second worker instead of reusing `ag-001`:

```sh
./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" --agent-adapter codex --master-provider codex master-request "Investigate database migration" --project-id demo --request-id req-004 --json
```

Review persisted Master decisions:

```sh
./bin/agentgrid-orchestrator --runtime-root "$runtime" --socket-name "$socket" master-history --json
```

Stop workers and clean up:

```sh
./bin/agentgrid-agent --registry "$runtime/agents.sqlite3" stop ag-001 --json
tmux -L "$socket" kill-server
rm -rf "$runtime"
```

Known Master MVP limitations: no autonomous coding loop, no semantic Codex completion detection, no approval/waiting-input parser, no automatic retry of uncertain delivery, no real semantic router, and no provider other than the local Codex CLI for the real Master backend.
