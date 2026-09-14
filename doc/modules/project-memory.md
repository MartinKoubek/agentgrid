# Project Memory

## Responsibility

Persistent knowledge owned by a project. It must survive agent replacement and restarts.

## Project State

Where work currently stands.

```text
Charging stop bug is implemented.
Unit tests pass.
Android E2E test is still pending.
```

## Decision Log

Important decisions and why they were made.

```text
Decision: charging completion does not terminate pairing.
Reason: pairing represents physical connection, not charging activity.
```

## Lessons Learned

Reusable experience from successful and unsuccessful attempts.

```text
Attempt A failed on emulator API 33.
API 35 worked correctly.
Use API 35 for this E2E scenario.
```

Project Memory belongs to the project, not to an individual Master or worker conversation.
