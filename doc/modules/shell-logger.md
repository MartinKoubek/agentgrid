# Shell Logger

## Responsibility

Records activity performed manually in shell panes so project agents can understand what was tried and whether it succeeded.

## Desired record

```text
COMMAND_START
command: ./gradlew test
timestamp: ...

stdout: ...
stderr: ...
exit_code: 1

COMMAND_END
```

The log should allow later reasoning such as:

```text
This command succeeded.
This command failed.
This exact error occurred.
```

Interactive TUI programs may require a separate strategy because ordinary stdout/stderr logging is not always sufficient.
