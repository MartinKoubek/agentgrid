# Dispatcher

## Responsibility

Delivers queued events to the Master in a controlled manner.

Many workers can run in parallel while the Master processes one active issue at a time.

```mermaid
sequenceDiagram
    participant E as Event Collector
    participant Q as Event Queue
    participant D as Dispatcher
    participant M as Master

    E->>Q: Event A
    E->>Q: Event B
    E->>Q: Event C
    D->>Q: Get next event
    Q-->>D: Event A
    D->>M: Event A
    Note over M: Master processes Event A
    M-->>D: Done
    D->>Q: Get next event
    Q-->>D: Event B
    D->>M: Event B
```

An event waiting for the user should be parkable so unrelated work can continue.
