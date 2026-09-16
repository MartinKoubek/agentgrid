from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path
from shlex import quote

import pytest

from tmuxio import TmuxClient
from tmuxio.errors import TmuxCommandError, UnsafePaneError


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def require_tmux_can_allocate_panes() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")
    socket_name = f"agentgrid-preflight-{uuid.uuid4().hex}"
    run_tmux_or_skip(["tmux", "-L", socket_name, "new-session", "-d", "-s", "preflight-env", "bash"])
    client = TmuxClient(socket_name=socket_name)
    try:
        client.start_process("bash", session="preflight")
    except TmuxCommandError as exc:
        if "Device not configured" in str(exc):
            pytest.skip(f"tmux cannot allocate a test pane: {exc}")
        raise
    finally:
        try:
            client.kill_server()
        except subprocess.TimeoutExpired:
            pass


def wait_for_text(client: TmuxClient, pane_id: str, text: str, timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        last_output = client.read(pane_id)
        if text in last_output:
            return last_output
        time.sleep(0.05)
    raise AssertionError(f"did not find {text!r} in pane output: {last_output!r}")


def run_tmux_or_skip(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode == 0:
        return
    if "Device not configured" in completed.stderr:
        pytest.skip(f"tmux cannot allocate a test pane: {completed.stderr.strip()}")
    raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, completed.stderr)


def test_tmux_discover_handshake_write_read_and_exit() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    session_name = "agentgrid"
    client = TmuxClient(socket_name=socket_name)

    run_tmux_or_skip(
        ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name, "bash"],
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
        assert active_result.pane_alive is True
        assert active_result.agent_alive is True
        assert active_result.matched_endpoint_id is True

        mismatch_result = client.handshake(pane_id, active=True, expected_endpoint_id="wrong")
        assert mismatch_result.matched_endpoint_id is False

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
        subprocess.run(["tmux", "-L", socket_name, "kill-server"], check=False, timeout=5)


def test_tmux_existing_pane_launch_tracks_worker_separately_from_shell() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    client = TmuxClient(socket_name=socket_name)

    try:
        shell_pane = client.start_process("bash", session="existing-shell")
        client.start_process_in_pane(
            shell_pane.pane_id,
            "python3.11 -c 'print(\"WORKER_DONE\", flush=True)'",
            endpoint_id="worker-1",
        )
        wait_for_text(client, shell_pane.pane_id, "WORKER_DONE")

        deadline = time.monotonic() + 3.0
        last_result = client.handshake(shell_pane.pane_id, active=True, expected_endpoint_id="worker-1")
        while time.monotonic() < deadline:
            last_result = client.handshake(shell_pane.pane_id, active=True, expected_endpoint_id="worker-1")
            if last_result.pane_alive and not last_result.agent_alive:
                break
            time.sleep(0.05)

        assert last_result.pane_alive is True
        assert last_result.agent_alive is False
        assert last_result.matched_endpoint_id is False
    finally:
        client.kill_server()


def test_tmux_refuses_to_launch_in_non_shell_pane() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    client = TmuxClient(socket_name=socket_name)

    try:
        pane = client.start_process("python3.11 -c 'import time; time.sleep(5)'", session="busy-pane")
        with pytest.raises(UnsafePaneError):
            client.start_process_in_pane(pane.pane_id, "echo unsafe", endpoint_id="unsafe")
    finally:
        client.kill_server()


def test_tmux_follow_can_be_started_and_stopped(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    client = TmuxClient(socket_name=socket_name)
    output_path = tmp_path / "follow.log"

    try:
        pane = client.start_process("bash", session="streaming")
        returned_path = client.follow(pane.pane_id, output_path=str(output_path))
        assert returned_path == str(output_path)

        client.write(pane.pane_id, "echo STREAM_ON")
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if output_path.exists() and "STREAM_ON" in output_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.05)
        assert "STREAM_ON" in output_path.read_text(encoding="utf-8")

        client.stop_follow(pane.pane_id)
        before = output_path.read_text(encoding="utf-8")
        client.write(pane.pane_id, "echo STREAM_OFF")
        time.sleep(0.3)
        after = output_path.read_text(encoding="utf-8")
        assert after == before
    finally:
        client.kill_server()


def test_tmux_paste_text_delivers_multiline_prompt_as_one_terminal_paste(tmp_path) -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    client = TmuxClient(socket_name=socket_name)
    output_path = tmp_path / "received.bin"
    recorder_path = tmp_path / "recorder.py"
    recorder_source = r"""
from __future__ import annotations

import select
import sys
import termios
import time
import tty

output_path = sys.argv[1]
fd = sys.stdin.fileno()
old_attrs = termios.tcgetattr(fd)
data = bytearray()

try:
    tty.setraw(fd)
    sys.stdout.write("\x1b[?2004h")
    sys.stdout.flush()
    print("RECORDER_READY", flush=True)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        readable, _, _ = select.select([sys.stdin], [], [], 0.1)
        if not readable:
            continue
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            break
        data.extend(chunk)
        if data.endswith(b"\x1b[201~\r"):
            break
finally:
    sys.stdout.write("\x1b[?2004l")
    sys.stdout.flush()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    with open(output_path, "wb") as output_file:
        output_file.write(bytes(data))
    print("RECORDER_DONE", flush=True)
""".strip()
    assert 'data.endswith(b"\\x1b[201~\\r")' in recorder_source
    recorder_path.write_text(recorder_source, encoding="utf-8")
    prompt = "First paragraph with café.\n\nSecond paragraph: $(rm -rf /) && echo '$PATH' * ?"

    try:
        launch_command = (
            f"python3.11 -u {quote(str(recorder_path))} {quote(str(output_path))}; "
            "status=$?; echo RECORDER_EXIT:$status; sleep 30"
        )
        pane = client.start_process(
            f"bash -lc {quote(launch_command)}",
            session="paste-recorder",
        )
        try:
            wait_for_text(client, pane.pane_id, "RECORDER_READY")
        except (AssertionError, TmuxCommandError) as exc:
            source = recorder_path.read_text(encoding="utf-8")
            raise AssertionError(f"recorder did not become ready; source was:\n{source}") from exc
        client.paste_text(pane.pane_id, prompt)
        client.send_key(pane.pane_id, "ENTER")
        wait_for_text(client, pane.pane_id, "RECORDER_DONE")

        received = output_path.read_bytes()
        prompt_bytes = prompt.encode("utf-8")
        expected = b"\x1b[200~" + prompt_bytes + b"\x1b[201~\r"
        assert received == expected
        assert received.count(prompt_bytes) == 1
        assert received.startswith(b"\x1b[200~")
        assert prompt_bytes in received
        assert b"\x1b[201~\r" in received
    finally:
        client.kill_server()


def test_tmux_interactive_prompt_roundtrip() -> None:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is not installed")

    socket_name = f"agentgrid-test-{uuid.uuid4().hex}"
    session_name = "interactive"
    client = TmuxClient(socket_name=socket_name)
    script = "read -p 'What is your name? ' name; echo Hello $name; read -p 'Proceed? [y/N] ' yn; [ \"$yn\" = y ] && echo DONE; sleep 1"

    run_tmux_or_skip(
        ["tmux", "-L", socket_name, "new-session", "-d", "-s", session_name, "bash", "-lc", script],
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
        subprocess.run(["tmux", "-L", socket_name, "kill-server"], check=False, timeout=5)
