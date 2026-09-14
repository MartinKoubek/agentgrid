# agentgrid-tmux

`agentgrid-tmux` is the standalone tmux communication layer for AgentGrid.

It knows nothing about AI agents, providers, memory, orchestration, or event routing. Its only job is to discover tmux resources, verify panes are reachable, read from panes, write to panes, stream output, and report state through stable machine-readable interfaces.

## Scope

- Discover tmux sessions, windows, and panes.
- Inspect panes by stable tmux pane ID, such as `%17`.
- Perform non-invasive handshakes by default.
- Optionally perform active handshakes only for controlled AgentGrid-created endpoints.
- Store controlled endpoint IDs in tmux pane option `@agentgrid_endpoint_id`, with process environment lookup as a best-effort fallback where supported.
- Track controlled runtime process IDs separately from pane IDs through `@agentgrid_runtime_pid`.
- Read snapshots through `capture-pane`.
- Follow new output through `pipe-pane`.
- Stop output streaming with `stop-follow`.
- Distinguish text input from key input.

## CLI

The easiest way to run the tool is the checked-in executable script. It is already marked executable with `chmod +x`.

From the repository root:

```sh
./bin/tmuxio panes --json
./bin/tmuxio inspect %17 --json
./bin/tmuxio write %17 "echo hello"
./bin/tmuxio read %17 --lines 50
```

From inside `agentgrid-tmux`, use the local wrapper:

```sh
bin/tmuxio panes --json
bin/tmuxio inspect %17 --json
bin/tmuxio write %17 "echo hello"
bin/tmuxio read %17 --lines 50
```

If executable permissions are lost after copying the file, restore them with:

```sh
chmod +x bin/tmuxio
```

Or install the package and use either `agentgrid-tmux` or `tmuxio`:

```sh
agentgrid-tmux sessions --json
tmuxio sessions --json
agentgrid-tmux windows --json
agentgrid-tmux panes --session work --json
agentgrid-tmux inspect %17 --json
agentgrid-tmux handshake %17 --json
agentgrid-tmux read %17 --lines 50
agentgrid-tmux write %17 "echo hello"
agentgrid-tmux key %17 ENTER
agentgrid-tmux follow %17
agentgrid-tmux stop-follow %17
```

Use `--socket-name` or `--socket-path` to target an isolated tmux server during tests or automation.

## Common Usage

Find pane IDs:

```sh
bin/tmuxio panes --json
```

Inspect one pane without writing to it:

```sh
bin/tmuxio inspect %17 --json
bin/tmuxio handshake %17 --json
```

Read the current pane contents:

```sh
bin/tmuxio read %17
bin/tmuxio read %17 --lines 100
```

Write text and press enter:

```sh
bin/tmuxio write %17 "echo hello"
```

Type text without pressing enter, then press enter separately:

```sh
bin/tmuxio write %17 "echo hello" --no-enter
bin/tmuxio key %17 ENTER
```

Send special keys:

```sh
bin/tmuxio key %17 C-c
bin/tmuxio key %17 ENTER
bin/tmuxio key %17 Escape
```

Start and stop continuous output streaming:

```sh
bin/tmuxio follow %17 --output /tmp/pane.log
bin/tmuxio stop-follow %17
```

Active handshakes report pane liveness separately from controlled worker liveness:

```sh
bin/tmuxio handshake %17 --active --endpoint-id abc123 --json
```

The JSON response includes `pane_alive`, `agent_alive`, `runtime_pid`, `endpoint_id`, and `matched_endpoint_id`.

Use an isolated tmux server:

```sh
tmux -L agentgrid-demo new-session -d -s demo bash
bin/tmuxio --socket-name agentgrid-demo panes --json
bin/tmuxio --socket-name agentgrid-demo write %0 "echo hello"
bin/tmuxio --socket-name agentgrid-demo read %0
tmux -L agentgrid-demo kill-server
```

## Python API

Python package description: `tmuxio` is a provider-neutral tmux communication library for discovering panes, inspecting state, performing safe handshakes, reading terminal snapshots, writing text, sending keys, and starting output streams.

```python
from tmuxio import TmuxClient

tmux = TmuxClient()
pane = tmux.get_pane("%17")

pane.read()
pane.write("ls -la")
pane.send_key("ENTER")
pane.is_alive()
pane.info()

tmux.follow("%17", output_path="/tmp/pane.log")
tmux.stop_follow("%17")
```

## Architectural Rule

No other AgentGrid module should execute tmux commands directly. Everything tmux-related should go through `agentgrid-tmux` so the workspace backend can be replaced later without changing the rest of AgentGrid.
