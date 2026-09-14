# Workflows

## New user request

Example request:

```text
Fix the Android login bug.
```

```mermaid
sequenceDiagram
    actor U as User
    participant M as Master
    participant R as Context Router
    participant C as Project Context Service
    participant A as Agent Manager
    participant T as agentgrid-tmux
    participant W as Worker Agent
    participant Q as Event Queue

    U->>M: Fix Android login bug
    M->>R: Resolve target
    R->>C: Get relevant project context
    C-->>R: android-app context
    R-->>M: New worker required
    M->>A: Start worker with task
    A->>T: Create pane / start process
    T-->>A: pane %42
    A->>T: Send initial prompt
    T->>W: Fix Android login bug
    W-->>T: Run emulator E2E? [y/N]
    T-->>Q: AGENT_WAITING_INPUT
    Q-->>M: next event
    M->>A: Send y
    A->>T: Write y
    T->>W: y
    W-->>T: Tests passed. Done.
    T-->>Q: AGENT_FINISHED
```

## Context-aware pane routing

```mermaid
flowchart TD
    REQUEST["New request"] --> ROUTER["Context Router"]
    ROUTER -->|"same task/thread"| CURRENT["Continue existing worker"]
    ROUTER -->|"new task, same project"| NEWPANE["Create new worker pane"]
    ROUTER -->|"other project"| OTHER["Select/open other project"]
```

## Event processing

Workers are parallel; Master event handling is controlled and normally sequential:

```text
workers -> Monitor -> Event Queue -> Dispatcher -> Master
```

`WAITING_USER` events may be parked while unrelated work continues.
