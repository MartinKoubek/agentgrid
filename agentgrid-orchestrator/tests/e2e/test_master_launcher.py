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
SKILL = ROOT / ".agents" / "skills" / "agentgrid" / "SKILL.md"
SKILL_SCRIPT = ROOT / ".agents" / "skills" / "agentgrid" / "scripts" / "agentgrid.py"


def test_master_launcher_help_requires_no_codex() -> None:
    result = subprocess.run(["bash", str(LAUNCHER), "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "--project PATH" in result.stdout
    assert "--once" in result.stdout


def test_agentgrid_skill_metadata_and_helper_status(tmp_path: Path) -> None:
    assert SKILL.exists()
    skill_text = SKILL.read_text(encoding="utf-8")
    assert "name: agentgrid" in skill_text
    assert "description:" in skill_text
    assert SKILL_SCRIPT.exists()
    assert SKILL_SCRIPT.stat().st_mode & 0o111

    runtime = tmp_path / "runtime"
    socket = f"agentgrid-skill-{uuid.uuid4().hex}"
    project = tmp_path / "project"
    project.mkdir()
    project_id = "project-a"
    opened = subprocess.run(
        [
            str(ORCHESTRATOR), "--runtime-root", str(runtime), "--socket-name", socket,
            "open-project", project_id, "--path", str(project), "--json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert opened.returncode == 0, opened.stderr

    result = subprocess.run(
        [
            str(SKILL_SCRIPT), "--runtime-root", str(runtime), "--socket-name", socket,
            "--agent-adapter", "fake", "status", "--project-id", project_id,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["project"]["id"] == project_id
    assert payload["agent_adapter"] == "fake"


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
        if "Device not configured" in result.stdout or "Device not configured" in result.stderr:
            pytest.skip(f"tmux cannot allocate a test pane: {(result.stderr or result.stdout).strip()}")
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


def test_master_launcher_status_reports_registered_project_without_codex(tmp_path: Path) -> None:
    if shutil.which("tmux") is None or shutil.which("python3.11") is None:
        pytest.skip("tmux and python3.11 are needed for the launcher status test")
    project = tmp_path / "status project"
    project.mkdir()
    runtime = tmp_path / "runtime"
    socket = f"agentgrid-launcher-status-{uuid.uuid4().hex}"

    result = subprocess.run(
        [
            "bash", str(LAUNCHER), "--project", str(project),
            "--runtime-root", str(runtime), "--socket-name", socket, "--status",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["project_path"] == str(project)
    assert payload["provider"] == "codex"
    assert payload["master_running"] is False
    assert payload["observer_running"] is False


def test_master_launcher_starts_and_reattaches_master_without_duplicate(tmp_path: Path) -> None:
    if shutil.which("tmux") is None or shutil.which("python3.11") is None:
        pytest.skip("tmux and python3.11 are needed for the launcher interactive test")
    project = tmp_path / "interactive project"
    project.mkdir()
    runtime = tmp_path / "runtime"
    socket = f"agentgrid-launcher-master-{uuid.uuid4().hex}"
    fake_codex = tmp_path / "codex"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "case \"$1\" in\n"
        "  --version) echo codex-cli-test; exit 0 ;;\n"
        "  doctor) exit 0 ;;\n"
        "esac\n"
        "printf 'FAKE INTERACTIVE CODEX\\n'\n"
        "sleep 300\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    environment = {**dict(), **{
        "CODEX": str(fake_codex),
        "AGENTGRID_MASTER_NO_ATTACH": "1",
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": __import__("os").environ.get("HOME", ""),
    }}
    try:
        args = [
            "bash", str(LAUNCHER), "--project", str(project),
            "--runtime-root", str(runtime), "--socket-name", socket,
        ]
        first = subprocess.run(args, capture_output=True, text=True, timeout=30, env=environment)
        if "Device not configured" in first.stdout or "Device not configured" in first.stderr:
            pytest.skip(f"tmux cannot allocate a test pane: {(first.stderr or first.stdout).strip()}")
        assert first.returncode == 0, first.stderr
        first_status = json.loads(first.stdout)
        assert first_status["master_running"] is True
        assert first_status["observer_running"] is True

        second = subprocess.run(args, capture_output=True, text=True, timeout=30, env=environment)
        assert second.returncode == 0, second.stderr
        panes = subprocess.run(
            ["tmux", "-L", socket, "list-panes", "-a", "-F", "#{session_name}:#{window_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert panes.returncode == 0, panes.stderr
        assert panes.stdout.splitlines().count("agentgrid-master:master") == 1
    finally:
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False, timeout=10)


def test_master_launcher_defaults_to_git_root_from_subdirectory(tmp_path: Path) -> None:
    if shutil.which("tmux") is None or shutil.which("python3.11") is None or shutil.which("git") is None:
        pytest.skip("tmux, python3.11, and git are needed for the launcher git-root test")
    project = tmp_path / "repo root"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", str(project)], capture_output=True, text=True, check=True, timeout=30)
    runtime = tmp_path / "runtime"
    socket = f"agentgrid-launcher-root-{uuid.uuid4().hex}"
    try:
        result = subprocess.run(
            [
                "bash", str(LAUNCHER), "--fake",
                "--runtime-root", str(runtime), "--socket-name", socket,
                "--once", "Read the repo root",
            ],
            cwd=nested,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if "Device not configured" in result.stdout or "Device not configured" in result.stderr:
            pytest.skip(f"tmux cannot allocate a test pane: {(result.stderr or result.stdout).strip()}")
        assert result.returncode == 0, result.stderr
        decision = json.loads(result.stdout)
        assert decision["project_id"].startswith("repo-root-")
    finally:
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False, timeout=10)


def test_master_launcher_once_returns_nonzero_for_policy_denial(tmp_path: Path) -> None:
    if shutil.which("tmux") is None or shutil.which("python3.11") is None:
        pytest.skip("tmux and python3.11 are needed for the launcher policy test")
    project = tmp_path / "policy project"
    project.mkdir()
    runtime = tmp_path / "runtime"
    socket = f"agentgrid-launcher-policy-{uuid.uuid4().hex}"
    try:
        result = subprocess.run(
            [
                "bash", str(LAUNCHER), "--fake", "--project", str(project),
                "--runtime-root", str(runtime), "--socket-name", socket,
                "--once", "force-push protected branch",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if "Device not configured" in result.stdout or "Device not configured" in result.stderr:
            pytest.skip(f"tmux cannot allocate a test pane: {(result.stderr or result.stdout).strip()}")
        assert result.returncode == 1
        decision = json.loads(result.stdout)
        assert decision["action"] == "DENY"

        history = subprocess.run(
            [str(ORCHESTRATOR), "--runtime-root", str(runtime), "--socket-name", socket,
             "master-history", "--json"], capture_output=True, text=True, timeout=30,
        )
        assert history.returncode == 0, history.stderr
        records = json.loads(history.stdout)
        assert records[0]["status"] == "FAILED"
    finally:
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True, check=False, timeout=10)
