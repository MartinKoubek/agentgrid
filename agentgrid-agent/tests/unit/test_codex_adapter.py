from __future__ import annotations

import pytest

from agentgrid_agent.adapters import CodexAgentAdapter, default_adapters
from agentgrid_agent.models import Agent, AgentConfig, AgentState
from tmuxio.models import HandshakeResult


class FakeTmux:
    def __init__(self) -> None:
        self.output = "CODEX_READY\n"
        self.writes: list[tuple[str, str, bool]] = []
        self.texts: list[tuple[str, str]] = []
        self.keys: list[tuple[str, str]] = []
        self.started = []
        self.handshake_result = HandshakeResult(
            reachable=True,
            pane_id="%1",
            pane_alive=True,
            agent_alive=True,
            runtime_pid=456,
            endpoint_id="endpoint-1",
            expected_endpoint_id="endpoint-1",
            matched_endpoint_id=True,
        )

    def write(self, pane_id: str, text: str, enter: bool = True) -> None:
        self.writes.append((pane_id, text, enter))
        self.output += text + "\n"

    def send_text(self, pane_id: str, text: str) -> None:
        self.texts.append((pane_id, text))
        self.output += text

    def read(self, pane_id: str) -> str:
        return self.output

    def send_key(self, pane_id: str, key: str) -> None:
        self.keys.append((pane_id, key))

    def handshake(self, pane_id: str, active: bool = False, expected_endpoint_id: str | None = None):
        return self.handshake_result

    def start_process(self, command, session="agentgrid", window=None, cwd=None, endpoint_id=None):
        self.started.append(
            {
                "command": command,
                "session": session,
                "window": window,
                "cwd": cwd,
                "endpoint_id": endpoint_id,
            }
        )
        return type(
            "Pane",
            (),
            {"pane_id": "%1", "pid": 123, "session": session, "window": window or "ag-001"},
        )()

    def get_pane(self, pane_id: str):
        return object()


def codex_agent() -> Agent:
    return Agent(
        id="ag-001",
        adapter="codex",
        pane_id="%1",
        pid=123,
        runtime_pid=456,
        endpoint_id="endpoint-1",
        state=AgentState.RUNNING,
    )


def test_default_adapters_include_fake_and_codex() -> None:
    adapters = default_adapters(FakeTmux())

    assert "fake" in adapters
    assert isinstance(adapters["codex"], CodexAgentAdapter)


def test_codex_command_uses_documented_cli_flags(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda executable: f"/usr/bin/{executable}")
    adapter = CodexAgentAdapter(
        FakeTmux(),
        executable="codex",
        approval_policy="on-request",
        sandbox="workspace-write",
        extra_args=["--model", "gpt-test"],
    )

    command = adapter.default_command()

    assert command == "/usr/bin/codex --no-alt-screen --ask-for-approval on-request --sandbox workspace-write --model gpt-test"


def test_codex_command_reports_missing_executable(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda executable: None)
    adapter = CodexAgentAdapter(FakeTmux(), executable="missing-codex")

    with pytest.raises(FileNotFoundError, match="missing-codex"):
        adapter.default_command()


def test_codex_start_uses_agent_manager_tmux_process_and_cwd(monkeypatch, tmp_path) -> None:
    from agentgrid_agent.manager import AgentManager
    from agentgrid_agent.registry import FileAgentRegistry

    tmux = FakeTmux()
    monkeypatch.setattr("shutil.which", lambda executable: f"/usr/bin/{executable}")
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"codex": CodexAgentAdapter(tmux)},
    )

    agent = manager.start(adapter="codex", cwd="/repo/project")

    assert agent.adapter == "codex"
    assert agent.state == AgentState.RUNNING
    assert tmux.started[0]["cwd"] == "/repo/project"
    assert tmux.started[0]["command"].startswith("/usr/bin/codex --no-alt-screen")


def test_codex_send_supports_multiline_prompts() -> None:
    tmux = FakeTmux()
    adapter = CodexAgentAdapter(tmux)
    prompt = "Update scheduler.py.\nAdd tests for DST changes.\nRun tests."

    adapter.send(codex_agent(), prompt)

    assert tmux.texts == [("%1", prompt)]
    assert tmux.keys == [("%1", "ENTER")]


def test_codex_read_delegates_to_tmux_capture() -> None:
    adapter = CodexAgentAdapter(FakeTmux())

    assert adapter.read(codex_agent()) == "CODEX_READY\n"


def test_codex_liveness_uses_endpoint_runtime_identity() -> None:
    adapter = CodexAgentAdapter(FakeTmux())

    assert adapter.is_alive(codex_agent()) is True


def test_codex_liveness_rejects_runtime_pid_mismatch() -> None:
    tmux = FakeTmux()
    tmux.handshake_result = HandshakeResult(
        reachable=True,
        pane_id="%1",
        pane_alive=True,
        agent_alive=True,
        runtime_pid=999,
        endpoint_id="endpoint-1",
        expected_endpoint_id="endpoint-1",
        matched_endpoint_id=True,
    )
    adapter = CodexAgentAdapter(tmux)

    assert adapter.is_alive(codex_agent()) is False


def test_codex_stop_sends_interrupt_when_alive() -> None:
    tmux = FakeTmux()
    adapter = CodexAgentAdapter(tmux)

    adapter.stop(codex_agent())

    assert tmux.keys == [("%1", "C-c"), ("%1", "C-d")]


def test_codex_stop_does_nothing_when_not_alive() -> None:
    tmux = FakeTmux()
    tmux.handshake_result = HandshakeResult(
        reachable=False,
        pane_id="%1",
        pane_alive=False,
        agent_alive=False,
        runtime_pid=None,
        matched_endpoint_id=False,
    )
    adapter = CodexAgentAdapter(tmux)

    adapter.stop(codex_agent())

    assert tmux.keys == []
