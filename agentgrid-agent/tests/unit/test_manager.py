from __future__ import annotations

from tmuxio.models import HandshakeResult, Pane

from agentgrid_agent.adapters.fake import FakeAgentAdapter
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.models import AgentState
from agentgrid_agent.registry import FileAgentRegistry


class FakeTmux:
    def __init__(self) -> None:
        self.output = ""
        self.alive = True
        self.endpoint_id: str | None = None
        self.runtime_pid = 456
        self.writes: list[tuple[str, str]] = []

    def start_process(self, command, session="agentgrid", window=None, cwd=None, endpoint_id=None):
        self.output = "FAKE_AGENT_READY\n"
        self.endpoint_id = endpoint_id
        return self._pane(command, session, window)

    def start_process_in_pane(self, pane_id, command, endpoint_id=None, require_idle_shell=True):
        self.output = "FAKE_AGENT_READY\n"
        self.endpoint_id = endpoint_id
        return self._pane(command, "existing", "existing")

    def get_pane(self, pane_id):
        return object()

    def write(self, pane_id, text, enter=True):
        self.writes.append((pane_id, text))
        if text == "exit":
            self.output += "BYE\n"
            self.alive = False
        else:
            self.output += f"ACK: {text}\n"

    def read(self, pane_id):
        return self.output

    def handshake(self, pane_id, active=False, expected_endpoint_id=None):
        return HandshakeResult(
            reachable=True,
            pane_id=pane_id,
            pane_alive=True,
            agent_alive=self.alive,
            runtime_pid=self.runtime_pid,
            endpoint_id=self.endpoint_id,
            expected_endpoint_id=expected_endpoint_id,
            matched_endpoint_id=self.alive and self.endpoint_id == expected_endpoint_id,
            dead=False,
        )

    def _pane(self, command, session, window):
        return Pane(
            pane_id="%1",
            session=session,
            window=window or "ag-001",
            window_id="@1",
            window_index=0,
            pane_index=0,
            pid=123,
            command=command,
            tty="/dev/ttys001",
            active=True,
            dead=not self.alive,
            current_path="/tmp",
            title="fake",
        )


class DisappearingTmux(FakeTmux):
    def handshake(self, pane_id, active=False, expected_endpoint_id=None):
        if not self.alive:
            return HandshakeResult(
                reachable=False,
                pane_id=pane_id,
                pane_alive=False,
                agent_alive=False,
                expected_endpoint_id=expected_endpoint_id,
                error="server exited unexpectedly",
            )
        return super().handshake(pane_id, active=active, expected_endpoint_id=expected_endpoint_id)


def test_manager_starts_sends_reads_and_stops_agent(tmp_path) -> None:
    tmux = FakeTmux()
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"fake": FakeAgentAdapter(tmux)},
    )

    agent = manager.start(adapter="fake")
    assert agent.id == "ag-001"
    assert agent.state == AgentState.RUNNING

    manager.send(agent.id, "hello")
    assert "ACK: hello" in manager.read(agent.id)

    stopped = manager.stop(agent.id)
    assert stopped.state == AgentState.STOPPED


def test_manager_restarts_with_same_agent_id(tmp_path) -> None:
    tmux = FakeTmux()
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"fake": FakeAgentAdapter(tmux)},
    )
    agent = manager.start(adapter="fake")

    restarted = manager.restart(agent.id)

    assert restarted.id == agent.id
    assert restarted.state == AgentState.RUNNING
    assert [saved.id for saved in manager.list()] == ["ag-001"]


def test_manager_uses_registered_adapter_map(tmp_path) -> None:
    tmux = FakeTmux()
    adapter = FakeAgentAdapter(tmux)
    manager = AgentManager(tmux=tmux, registry=FileAgentRegistry(tmp_path / "agents.sqlite3"), adapters={})

    manager.register_adapter("fake", adapter)
    agent = manager.start(adapter="fake")

    assert agent.adapter == "fake"
    assert agent.state == AgentState.RUNNING


def test_manager_detects_runtime_pid_mismatch(tmp_path) -> None:
    tmux = FakeTmux()
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"fake": FakeAgentAdapter(tmux)},
    )
    agent = manager.start(adapter="fake")

    tmux.runtime_pid = 999

    assert manager.is_alive(agent.id) is False
    assert manager.inspect(agent.id).state == AgentState.STOPPED


def test_manager_marks_stopped_when_endpoint_disappears_after_exit(tmp_path) -> None:
    tmux = DisappearingTmux()
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"fake": FakeAgentAdapter(tmux)},
    )
    agent = manager.start(adapter="fake")

    manager.send(agent.id, "exit")

    assert manager.is_alive(agent.id) is False
    assert manager.inspect(agent.id).state == AgentState.STOPPED


def test_manager_stop_marks_stopped_when_endpoint_disappears(tmp_path) -> None:
    tmux = DisappearingTmux()
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters={"fake": FakeAgentAdapter(tmux)},
    )
    agent = manager.start(adapter="fake")

    stopped = manager.stop(agent.id)

    assert stopped.state == AgentState.STOPPED
