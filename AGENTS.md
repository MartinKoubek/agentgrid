# AGENTS.md - AgentGrid

## Project

AgentGrid is a modular orchestration platform for managing projects, agents, shells, events, and automated workflows.

The project should remain independent of any specific AI provider, model, or agent implementation.

## General Principles

- Keep the architecture modular.
- Prefer clear interfaces between components.
- Avoid unnecessary coupling between modules.
- Keep provider-specific behavior behind adapters.
- Prefer simple solutions over premature complexity.
- Preserve backward compatibility where practical.
- Keep important state outside of the AI model.
- Make failures observable and diagnosable.

## Agent Behavior

When working on this repository:

1. Understand the task before changing code.
2. Inspect the relevant existing implementation first.
3. Make the smallest reasonable change that solves the problem.
4. Avoid unrelated refactoring unless it is required.
5. Follow existing project structure and conventions.
6. Do not introduce provider-specific assumptions into core modules.
7. Explain important architectural changes when they are not obvious.
8. If requirements are ambiguous and the choice could significantly affect the design, ask before making a large change.

## Architecture

AgentGrid should be composed of independent modules communicating through well-defined interfaces.

Core modules should not depend directly on implementation details of:

- tmux
- a specific AI agent
- a specific LLM provider
- external services
- UI implementations

Use adapters where platform-specific behavior is required.

```text
Core
  |
  +-- Agent Adapter
  +-- Workspace Adapter
  +-- Persistence Adapter
  +-- External Service Adapter
```

The exact module structure will evolve as the project develops.

## V1 Module Shape

The first standalone component is `agentgrid-tmux`. Build and maintain it before introducing agents, Master, memory, or event routing.

`agentgrid-tmux` is the only module allowed to execute tmux commands directly. Its job is to discover tmux resources, establish pane reachability, read from panes, write to panes, stream pane output, and report pane state through a stable machine-readable API and CLI. It must know nothing about Codex, AI agents, providers, orchestration, memory, or event routing.

Prefer stable tmux pane IDs such as `%17` over positional targets like `session:3.1`, because indices can move. Distinguish text from keys in public APIs, for example `send_text("hello")` versus `send_key("ENTER")`.

Handshake behavior must be safe by default:

- Level 1 is a non-invasive tmux handshake that verifies pane existence, session, window, process ID, command, TTY, active state, and dead state without sending input.
- Level 2 is an active application handshake only for AgentGrid-created controlled endpoints, such as panes launched with `AGENTGRID_ENDPOINT_ID`. Do not run active handshakes automatically against arbitrary human shells.

Reading behavior should separate snapshots from streams:

- Use tmux `capture-pane` for occasional inspection.
- Use tmux `pipe-pane` for continuous output streams.

The second standalone component is `agentgrid-agent`, the Agent Runtime Manager. Build it on top of `agentgrid-tmux` only, before introducing Master, project memory, queues, or event routing.

`agentgrid-agent` turns a tmux pane into an AgentGrid agent by assigning a stable `agent_id`, storing the `agent_id` to tmux `pane_id` mapping, sending input, reading output, and tracking basic lifecycle state. It should know nothing about projects, Master, memory, queues, or monitoring protocols.

`agentgrid-agent` must never execute tmux commands directly. All tmux interaction must go through `agentgrid-tmux`.

Agent runtime state should stay simple at this layer:

- `STARTING`
- `RUNNING`
- `STOPPED`
- `FAILED`

Agent adapters should define provider-neutral operations such as `start`, `send`, `read`, `is_alive`, and `stop`. Do not add protocol interpretation here, such as deciding whether an agent is asking yes or no, whether a task is complete, or whether output changed. That belongs to the later monitor and event collector layer.

Agent liveness must be separate from tmux pane liveness. Track the controlled worker runtime identity, such as `runtime_pid`, separately from `pane_id`. A pane can stay alive after a worker exits, especially when the worker was launched inside an existing shell pane.

Active handshakes should verify three separate facts: the pane exists, the worker process exists, and the endpoint identity matches. Keep this simple and testable, not a complex IPC protocol.

The agent registry should use concurrency-safe persistence. SQLite is the preferred default for V1 because concurrent starts must not allocate duplicate agent IDs or overwrite state.

Adapter registration must be pluggable through injected or registered adapter maps. Do not hard-code future providers into `AgentManager`.

For V1, keep the system split into a small number of clear modules with one main responsibility each. Do not turn the initial architecture into many independent microservices.

Start with roughly these packages or services:

```text
agentgrid/
  orchestrator/
  projects/
  workspace/
  agents/
  events/
  memory/
  execution/
  cli/
```

Suggested responsibilities:

- `orchestrator/`: Owns main decision-making. Receives user requests and system events, chooses what happens next, and delegates work to project agents. It should not directly manipulate tmux or provider-specific agents.
- `projects/`: Tracks projects and workspaces, including paths, repositories, current state, active agents, and related metadata. Opens, restores, and closes projects.
- `workspace/`: Manages terminal workspaces. For V1 this primarily means tmux sessions, windows, and panes. Keep tmux-specific behavior behind a workspace adapter.
- `agents/`: Manages worker agents and agent adapters. Starts, stops, restarts, and tracks agents, including agent ID, project, task, state, pane, and lifecycle information.
- `events/`: Contains event collection, queueing, and dispatch. Normalize observations into events, persist and deduplicate pending events, and deliver them to the orchestrator without flooding it.
- `memory/`: Owns project memory, knowledge storage, and context retrieval. Persist project state, decision logs, lessons learned, and relevant context for future agent work.
- `execution/`: Runs builds, tests, deployments, validations, and end-to-end driver adapters. Keep Android, Playwright, SSH, Docker, REST, and similar platform drivers out of core modules.
- `cli/`: Provides the human and agent-facing command-line interface, such as `agentgrid status`, `agentgrid projects`, `agentgrid agents`, `agentgrid open`, `agentgrid send`, and `agentgrid logs`.

Additional logical components may exist inside these modules rather than as separate services:

- Context Router decides whether a request should continue an existing agent or thread, create a new agent in the same project, or open another project.
- Monitor observes agents, shells, SSH sessions, builds, and other processes, detecting finished agents, waiting input, crashed processes, and disconnected SSH sessions.
- Shell Logger records human shell activity, ideally including command, stdout, stderr, exit code, and timestamps, so project agents can understand prior manual work.
- Agent Adapter defines provider-neutral operations such as starting an agent, sending a prompt, sending confirmation, reading output, and determining current state.
- Persistence Layer provides storage for projects, agents, events, queue state, memory, and runtime state. Start simple, likely SQLite or filesystem-based storage.
- Policy and Approval Engine returns decisions such as `ALLOW`, `ASK_USER`, or `DENY` for confirmations, destructive commands, Git operations, and other sensitive actions.
- Configuration Manager loads global and per-project configuration for providers, paths, policies, adapters, logging, timeouts, and related settings.
- Observability and Logging provide central diagnostics so it is easy to reconstruct what happened, which project or agent was involved, which event occurred, and why something failed.

## State and Persistence

Important runtime and project state should be explicit and persistable.

Do not rely on an AI agent's conversation history as the only source of truth.

Examples of state that may need persistence:

- projects
- agents
- tasks
- events
- workflow state
- decisions
- project context

Persistence details will be defined as the project evolves.

## Testing

Changes should be tested at the appropriate level.

Prefer:

- unit tests for isolated logic
- integration tests for module boundaries
- end-to-end tests for important workflows

For bug fixes, add a regression test when practical.

Do not claim a workflow works end-to-end unless it was actually exercised end-to-end.

Avoid tests that depend unnecessarily on:

- remote AI services
- nondeterministic model output
- external infrastructure
- fixed timing assumptions

Use deterministic test doubles or local fixtures where appropriate.

## End-to-End Philosophy

Important AgentGrid workflows should eventually be testable from the same interfaces used by real users or agents.

Examples may include:

- opening a project
- starting an agent
- sending work to an existing agent
- creating a new agent for unrelated work
- handling events
- waiting for user input
- running shell commands
- restoring state after restart

Detailed end-to-end scenarios will be specified later.

## Error Handling

- Fail clearly.
- Preserve useful diagnostic information.
- Do not silently ignore unexpected states.
- Include enough context in errors to identify the affected project, agent, task, or component.
- Prefer structured errors and events where practical.

## Logging

Logs should help answer:

- what happened
- where it happened
- which project or agent was involved
- whether the operation succeeded
- why it failed

Avoid logging secrets or sensitive credentials.

## Security

- Never hard-code secrets.
- Do not commit credentials, tokens, or API keys.
- Treat external commands and agent-generated actions as potentially unsafe.
- Destructive or irreversible actions should be explicit.
- Additional policy and approval rules will be defined later.

## Documentation

- Keep documentation concise and close to the implementation.
- When introducing a new public interface, module, or important behavior, update the relevant documentation.
- Avoid documenting speculative behavior as if it already exists.

## Definition of Done

A change is complete when:

- the requested behavior is implemented
- relevant tests pass
- obvious regressions have been considered
- important errors are handled
- code fits the existing architecture
- documentation is updated when necessary

More specific project rules and testing requirements will be added as AgentGrid evolves.
