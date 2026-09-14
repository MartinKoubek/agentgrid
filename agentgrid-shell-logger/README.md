# agentgrid-shell-logger

`agentgrid-shell-logger` is the standalone Shell Logger for AgentGrid.

It records human shell command activity so later AgentGrid modules can understand what was tried manually, what output was produced, and whether the command succeeded. It does not interpret output, route events, manage agents, or implement project memory.

## Scope

- Run commands and record stdout, stderr, exit code, timestamps, duration, working directory, and optional pane ID.
- Store records in SQLite.
- List recent command records.
- Inspect a single command record.
- Remain independently runnable and testable.

## CLI

From the repository root:

```sh
./bin/agentgrid-shell-logger --help
```

Run and log a command:

```sh
./bin/agentgrid-shell-logger --store /tmp/shell-log.sqlite3 run -- echo hello
```

List recent commands:

```sh
./bin/agentgrid-shell-logger --store /tmp/shell-log.sqlite3 list --json
```

Inspect a command record:

```sh
./bin/agentgrid-shell-logger --store /tmp/shell-log.sqlite3 inspect cmd-001 --json
```

Attach a tmux pane ID when known:

```sh
./bin/agentgrid-shell-logger --store /tmp/shell-log.sqlite3 run --pane %17 -- pytest tests/
```

## Python API

```python
from agentgrid_shell_logger import ShellLogger

logger = ShellLogger("/tmp/shell-log.sqlite3")
record = logger.run(["echo", "hello"])

print(record.exit_code)
print(record.stdout)
```

## Boundary

The Shell Logger records command facts only. Understanding whether output means a task is blocked, complete, or waiting for input belongs to later context, monitor, event, and orchestration modules.
