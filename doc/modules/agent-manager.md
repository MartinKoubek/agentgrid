# Agent Manager

## Responsibility

Turns anonymous terminal processes into managed AgentGrid workers with stable identities and lifecycle state.

## Example state

```json
{
  "agent_id": "ag-42",
  "project_id": "android-app",
  "pane_id": "%17",
  "adapter": "codex",
  "state": "RUNNING",
  "task": "Fix login bug"
}
```

## Typical operations

- start / stop / restart agent
- list and inspect agents
- send input to an agent
- read agent output
- map `agent_id` to its runtime endpoint

Example:

```bash
agentgrid-agent send ag-42 "Fix login bug"
```

The Agent Manager resolves `ag-42 -> %17` and delegates terminal I/O to `agentgrid-tmux`.

## Adapters

Provider-specific behavior should live in adapters such as:

```text
fake
codex
claude
other
```

Core AgentGrid should not require any one provider.
