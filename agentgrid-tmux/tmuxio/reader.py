from __future__ import annotations


def read_pane(client, pane_id: str, lines: int | None = None) -> str:
    args = ["capture-pane", "-p", "-t", pane_id]
    if lines is not None:
        if lines <= 0:
            raise ValueError("lines must be greater than zero")
        args.extend(["-S", f"-{lines}"])
    return client.run(args).stdout
