from __future__ import annotations

import os

from tmuxio.errors import TmuxError
from tmuxio.models import HandshakeResult


def handshake(
    client,
    pane_id: str,
    active: bool = False,
    expected_endpoint_id: str | None = None,
) -> HandshakeResult:
    try:
        pane = client.inspect_pane(pane_id)
    except TmuxError as exc:
        return HandshakeResult(reachable=False, pane_id=pane_id, error=str(exc))

    result = HandshakeResult(
        reachable=True,
        pane_id=pane.pane_id,
        session=pane.session,
        window=pane.window,
        pid=pane.pid,
        command=pane.command,
        tty=pane.tty,
        active=pane.active,
        dead=pane.dead,
        active_handshake=active,
        expected_endpoint_id=expected_endpoint_id,
    )

    if not active:
        return result

    if not expected_endpoint_id:
        return HandshakeResult(
            **{**result.to_dict(), "matched_endpoint_id": None, "error": "active handshake requires expected_endpoint_id"}
        )

    env_value = client.get_pane_option(pane_id, "@agentgrid_endpoint_id") or _read_process_environment(pane.pid).get(
        "AGENTGRID_ENDPOINT_ID"
    ) if pane.pid else None
    return HandshakeResult(
        **{
            **result.to_dict(),
            "matched_endpoint_id": env_value == expected_endpoint_id,
            "error": None if env_value == expected_endpoint_id else "AGENTGRID_ENDPOINT_ID did not match",
        }
    )


def _read_process_environment(pid: int) -> dict[str, str]:
    environ_path = f"/proc/{pid}/environ"
    if not os.path.exists(environ_path):
        return {}
    with open(environ_path, "rb") as environ_file:
        raw_entries = environ_file.read().split(b"\0")
    environment: dict[str, str] = {}
    for raw_entry in raw_entries:
        if not raw_entry or b"=" not in raw_entry:
            continue
        key, value = raw_entry.split(b"=", 1)
        environment[key.decode(errors="replace")] = value.decode(errors="replace")
    return environment
