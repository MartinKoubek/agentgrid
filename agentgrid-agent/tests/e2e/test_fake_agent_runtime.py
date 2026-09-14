from __future__ import annotations

import shutil
import time
import uuid

import pytest
from tmuxio import TmuxClient

from agentgrid_agent.manager import AgentManager
from agentgrid_agent.models import AgentState
from agentgrid_agent.registry import FileAgentRegistry


pytestmark = pytest.mark.e2e


def wait_for_output(manager: AgentManager, agent_id: str, text: str, timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        last_output = manager.read(agent_id)
        if text in last_output:
            return last_output
        time.sleep(0.05)
    raise AssertionError(f"did not find {text!r} in agent output: {last_output!r}")


def test_fake_agent_roundtrip_and_stop(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-agent-test-{uuid.uuid4().hex}"
    tmux = TmuxClient(socket_name=socket_name)
    manager = AgentManager(tmux=tmux, registry=FileAgentRegistry(tmp_path / "agents.json"))

    try:
        agent = manager.start(adapter="fake", session="agentgrid-agents")
        assert agent.id == "ag-001"
        assert agent.pane_id.startswith("%")
        assert agent.state == AgentState.RUNNING

        wait_for_output(manager, agent.id, "FAKE_AGENT_READY")

        manager.send(agent.id, "hello")
        assert "ACK: hello" in wait_for_output(manager, agent.id, "ACK: hello")

        manager.send(agent.id, "exit")
        wait_for_output(manager, agent.id, "BYE")


        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and manager.is_alive(agent.id):
            time.sleep(0.05)
        inspected = manager.inspect(agent.id)
        assert inspected.state == AgentState.STOPPED
    finally:
        tmux.kill_server()
