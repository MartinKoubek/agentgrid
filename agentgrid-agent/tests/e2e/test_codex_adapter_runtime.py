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


def wait_for_new_output_marker(
    manager: AgentManager,
    agent_id: str,
    marker: str,
    baseline: str,
    timeout: float = 120.0,
) -> str:
    deadline = time.monotonic() + timeout
    last_output = baseline
    while time.monotonic() < deadline:
        last_output = manager.read(agent_id)
        new_output = last_output[len(baseline) :] if last_output.startswith(baseline) else last_output
        if marker in new_output:
            return last_output
        time.sleep(0.5)
    raise AssertionError(
        f"did not find response marker {marker!r} in new Codex output. "
        f"Last output was:\n{last_output}"
    )


def test_wait_for_new_output_marker_rejects_marker_from_prompt_echo_only() -> None:
    class EchoOnlyManager:
        def read(self, agent_id: str) -> str:
            return "prompt echo contains AGENTGRID-CODEX-SMOKE-ONE"

    with pytest.raises(AssertionError, match="response marker"):
        wait_for_new_output_marker(
            EchoOnlyManager(),
            "ag-001",
            "AGENTGRID-CODEX-SMOKE-ONE",
            "prompt echo contains AGENTGRID-CODEX-SMOKE-ONE",
            timeout=0.01,
        )


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
        first_identity = (agent.pane_id, agent.runtime_pid, agent.endpoint_id)

        first_marker = "AGENTGRID-CODEX-SMOKE-ONE"
        first_prompt = (
            "This is the first AgentGrid Codex smoke request.\n\n"
            "Reply with exactly one line made from these five tokens joined by hyphens:\n"
            "AGENTGRID CODEX SMOKE ONE\n\n"
            "Do not include any other words."
        )
        assert first_marker not in first_prompt
        baseline = manager.read(agent.id)
        manager.send(agent.id, first_prompt)
        wait_for_new_output_marker(manager, agent.id, first_marker, baseline)

        inspected = manager.inspect(agent.id)
        assert (inspected.pane_id, inspected.runtime_pid, inspected.endpoint_id) == first_identity

        second_marker = "AGENTGRID-CODEX-SMOKE-TWO"
        second_prompt = (
            "This is the second related AgentGrid Codex smoke request in the same session.\n\n"
            "Reply with exactly one line made from these five tokens joined by hyphens:\n"
            "AGENTGRID CODEX SMOKE TWO\n\n"
            "Do not include any other words."
        )
        assert second_marker not in second_prompt
        baseline = manager.read(agent.id)
        manager.send(agent.id, second_prompt)
        wait_for_new_output_marker(manager, agent.id, second_marker, baseline)

        inspected_again = manager.inspect(agent.id)
        assert (inspected_again.pane_id, inspected_again.runtime_pid, inspected_again.endpoint_id) == first_identity

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
