import subprocess

import pytest

from tmuxio.writer import send_key, send_text, write_text


def test_e2e_preflight_helper_uses_timeout(monkeypatch) -> None:
    from tests.e2e.test_tmux_roundtrip import run_tmux_or_skip

    calls = []

    def fake_run(command, capture_output, text, check, timeout):
        calls.append(
            {
                "command": command,
                "capture_output": capture_output,
                "text": text,
                "check": check,
                "timeout": timeout,
            }
        )
        return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    run_tmux_or_skip(["tmux", "display-message"])

    assert calls == [
        {
            "command": ["tmux", "display-message"],
            "capture_output": True,
            "text": True,
            "check": False,
            "timeout": 30,
        }
    ]


def test_e2e_preflight_helper_does_not_skip_timeout(monkeypatch) -> None:
    from tests.e2e.test_tmux_roundtrip import run_tmux_or_skip

    def fake_run(command, capture_output, text, check, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(subprocess.TimeoutExpired):
        run_tmux_or_skip(["tmux", "display-message"])


class FakeClient:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, args: list[str]) -> None:
        self.commands.append(args)


def test_send_text_uses_literal_mode() -> None:
    client = FakeClient()

    send_text(client, "%17", "hello ENTER")

    assert client.commands == [["send-keys", "-t", "%17", "-l", "hello ENTER"]]


def test_send_key_sends_key_name() -> None:
    client = FakeClient()

    send_key(client, "%17", "C-c")

    assert client.commands == [["send-keys", "-t", "%17", "C-c"]]


def test_write_text_can_append_enter() -> None:
    client = FakeClient()

    write_text(client, "%17", "echo hello")

    assert client.commands == [
        ["send-keys", "-t", "%17", "-l", "echo hello"],
        ["send-keys", "-t", "%17", "ENTER"],
    ]
