# agentgrid-orchestrator

`agentgrid-orchestrator` is the high-level coordination boundary for AgentGrid.

It receives user requests or dispatched events, asks injected context and routing services what should happen, checks policy, and delegates to injected agent/runtime services. It does not execute tmux commands, persist project memory itself, or implement provider-specific behavior.

## CLI

```sh
./bin/agentgrid-orchestrator request "fix failing test" --json
./bin/agentgrid-orchestrator event '{"type":"AGENT_EXITED","agent_id":"ag-001"}' --json
```

The standalone CLI uses safe no-op dependencies. Real deployments should inject concrete services through Python.
