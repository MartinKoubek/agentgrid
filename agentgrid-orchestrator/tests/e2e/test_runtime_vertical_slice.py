from __future__ import annotations

import shutil
import subprocess
import time
import uuid

import pytest
from agentgrid_agent.models import AgentState
from agentgrid_dispatcher import DispatchDecision
from agentgrid_event_queue import EventStatus
from agentgrid_orchestrator.runtime import AgentGridRuntime
from tmuxio.errors import TmuxCommandError


pytestmark = pytest.mark.e2e


def wait_for_output(runtime: AgentGridRuntime, agent_id: str, text: str, timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        last_output = runtime.agent_manager.read(agent_id)
        if text in last_output:
            return last_output
        time.sleep(0.05)
    raise AssertionError(f"did not find {text!r} in output: {last_output!r}")


def wait_for_stopped(runtime: AgentGridRuntime, agent_id: str, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not runtime.agent_manager.is_alive(agent_id):
            return
        time.sleep(0.05)
    raise AssertionError(f"agent did not stop: {agent_id}")


def require_tmux_runtime(tmp_path, socket_name: str) -> None:
    run_tmux_or_skip(["tmux", "-L", socket_name, "new-session", "-d", "-s", "preflight-env", "bash"])
    runtime = AgentGridRuntime(tmp_path / "preflight-runtime", socket_name=socket_name)
    try:
        agent = runtime.agent_manager.start(adapter="fake", session="agentgrid-preflight")
        runtime.agent_manager.stop(agent.id)
    except TmuxCommandError as exc:
        if "Device not configured" in str(exc):
            pytest.skip(f"tmux cannot allocate a test pane: {exc}")
        raise
    finally:
        try:
            runtime.tmux.kill_server()
        except subprocess.TimeoutExpired:
            pass


def run_tmux_or_skip(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        return
    if "Device not configured" in completed.stderr:
        pytest.skip(f"tmux cannot allocate a test pane: {completed.stderr.strip()}")
    raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, completed.stderr)


def dispatch_all(runtime: AgentGridRuntime) -> list[str]:
    event_ids = []
    while True:
        result = runtime.dispatch_next()
        if not result.delivered:
            return event_ids
        assert result.decision == DispatchDecision.ACK
        assert result.event_id is not None
        event_ids.append(result.event_id)


def test_runtime_vertical_slice_start_continue_queue_dispatch_and_exit(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-runtime-test-{uuid.uuid4().hex}"
    require_tmux_runtime(tmp_path, socket_name)
    runtime = AgentGridRuntime(tmp_path / "runtime", socket_name=socket_name)
    project_path = tmp_path / "project"
    project_path.mkdir()

    try:
        assert runtime.agent_manager.tmux is runtime.tmux
        assert runtime.monitor.agent_manager is runtime.agent_manager

        runtime.project_manager.open_project("project-a", str(project_path), name="Project A")

        first = runtime.orchestrator.handle_request("work on scheduler", "project-a")
        assert first.action == "START_AGENT"
        assert first.agent_id == "ag-001"
        wait_for_output(runtime, first.agent_id, "ACK: work on scheduler")

        first_agent = runtime.agent_manager.inspect(first.agent_id)
        assert first_agent.pane_id.startswith("%")
        assert first_agent.runtime_pid is not None
        assert runtime.project_owner_for_agent(first.agent_id) == "project-a"

        started_records = runtime.enqueue_monitor_events()
        assert started_records
        assert any(record.type == "AGENT_STARTED" for record in runtime.event_queue.list())
        processed = dispatch_all(runtime)
        assert processed

        second = runtime.orchestrator.handle_request("add scheduler test", "project-a")
        assert second.action == "CONTINUE_AGENT"
        assert second.agent_id == first.agent_id
        assert len(runtime.agent_manager.list()) == 1
        wait_for_output(runtime, first.agent_id, "ACK: add scheduler test")

        output_records = runtime.enqueue_monitor_events()
        assert any(record.type == "AGENT_OUTPUT_CHANGED" for record in output_records)
        dispatch_all(runtime)

        context = runtime.project_context.get_context("project-a")
        assert [agent["id"] for agent in context.agents] == [first.agent_id]

        runtime.agent_manager.send(first.agent_id, "exit")
        wait_for_output(runtime, first.agent_id, "BYE")
        wait_for_stopped(runtime, first.agent_id)

        exit_records = runtime.enqueue_monitor_events()
        assert any(record.type == "AGENT_EXITED" for record in exit_records)
        dispatch_all(runtime)

        project = runtime.project_manager.get_project("project-a")
        events = runtime.event_queue.list(limit=100)
        assert len(runtime.project_manager.list_projects()) == 1
        assert project.agents == [first.agent_id]
        assert runtime.agent_manager.inspect(first.agent_id).state == AgentState.STOPPED
        assert runtime.project_owner_for_agent(first.agent_id) == "project-a"
        assert events
        assert all(event.status == EventStatus.ACKED for event in events)
    finally:
        runtime.tmux.kill_server()


def test_runtime_starts_new_agent_for_unrelated_task(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-routing-test-{uuid.uuid4().hex}"
    require_tmux_runtime(tmp_path, socket_name)
    runtime = AgentGridRuntime(tmp_path / "runtime", socket_name=socket_name)
    project_path = tmp_path / "project"
    project_path.mkdir()

    try:
        assert runtime.agent_manager.tmux is runtime.tmux

        runtime.project_manager.open_project("project-a", str(project_path), name="Project A")

        first = runtime.orchestrator.handle_request("work on scheduler", "project-a")
        assert first.action == "START_AGENT"
        assert first.agent_id == "ag-001"
        wait_for_output(runtime, first.agent_id, "ACK: work on scheduler")

        second = runtime.orchestrator.handle_request("investigate database migration", "project-a")
        assert second.action == "START_AGENT"
        assert second.agent_id == "ag-002"
        wait_for_output(runtime, second.agent_id, "ACK: investigate database migration")

        project = runtime.project_manager.get_project("project-a")
        assert project.agents == ["ag-001", "ag-002"]
        assert len(runtime.agent_manager.list()) == 2
    finally:
        for agent in runtime.agent_manager.list():
            if agent.state == AgentState.RUNNING:
                runtime.agent_manager.stop(agent.id)
        runtime.tmux.kill_server()
