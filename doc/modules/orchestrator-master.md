# Orchestrator / Master

## Responsibility

High-level reasoning and coordination.

The Master decides what should happen; infrastructure work is delegated to specialized modules.

## Responsibilities

- receive user requests
- receive dispatched system events
- ask Context Router where work belongs
- request compact project context
- delegate work to agents
- consult Policy Engine
- request builds/tests from Execution Manager
- present decisions and questions to the user

## The Master should not

- execute raw tmux commands
- be the only storage of project knowledge
- continuously poll all terminal panes
- directly implement provider-specific behavior

The Master should be restartable or replaceable without losing project state.
