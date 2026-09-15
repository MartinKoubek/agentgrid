from __future__ import annotations

import json
import sqlite3

from agentgrid_shell_logger import ShellLogger, ShellLogStore


def test_shell_logger_records_successful_command(tmp_path) -> None:
    logger = ShellLogger(store_path=tmp_path / "shell-log.sqlite3")

    record = logger.run(["python3.11", "-c", "print('hello')"], pane_id="%17")

    assert record.id == "cmd-001"
    assert record.exit_code == 0
    assert record.stdout == "hello\n"
    assert record.stderr == ""
    assert record.pane_id == "%17"

    loaded = logger.inspect(record.id)
    assert loaded == record


def test_shell_logger_records_failed_command(tmp_path) -> None:
    logger = ShellLogger(store_path=tmp_path / "shell-log.sqlite3")

    record = logger.run(["python3.11", "-c", "import sys; print('bad', file=sys.stderr); sys.exit(7)"])

    assert record.exit_code == 7
    assert record.stdout == ""
    assert record.stderr == "bad\n"


def test_shell_logger_lists_recent_commands(tmp_path) -> None:
    logger = ShellLogger(store_path=tmp_path / "shell-log.sqlite3")
    first = logger.run(["python3.11", "-c", "print('one')"])
    second = logger.run(["python3.11", "-c", "print('two')"])

    records = logger.list(limit=2)

    assert [record.id for record in records] == [second.id, first.id]


def test_shell_logger_filters_project_before_limit(tmp_path) -> None:
    logger = ShellLogger(store_path=tmp_path / "shell-log.sqlite3")

    for index in range(3):
        logger.run(["python3.11", "-c", f"print('a-{index}')"], project_id="project-a")
    for index in range(8):
        logger.run(["python3.11", "-c", f"print('b-{index}')"], project_id="project-b")

    records = logger.list(limit=5, project_id="project-a")

    assert len(records) == 3
    assert {record.project_id for record in records} == {"project-a"}


def test_shell_log_store_migrates_legacy_project_id_once(tmp_path, monkeypatch) -> None:
    path = tmp_path / "shell-log.sqlite3"
    legacy_record = {
        "id": "cmd-001",
        "command": ["echo", "hello"],
        "cwd": "/tmp",
        "stdout": "hello\n",
        "stderr": "",
        "exit_code": 0,
        "started_at": 1.0,
        "finished_at": 1.1,
        "duration_seconds": 0.1,
        "pane_id": None,
        "project_id": "project-a",
    }
    global_record = {
        "id": "cmd-002",
        "command": ["echo", "global"],
        "cwd": "/tmp",
        "stdout": "global\n",
        "stderr": "",
        "exit_code": 0,
        "started_at": 2.0,
        "finished_at": 2.1,
        "duration_seconds": 0.1,
        "pane_id": None,
    }
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE command_records ("
            "id TEXT PRIMARY KEY, started_at REAL NOT NULL, data TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO command_records(id, started_at, data) VALUES(?, ?, ?)",
            ("cmd-001", 1.0, json.dumps(legacy_record)),
        )
        connection.execute(
            "INSERT INTO command_records(id, started_at, data) VALUES(?, ?, ?)",
            ("cmd-002", 2.0, json.dumps(global_record)),
        )

    store = ShellLogStore(path)
    assert [record.id for record in store.list(project_id="project-a")] == ["cmd-001"]

    def fail_backfill(*args, **kwargs):
        raise AssertionError("backfill should not run after migration")

    monkeypatch.setattr(ShellLogStore, "_backfill_project_ids", fail_backfill)
    ShellLogStore(path)
