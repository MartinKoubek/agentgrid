from __future__ import annotations


def send_text(client, pane_id: str, text: str) -> None:
    client.run(["send-keys", "-t", pane_id, "-l", text])


def send_key(client, pane_id: str, key: str) -> None:
    client.run(["send-keys", "-t", pane_id, key])


def write_text(client, pane_id: str, text: str, enter: bool = True) -> None:
    send_text(client, pane_id, text)
    if enter:
        send_key(client, pane_id, "ENTER")
