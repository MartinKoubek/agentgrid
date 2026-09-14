from __future__ import annotations

import shutil
import time
import uuid

import pytest
from agentgrid_agent.adapters import default_adapters
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.registry import FileAgentRegistry
from agentgrid_monitor.models import EventType
from agentgrid_monitor.monitor import Monitor
from tmuxio import TmuxClient


pytestmark = pytest.mark.e2e


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
