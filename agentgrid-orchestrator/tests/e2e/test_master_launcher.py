from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "bin" / "master_codex"
ORCHESTRATOR = ROOT / "bin" / "agentgrid-orchestrator"


def test_master_launcher_help_requires_no_codex() -> None:
    result = subprocess.run(["bash", str(LAUNCHER), "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "--project PATH" in result.stdout
    assert "--once" in result.stdout


def test_master_launcher_fake_once_registers_and_delegates(tmp_path: Path) -> None:
    if shutil.which("tmux") is None or shutil.which("python3.11") is None:
        pytest.skip("tmux and python3.11 are needed for the integrated launcher test")
    project = tmp_path / "test project with spaces"
    project.mkdir()
    (project / "README.md").write_text("# Smoke test\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    socket = f"agentgrid-launcher-{uuid.uuid4().hex}"
    launcher_args = [
        "bash", str(LAUNCHER), "--fake", "--project", str(project),
        "--runtime-root", str(runtime), "--socket-name", socket,
    ]
    try:
        result = subprocess.run(launcher_args + ["--once", "Read README.md"], capture_output=True, text=True, timeout=90)
        if "Device not configured" in result.stderr:
            pytest.skip(f"tmux cannot allocate a test pane: {result.stderr.strip()}")
        assert result.returncode == 0, result.stderr
        decision = json.loads(result.stdout)
        assert decision["action"] == "START_AGENT"
        assert decision["agent_id"]
        project_id = decision["project_id"]
        assert project_id.startswith("test-project-with-spaces-")

        history = subprocess.run(
            [str(ORCHESTRATOR), "--runtime-root", str(runtime), "--socket-name", socket,
             "master-history", "--json"], capture_output=True, text=True, timeout=30,
        )
        assert history.returncode == 0, history.stderr
        records = json.loads(history.stdout)
        assert len(records) == 1
        assert records[0]["status"] == "EXECUTED"
        assert records[0]["project_id"] == project_id

        again = subprocess.run(launcher_args + ["--once", "Different task"], capture_output=True, text=True, timeout=90)
        assert again.returncode == 0, again.stderr
        second = json.loads(again.stdout)
        assert second["project_id"] == project_id
        assert second["agent_id"] != decision["agent_id"]
    finally:
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False, timeout=10)
