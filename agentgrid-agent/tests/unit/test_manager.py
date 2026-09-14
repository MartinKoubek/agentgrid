from __future__ import annotations

from tmuxio.models import HandshakeResult, Pane

from agentgrid_agent.manager import AgentManager
from agentgrid_agent.models import AgentState
from agentgrid_agent.registry import FileAgentRegistry


class FakeTmux:
    def __init__(self) -> None:
        self.output = ""
        self.alive = True
        self.writes: list[tuple[str, str]] = []

    def start_process(self, command, session="agentgrid", window=None, cwd=None, endpoint_id=None):
        self.output = "FAKE_AGENT_READY\n"
        return self._pane(command, session, window)

    def start_process_in_pane(self, pane_id, command, endpoint_id=None):
        self.output = "FAKE_AGENT_READY\n"
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

    def handshake(self, pane_id):
        return HandshakeResult(reachable=True, pane_id=pane_id, dead=not self.alive)

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


def test_manager_starts_sends_reads_and_stops_agent(tmp_path) -> None:
    manager = AgentManager(tmux=FakeTmux(), registry=FileAgentRegistry(tmp_path / "agents.json"))

    agent = manager.start(adapter="fake")
    assert agent.id == "ag-001"
    assert agent.state == AgentState.RUNNING

    manager.send(agent.id, "hello")
    assert "ACK: hello" in manager.read(agent.id)

    stopped = manager.stop(agent.id)
    assert stopped.state == AgentState.STOPPED


def test_manager_restarts_with_same_agent_id(tmp_path) -> None:
    tmux = FakeTmux()
    manager = AgentManager(tmux=tmux, registry=FileAgentRegistry(tmp_path / "agents.json"))
    agent = manager.start(adapter="fake")

    restarted = manager.restart(agent.id)

    assert restarted.id == agent.id
    assert restarted.state == AgentState.RUNNING
    assert [saved.id for saved in manager.list()] == ["ag-001"]
