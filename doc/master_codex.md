# One-command Master Codex launcher

`bin/master_codex` starts or reattaches a dedicated AgentGrid-owned interactive Codex Master TUI in an isolated tmux session. The ordinary path is now a real persistent Codex session, not the legacy `master>` shell and not one `codex exec` call per user message.

Quick start from any project:

```sh
export PATH="/absolute/path/to/agentgrid/bin:$PATH"
cd /path/to/project
master_codex
```

When run inside a Git repository, the launcher registers the Git root as the selected project. Use `--project /path/to/disposable-repo` to target another existing directory, including an explicit non-Git disposable test directory. Startup does not initialize Git or modify project files.

Prerequisites: `python3.11`, `tmux`, and an installed/authenticated `codex` CLI. The launcher uses documented interactive Codex flags: `codex -C <agentgrid-repo> --sandbox workspace-write --ask-for-approval on-request --no-alt-screen <bootstrap-prompt>`. It checks `codex --version` and `codex doctor --summary --no-color --ascii` before opening a real Master session. Help, `--status`, and `--fake --once` do not require Codex credentials.

The Master runs with CWD set to the AgentGrid repository so the repo-scoped `.agents/skills/agentgrid/SKILL.md` is discoverable. The bootstrap prompt and JSON context identify the selected target project, runtime root, tmux socket, worker adapter, and helper script. The Master should use `.agents/skills/agentgrid/scripts/agentgrid.py` to inspect projects/workers, start or reuse workers, read output, scan/dispatch events, and stop scoped workers.

Useful commands:

```sh
master_codex --status
master_codex --project /path/to/disposable-repo
AGENTGRID_MASTER_NO_ATTACH=1 master_codex --project /path/to/repo
master_codex --fake --once "Read README.md"
```

Runtime defaults are separated by provider: `${XDG_STATE_HOME:-$HOME/.local/state}/agentgrid/master-codex` for real Codex and `${XDG_STATE_HOME:-$HOME/.local/state}/agentgrid/master-fake` for deterministic fake tests. The default tmux socket is `agentgrid-master-$(id -u)`. Use `--runtime-root DIR` and `--socket-name NAME` to isolate a pilot. The monitor/dispatcher observer runs in an `agentgrid-master:observer` tmux window while the Master session exists; it stores logs in `<runtime-root>/monitor.log` and does not make Codex autonomous or wake an idle Master.

Detach from the Master TUI with `Ctrl+B`, then `D`. Detaching or exiting the Master leaves worker panes running. Re-running `master_codex` reattaches the existing `agentgrid-master:master` pane when it exists; if the Master tmux session is gone, the launcher starts a new interactive Codex Master and preserves AgentGrid project/worker state. Conversation context is not restored unless Codex itself supports that in the visible TUI session.

Inspect or stop a worker manually:

```sh
./bin/agentgrid-agent --registry <runtime-root>/agents.sqlite3 --socket-name <socket-name> inspect ag-001 --json
./bin/agentgrid-agent --registry <runtime-root>/agents.sqlite3 --socket-name <socket-name> read ag-001
./bin/agentgrid-agent --registry <runtime-root>/agents.sqlite3 --socket-name <socket-name> stop ag-001 --json
```

Safety: first test on a disposable repository. Workers use the Codex adapter's workspace-write sandbox with on-request approval. Master coordination must go through the AgentGrid skill helper and existing policy boundary before starting workers or sending bytes. `--once` remains as a deterministic legacy/API path for tests and returns nonzero for denied, failed, rejected, or parked requests while preserving decision JSON on stdout.

Known limitations: no Codex semantic completion detection, no approval/waiting-input parser, no automatic readiness detection, no idle Master wake-up, no automatic retry of uncertain delivery, and no autonomous build/test repair loop. Fake E2E tests validate infrastructure only; a real Master/worker pilot requires an authenticated local Codex CLI.
