from __future__ import annotations

from agentgrid_shell_logger import ShellLogger


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
