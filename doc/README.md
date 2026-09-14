# AgentGrid Documentation

AgentGrid is a modular orchestration platform for projects, interactive agents, shells, events, project context, and automated workflows.

The design is intentionally independent of a specific AI provider. Codex, Claude Code, shells, SSH sessions, and future workers are integrated through adapters.

## Documentation map

- [Architecture](architecture.md) - high-level design and communication rules.
- [Workflows](workflows.md) - example end-to-end flows.
- [Roadmap](roadmap.md) - recommended implementation order and V2 direction.

### Modules

- [`agentgrid-tmux`](modules/agentgrid-tmux.md) - tmux discovery and terminal I/O.
- [Agent Manager](modules/agent-manager.md) - worker identity and lifecycle.
- [Project Manager](modules/project-manager.md) - project/workspace metadata.
- [Project Memory](modules/project-memory.md) - project state, decisions, and lessons learned.
- [Project Context Service](modules/project-context-service.md) - compact context for Master/agents.
- [Context Router](modules/context-router.md) - route a request to an existing/new agent or project.
- [Monitor / Event Collector](modules/monitor-event-collector.md) - observe runtime changes and emit events.
- [Shell Logger](modules/shell-logger.md) - record commands, output, and exit codes.
- [Event Queue](modules/event-queue.md) - store, prioritize, and deduplicate events.
- [Dispatcher](modules/dispatcher.md) - deliver queued work to the Master sequentially.
- [Policy Engine](modules/policy-engine.md) - ALLOW / ASK_USER / DENY decisions.
- [Execution / Test Manager](modules/execution-test-manager.md) - build, deploy, test, and E2E adapters.
- [Orchestrator / Master](modules/orchestrator-master.md) - high-level reasoning and coordination.

## Core rule

Infrastructure details stay behind adapters. In particular, no module except `agentgrid-tmux` should execute tmux commands directly.

## Current maturity

- DONE: the deterministic fake-agent vertical runtime slice is wired through Orchestrator, Project Context Service, Context Router, Agent Manager, `agentgrid-tmux`, Monitor, Event Queue, and Dispatcher.
- DONE: project agent membership is separated from Agent Manager runtime liveness.
- MVP: standalone services such as Shell Logger, Project Memory, Policy, Persistence, Execution, and Observability expose basic local behavior and tests.
- SKELETON: advanced recovery, connector framework, cross-system context, and platform E2E drivers are intentionally minimal.
- PLANNED: real Codex worker integration, Claude adapters, Gmail, Slack, GitHub, Calendar, semantic search, and autonomous coding loops are not implemented.

## Validation

Run the same checks used by CI from the repository root:

```sh
./bin/test-all
```
