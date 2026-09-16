# AgentGrid Implementation TODO

This document defines the recommended implementation order for AgentGrid modules.

The main goal is to build the system incrementally, keeping every module independently runnable and testable.

Status meanings:

- `DONE`: Implemented and integrated through a tested runtime path.
- `MVP`: Implemented as a standalone module with basic tests, but not fully integrated into production workflows.
- `SKELETON`: Public shape exists, but behavior is intentionally minimal.
- `PLANNED`: Not implemented yet.

## Phase 1 - Terminal and worker foundation

- [DONE] **1. `agentgrid-tmux`**
  - Independent tmux communication layer.
  - Discover sessions, windows, and panes.
  - Read pane output.
  - Write text and keys.
  - Create panes and start processes.
  - Detect whether a pane/process is alive.
  - This is the lowest-level runtime dependency for the first AgentGrid version.

- [DONE] **2. Agent Manager**
  - Give interactive workers stable AgentGrid identities.
  - Map `agent_id` to a runtime endpoint such as a tmux pane.
  - Start, stop, restart, inspect, read from, and write to workers.
  - Support agent adapters so the core remains independent of Codex, Claude Code, or another provider.
  - First adapter should preferably be a deterministic fake/test agent.

- [DONE] **3. Monitor / Event Collector**
  - Observe agents, panes, shells, and processes.
  - Detect runtime changes without requiring the Master to poll everything itself.
  - Produce normalized events such as:
    - `AGENT_STARTED`
    - `AGENT_OUTPUT_CHANGED`
    - `AGENT_EXITED`
    - `PROCESS_EXITED`
    - later `AGENT_WAITING_INPUT`

- [MVP] **4. Shell Logger**
  - Record work performed in human shell panes.
  - Store command, stdout, stderr, exit code, and ordering/timestamps.
  - Make shell history understandable by project agents later.

## Phase 2 - Event processing

- [DONE] **5. Event Queue**
  - Store normalized events from many workers/projects.
  - Support persistence, priority, deduplication, acknowledgment, and parking.
  - Keep event production independent from event processing.

- [DONE] **6. Dispatcher**
  - Deliver queued events to a consumer in a controlled way.
  - Initially deliver one active event at a time.
  - Allow `WAITING_USER` events to be parked so unrelated work can continue.

## Phase 3 - Project model and persistence

- [DONE] **7. Project Manager**
  - Introduce stable project identity.
  - Track repository/path, workspace mapping, historical agent membership, configuration, and last activity.
  - Keep runtime liveness in Agent Manager, not project state.
  - Support opening, listing, restoring, and closing projects.

- [MVP] **8. Persistence Layer**
  - Persist runtime metadata independently of any AI conversation.
  - Store projects, agents, events, queue state, and module state.
  - Start simple; SQLite or another local persistent store is sufficient for V1.

- [MVP] **9. Project Memory**
  - Store long-term project knowledge.
  - Initial categories:
    - Project State
    - Decision Log
    - Lessons Learned
  - Knowledge belongs to the project, not to a single agent session.

## Phase 4 - Context and routing

- [DONE] **10. Project Context Service**
  - Build a compact structured context package for a project.
  - Combine persistent and live context.
  - Sources may include Project Manager, Agent Manager, Project Memory, shell logs, events, Git state, and test state.
  - Support summary and detailed views.

- [DONE] **11. Context Router**
  - Decide where a new request belongs.
  - Possible results:
    - continue an existing agent/thread,
    - start a new agent in the current project,
    - select another existing project,
    - create a new project/workspace.
  - Routing should use project context rather than only pane names or raw terminal text.

## Phase 5 - High-level orchestration

- [MVP] **12. Policy Engine**
  - Provide explicit action decisions:
    - `ALLOW`
    - `ASK_USER`
    - `DENY`
  - Keep approval and safety rules outside the Master reasoning layer.

- [DONE] **13. Orchestrator / Master**
  - Receive user requests and dispatched events.
  - Ask Context Router where work belongs.
  - Request project context.
  - Delegate work through Agent Manager.
  - Consult Policy Engine for actions requiring authorization.
  - The Master should never directly execute tmux commands or act as the only storage of project state.

## Phase 6 - Build, test, and autonomous iteration

- [MVP] **14. Execution / Test Manager**
  - Provide generic build, test, deploy, and verification workflows.
  - Keep platform-specific behavior behind adapters.

- [SKELETON] **15. E2E Driver Adapters**
  - Add project-specific execution adapters as needed.
  - Examples:
    - Android / ADB / Emulator
    - Web / Playwright
    - SSH
    - Docker
    - REST API
  - Allow project agents to perform a full fix-test-iterate loop.

## Phase 7 - Recovery and robustness

- [SKELETON] **16. Recovery Manager**
  - Reconcile persisted AgentGrid state with live runtime state after restart.
  - Rediscover existing tmux panes and running agents where possible.
  - Detect stale registrations and missing resources.
  - Avoid duplicating already-running workers.

- [MVP] **17. Observability / Diagnostics**
  - Centralize structured logging and diagnostics.
  - Make it possible to answer:
    - what happened,
    - where,
    - which project/agent was involved,
    - why an operation failed.
  - Preserve useful failure artifacts for E2E tests.

## Phase 8 - External systems (V2)

- [SKELETON] **18. Connector Framework**
  - Define a generic interface for external systems.
  - Connectors should emit normalized AgentGrid events and expose actions through stable APIs.

- [PLANNED] **19. External Connectors**
  - Add integrations incrementally, for example:
    - Email
    - Slack
    - GitHub
    - Calendar
  - Keep provider-specific logic inside each connector.

- [SKELETON] **20. Cross-system Context Resolution**
  - Associate external events with AgentGrid projects even when the project name is not explicitly present.
  - Use sender, content, history, active work, and Project Memory.
  - Ask the user when confidence is too low.

---

# Recommended first milestones

Milestone status:

- Milestone A through D are implemented for the deterministic fake-agent runtime slice.
- The Codex Agent Adapter is MVP. Codex protocol monitoring, external connectors, platform E2E drivers, and autonomous coding loops remain planned or skeleton work.

## Milestone A - Managed worker

```text
agentgrid-tmux
    -> Agent Manager
    -> deterministic test agent
    -> send input
    -> read output
    -> stop/restart worker
```

## Milestone B - Event-driven runtime

```text
Agent Manager
    -> Monitor/Event Collector
    -> Event Queue
    -> Dispatcher
```

At this point many workers can run in parallel while events are processed independently.

## Milestone C - Project-aware runtime

```text
Project Manager
    -> Persistence
    -> Project Memory
    -> Project Context Service
    -> Context Router
```

At this point AgentGrid understands projects and can decide whether to continue an existing worker or create a new one.

## Milestone D - Master orchestration

```text
User
    -> Master
    -> Context Router
    -> Project Context Service
    -> Agent Manager
    -> worker
```

## Milestone E - Autonomous development loop

```text
worker
    -> edit code
    -> Execution/Test Manager
    -> E2E driver
    -> test result
    -> worker iterates
```

---

# Guiding rule

Each module should be independently runnable and testable before it becomes a dependency of the next module.

Prefer a working vertical path over implementing all modules in parallel.
