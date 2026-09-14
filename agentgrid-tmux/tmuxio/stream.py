from __future__ import annotations

import tempfile
from shlex import quote


def follow_pane(client, pane_id: str, output_path: str | None = None) -> str:
    if output_path is None:
        output_file = tempfile.NamedTemporaryFile(prefix="agentgrid-tmux-", suffix=".log", delete=False)
        output_file.close()
        output_path = output_file.name
    client.run(["pipe-pane", "-o", "-t", pane_id, f"cat >> {quote(output_path)}"])
    return output_path
