# Architecture

## Design goals

- Modules can be started, tested, and developed independently.
- Modules communicate through clear APIs and structured data.
- Core modules do not depend on a specific AI provider.
- tmux-specific behavior is isolated behind `agentgrid-tmux`.
- Important state is persisted outside AI conversations.
- The Master receives compact context instead of reading every pane and log directly.
- Many workers may run in parallel while the Master processes events in a controlled sequence.

## High-level architecture

```mermaid
flowchart TD
    USER["User / CLI"]
    MASTER["Orchestrator / Master"]
    ROUTER["Context Router"]
    PROJECT["Project Manager"]
    CONTEXT["Project Context Service"]
    MEMORY["Project Memory"]
    AGENT["Agent Manager"]
    TMUXAPI["agentgrid-tmux"]
    TMUX["tmux"]
    MONITOR["Monitor / Event Collector"]
    QUEUE["Event Queue"]
    DISPATCH["Dispatcher"]
    POLICY["Policy Engine"]
    EXEC["Execution / Test Manager"]

    USER --> MASTER
    MASTER --> ROUTER
    ROUTER --> PROJECT
    ROUTER --> CONTEXT
    CONTEXT --> PROJECT
    CONTEXT --> MEMORY
    CONTEXT --> AGENT
    ROUTER --> AGENT
    MASTER --> AGENT
    AGENT --> TMUXAPI
    TMUXAPI --> TMUX
    TMUXAPI --> MONITOR
    MONITOR --> QUEUE
    QUEUE --> DISPATCH
    DISPATCH --> MASTER
    MASTER --> POLICY
    MASTER --> CONTEXT
    MASTER --> EXEC
```

## Runtime composition

`agentgrid-orchestrator/agentgrid_orchestrator/runtime.py` is the current composition root. It is allowed to instantiate concrete module implementations and wire them together while lower-level modules keep depending on their direct interfaces.

The implemented V1 vertical slice uses the deterministic `fake` agent adapter by default:

```text
User request
    -> Orchestrator
    -> Project Context Service
    -> Context Router
    -> Agent Manager
    -> agentgrid-tmux
    -> Fake Agent
```

Runtime observations use the event path:

```text
Fake Agent / runtime
    -> Monitor
    -> Event Queue
    -> Dispatcher
    -> Orchestrator
```

The MVP `codex` adapter can replace the fake adapter at the Agent Manager boundary and run the local Codex CLI in tmux. Codex-specific protocol parsing, semantic completion detection, and approval-state interpretation are not implemented yet.

## Core communication principle

```mermaid
flowchart LR
    MASTER["Master"] --> AGENT["Agent Manager"]
    AGENT --> TMUXAPI["agentgrid-tmux"]
    TMUXAPI --> TMUX["tmux"]
    TMUX --> PROC["Agent / Shell / SSH / Tool"]
```

The same rule applies to other infrastructure: GitHub, Android, browsers, external services, and AI providers should be hidden behind adapters rather than embedded in core modules.

## Live vs persistent context

```mermaid
flowchart LR
    PERSIST["Persistent\nProject State\nDecision Log\nLessons Learned"]
    LIVE["Live\nAgents\nPanes\nEvents\nShells\nTests\nGit state"]
    CONTEXT["Project Context Service"]
    MASTER["Master"]

    PERSIST --> CONTEXT
    LIVE --> CONTEXT
    CONTEXT --> MASTER
```

The Master is a consumer of project context, not the source of truth.
