from __future__ import annotations

import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from tmuxio.errors import TmuxError


def send_text(client, pane_id: str, text: str) -> None:
    client.run(["send-keys", "-t", pane_id, "-l", text])


def send_key(client, pane_id: str, key: str) -> None:
    client.run(["send-keys", "-t", pane_id, key])


def write_text(client, pane_id: str, text: str, enter: bool = True) -> None:
    send_text(client, pane_id, text)
    if enter:
        send_key(client, pane_id, "ENTER")


def paste_text(client, pane_id: str, text: str, bracketed: bool = True) -> None:
    buffer_name = f"agentgrid-paste-{uuid.uuid4().hex}"
    temp_path: str | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp_file:
            temp_file.write(text)
            temp_path = temp_file.name
        client.run(["load-buffer", "-b", buffer_name, temp_path])
        Path(temp_path).unlink(missing_ok=True)
        args = ["paste-buffer", "-r", "-d", "-b", buffer_name, "-t", pane_id]
        if bracketed:
            args.insert(1, "-p")
        client.run(args)
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)
        try:
            client.run(["delete-buffer", "-b", buffer_name])
        except TmuxError:
            pass
