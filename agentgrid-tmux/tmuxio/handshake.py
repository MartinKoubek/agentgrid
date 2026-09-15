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
        runtime_pid = _parse_pid(client.get_pane_option(pane_id, "@agentgrid_runtime_pid")) or pane.pid
        endpoint_id = client.get_pane_option(pane_id, "@agentgrid_endpoint_id") or None
        agent_alive = _process_exists(runtime_pid) if runtime_pid else False
    except TmuxError as exc:
        return HandshakeResult(reachable=False, pane_id=pane_id, pane_alive=False, agent_alive=False, error=str(exc))

    result = HandshakeResult(
        reachable=True,
        pane_id=pane.pane_id,
        pane_alive=True,
        agent_alive=agent_alive,
        session=pane.session,
        window=pane.window,
        pid=pane.pid,
        runtime_pid=runtime_pid,
        command=pane.command,
        tty=pane.tty,
        active=pane.active,
        dead=pane.dead,
        active_handshake=active,
        expected_endpoint_id=expected_endpoint_id,
        endpoint_id=endpoint_id,
    )

    if not active:
        return result

    if not expected_endpoint_id:
        return HandshakeResult(
            **{**result.to_dict(), "matched_endpoint_id": None, "error": "active handshake requires expected_endpoint_id"}
        )

    env_value = endpoint_id or (_read_process_environment(runtime_pid).get("AGENTGRID_ENDPOINT_ID") if runtime_pid else None)
    return HandshakeResult(
        **{
            **result.to_dict(),
            "matched_endpoint_id": agent_alive and env_value == expected_endpoint_id,
            "error": None
            if agent_alive and env_value == expected_endpoint_id
            else "worker process is not alive or AGENTGRID_ENDPOINT_ID did not match",
        }
    )


def _parse_pid(value: str) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


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
