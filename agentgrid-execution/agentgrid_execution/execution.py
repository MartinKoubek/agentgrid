from __future__ import annotations

import os, subprocess
from time import time
from agentgrid_execution.models import ExecutionResult


class ExecutionManager:
    def run(self, command: list[str], cwd: str | None = None, timeout: float | None = None) -> ExecutionResult:
        command_cwd = cwd or os.getcwd(); started = time()
        completed = subprocess.run(command, cwd=command_cwd, capture_output=True, text=True, timeout=timeout, check=False)
        finished = time()
        return ExecutionResult(command, command_cwd, completed.returncode, completed.stdout, completed.stderr, finished - started)
