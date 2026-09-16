# agentgrid-orchestrator

`agentgrid-orchestrator` is the high-level coordination boundary for AgentGrid.

It receives user requests or dispatched events, asks injected context and routing services what should happen, checks policy, and delegates to injected agent/runtime services. It does not execute tmux commands, persist project memory itself, or implement provider-specific behavior.

## Runtime Composition

`AgentGridRuntime` is the V1 composition root for the deterministic vertical slice. It wires together concrete implementations of tmux, Agent Manager, Monitor, Event Queue, Dispatcher, Project Manager, Project Memory, Project Context Service, Context Router, Policy Engine, and Orchestrator.

The runtime uses the deterministic `fake` agent adapter by default. It can also select the MVP `codex` adapter without changing Orchestrator or Router logic. Claude Code and other providers are not implemented yet.

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
