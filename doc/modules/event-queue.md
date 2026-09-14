# Event Queue

## Responsibility

Stores events until they can be processed. Many projects and agents may generate events at the same time.

## Responsibilities

- persist pending events
- prioritize
- deduplicate repeated events
- acknowledge completed events
- allow events to be parked

## Example

```text
1. priority 100 - production command requires user approval
2. priority 80  - agent ag-17 waiting for input
3. priority 50  - SSH session disconnected
4. priority 20  - background test finished
```

The queue separates event production from Master processing speed.
