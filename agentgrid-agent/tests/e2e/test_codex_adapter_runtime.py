from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid

import pytest
from tmuxio import TmuxClient
from tmuxio.errors import TmuxCommandError

from agentgrid_agent.adapters import default_adapters
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.models import AgentState
from agentgrid_agent.registry import FileAgentRegistry


pytestmark = pytest.mark.e2e


def run_tmux_or_skip(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode == 0:
        return
    if "Device not configured" in completed.stderr:
        pytest.skip(f"tmux cannot allocate a test pane: {completed.stderr.strip()}")
    raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, completed.stderr)


def wait_for_output(manager: AgentManager, agent_id: str, text: str, timeout: float = 20.0) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        last_output = manager.read(agent_id)
        if text in last_output:
            return last_output
        time.sleep(0.1)
    raise AssertionError(f"did not find {text!r} in Codex output: {last_output!r}")


@pytest.mark.skipif(os.environ.get("AGENTGRID_TEST_REAL_CODEX") != "1", reason="real Codex smoke test is opt-in")
def test_real_codex_adapter_can_start_send_read_and_stop(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")
    if shutil.which("codex") is None:
        pytest.skip("codex CLI is not installed")

    socket_name = f"agentgrid-codex-test-{uuid.uuid4().hex}"
    run_tmux_or_skip(["tmux", "-L", socket_name, "new-session", "-d", "-s", "preflight-env", "bash"])
    tmux = TmuxClient(socket_name=socket_name)
    manager = AgentManager(
        tmux=tmux,
        registry=FileAgentRegistry(tmp_path / "agents.sqlite3"),
        adapters=default_adapters(tmux),
    )

    try:
        agent = manager.start(adapter="codex", session="codex-agents", cwd=str(tmp_path))
        assert agent.state == AgentState.RUNNING
        assert agent.runtime_pid is not None

        manager.send(agent.id, "Say exactly AGENTGRID_CODEX_SMOKE_READY and then stop.")
        wait_for_output(manager, agent.id, "AGENTGRID_CODEX_SMOKE_READY")

        stopped = manager.stop(agent.id)
        assert stopped.state == AgentState.STOPPED
    except TmuxCommandError as exc:
        if "Device not configured" in str(exc):
            pytest.skip(f"tmux cannot allocate a test pane: {exc}")
        raise
    finally:
        try:
            tmux.kill_server()
        except subprocess.TimeoutExpired:
            pass
