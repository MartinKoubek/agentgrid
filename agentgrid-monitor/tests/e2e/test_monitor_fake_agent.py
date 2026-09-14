from __future__ import annotations

import shutil
import subprocess
import time
import uuid

import pytest
from agentgrid_agent.adapters import default_adapters
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.registry import FileAgentRegistry
from agentgrid_monitor.models import EventType
from agentgrid_monitor.monitor import Monitor
from tmuxio import TmuxClient
from tmuxio.errors import TmuxCommandError


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def require_tmux_can_allocate_panes(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")
    socket_name = f"agentgrid-monitor-preflight-{uuid.uuid4().hex}"
    run_tmux_or_skip(["tmux", "-L", socket_name, "new-session", "-d", "-s", "preflight-env", "bash"])
    tmux = TmuxClient(socket_name=socket_name)
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "preflight-agents.sqlite3"),
        adapters=default_adapters(tmux),
    )
    try:
        agent = manager.start(adapter="fake", session="preflight")
        manager.stop(agent.id)
    except TmuxCommandError as exc:
        if "Device not configured" in str(exc):
            pytest.skip(f"tmux cannot allocate a test pane: {exc}")
        raise
    finally:
        try:
            tmux.kill_server()
        except subprocess.TimeoutExpired:
            pass


def run_tmux_or_skip(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        return
    if "Device not configured" in completed.stderr:
        pytest.skip(f"tmux cannot allocate a test pane: {completed.stderr.strip()}")
    raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, completed.stderr)


def wait_for_event(monitor: Monitor, event_type: EventType, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    last_events = []
    while time.monotonic() < deadline:
        last_events = monitor.scan()
        for event in last_events:
            if event.type == event_type:
                return event
        time.sleep(0.05)
    raise AssertionError(f"did not find {event_type}; last events were {last_events}")


def test_monitor_detects_fake_agent_lifecycle(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-monitor-test-{uuid.uuid4().hex}"
    tmux = TmuxClient(socket_name=socket_name)
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters=default_adapters(tmux),
    )
    monitor = Monitor(agent_manager=manager, state_path=tmp_path / "monitor.sqlite3")

    try:
        agent = manager.start(adapter="fake", session="monitor-agents")

        started = wait_for_event(monitor, EventType.AGENT_STARTED)
        assert started.agent_id == agent.id

        manager.send(agent.id, "hello")
        changed = wait_for_event(monitor, EventType.AGENT_OUTPUT_CHANGED)
        assert changed.agent_id == agent.id

        manager.send(agent.id, "exit")
        exited = wait_for_event(monitor, EventType.AGENT_EXITED)
        assert exited.agent_id == agent.id
    finally:
        tmux.kill_server()
