from __future__ import annotations

import shutil
import subprocess
import time
import uuid

import pytest

from tmuxio import TmuxClient


pytestmark = pytest.mark.e2e


def wait_for_text(client: TmuxClient, pane_id: str, text: str, timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        last_output = client.read(pane_id)
        if text in last_output:
            return last_output
        time.sleep(0.05)
    raise AssertionError(f"did not find {text!r} in pane output: {last_output!r}")


def test_tmux_discover_handshake_write_read_and_exit() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    session_name = "agentgrid"
    client = TmuxClient(socket_name=socket_name)

    subprocess.run(
        ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name, "bash"],
        check=True,
    )
    try:
        panes = client.list_panes(session=session_name)
        assert len(panes) == 1
        pane_id = panes[0].pane_id

        result = client.handshake(pane_id)
        assert result.reachable is True
        assert result.pane_id == pane_id
        assert result.session == session_name
        assert result.pid is not None
        assert result.tty

        client.set_pane_option(pane_id, "@agentgrid_endpoint_id", "abc123")
        active_result = client.handshake(pane_id, active=True, expected_endpoint_id="abc123")
        assert active_result.reachable is True
        assert active_result.active_handshake is True
        assert active_result.matched_endpoint_id is True

        client.write(pane_id, "echo AGENTGRID_TEST")
        assert "AGENTGRID_TEST" in wait_for_text(client, pane_id, "AGENTGRID_TEST")

        client.write(pane_id, "printf 'hello\\nworld\\n'")
        output = wait_for_text(client, pane_id, "world")
        assert "hello" in output
        assert "world" in output

        client.write(pane_id, "exit")
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not client.handshake(pane_id).reachable:
                break
            time.sleep(0.05)
        assert client.handshake(pane_id).reachable is False
    finally:
        subprocess.run(["tmux", "-L", socket_name, "kill-server"], check=False)


def test_tmux_interactive_prompt_roundtrip() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    session_name = "interactive"
    client = TmuxClient(socket_name=socket_name)
    script = "read -p 'What is your name? ' name; echo Hello $name; read -p 'Proceed? [y/N] ' yn; [ \"$yn\" = y ] && echo DONE; sleep 1"

    subprocess.run(
        ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name, "bash", "-lc", script],
        check=True,
    )
    try:
        pane_id = client.list_panes(session=session_name)[0].pane_id
        wait_for_text(client, pane_id, "What is your name?")
        client.write(pane_id, "Martin")

        wait_for_text(client, pane_id, "Hello Martin")
        wait_for_text(client, pane_id, "Proceed? [y/N]")
        client.write(pane_id, "y")

        assert "DONE" in wait_for_text(client, pane_id, "DONE")
    finally:
        subprocess.run(["tmux", "-L", socket_name, "kill-server"], check=False)
