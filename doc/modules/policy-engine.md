# Policy Engine

## Responsibility

Determines whether an action may happen automatically.

## Standard result

```text
ALLOW
ASK_USER
DENY
```

## Examples

```text
Run unit tests              -> ALLOW
Restart local worker        -> ALLOW
Delete project directory    -> ASK_USER
Force-push protected branch -> ASK_USER or DENY
```

Policy is separate from the Master so approval and safety behavior is explicit and testable.
