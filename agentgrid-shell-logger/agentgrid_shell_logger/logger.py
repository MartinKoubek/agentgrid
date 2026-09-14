from __future__ import annotations

import os
import subprocess
from time import time

from agentgrid_shell_logger.models import CommandRecord
from agentgrid_shell_logger.store import ShellLogStore


class ShellLogger:
    def __init__(self, store_path: str | None = None, store: ShellLogStore | None = None) -> None:
        self.store = store or ShellLogStore(store_path)

    def run(
        self,
        command: list[str],
        cwd: str | None = None,
        pane_id: str | None = None,
        project_id: str | None = None,
    ) -> CommandRecord:
        record_id = self.store.allocate_id()
        command_cwd = cwd or os.getcwd()
        started_at = time()
        completed = subprocess.run(
            command,
            cwd=command_cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        finished_at = time()
        record = CommandRecord(
            id=record_id,
            command=command,
            cwd=command_cwd,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=finished_at - started_at,
            pane_id=pane_id,
            project_id=project_id,
        )
        self.store.save(record)
        return record

    def list(self, limit: int = 50, project_id: str | None = None) -> list[CommandRecord]:
        return self.store.list(limit=limit, project_id=project_id)

    def inspect(self, record_id: str) -> CommandRecord:
        return self.store.get(record_id)
