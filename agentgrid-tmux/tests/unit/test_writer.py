import subprocess

import pytest

from tmuxio.errors import TmuxCommandError
from tmuxio.writer import paste_text, send_key, send_text, write_text


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
        self.fail_on: str | None = None

    def run(self, args: list[str]) -> None:
        self.commands.append(args)
        if self.fail_on and args[0] == self.fail_on:
            raise TmuxCommandError(args, 1, "failed")


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


def test_paste_text_uses_unique_buffer_and_bracketed_paste(monkeypatch, tmp_path) -> None:
    client = FakeClient()
    temp_path = tmp_path / "prompt.txt"

    class FakeTempFile:
        name = str(temp_path)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def write(self, text: str) -> None:
            temp_path.write_text(text, encoding="utf-8")

    monkeypatch.setattr("tmuxio.writer.NamedTemporaryFile", lambda *args, **kwargs: FakeTempFile())
    monkeypatch.setattr("tmuxio.writer.uuid.uuid4", lambda: type("Uuid", (), {"hex": "abc123"})())

    paste_text(client, "%17", "hello\nworld")

    assert client.commands == [
        ["load-buffer", "-b", "agentgrid-paste-abc123", str(temp_path)],
        ["paste-buffer", "-p", "-r", "-d", "-b", "agentgrid-paste-abc123", "-t", "%17"],
        ["delete-buffer", "-b", "agentgrid-paste-abc123"],
    ]
    assert not temp_path.exists()


def test_paste_text_cleans_buffer_after_paste_failure(monkeypatch, tmp_path) -> None:
    client = FakeClient()
    client.fail_on = "paste-buffer"
    temp_path = tmp_path / "prompt.txt"

    class FakeTempFile:
        name = str(temp_path)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def write(self, text: str) -> None:
            temp_path.write_text(text, encoding="utf-8")

    monkeypatch.setattr("tmuxio.writer.NamedTemporaryFile", lambda *args, **kwargs: FakeTempFile())
    monkeypatch.setattr("tmuxio.writer.uuid.uuid4", lambda: type("Uuid", (), {"hex": "abc123"})())

    with pytest.raises(TmuxCommandError):
        paste_text(client, "%17", "secret prompt")

    assert client.commands[-1] == ["delete-buffer", "-b", "agentgrid-paste-abc123"]
    assert not temp_path.exists()
