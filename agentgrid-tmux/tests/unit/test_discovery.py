from tmuxio.discovery import FIELD_SEPARATOR, parse_pane, parse_session, parse_window


def test_parse_session() -> None:
    session = parse_session(FIELD_SEPARATOR.join(["$1", "work", "2", "123456"]))

    assert session.session_id == "$1"
    assert session.name == "work"
    assert session.windows == 2
    assert session.created == 123456


def test_parse_window() -> None:
    window = parse_window(FIELD_SEPARATOR.join(["@1", "work", "editor", "3", "1", "4"]))

    assert window.window_id == "@1"
    assert window.session == "work"
    assert window.name == "editor"
    assert window.index == 3
    assert window.active is True
    assert window.panes == 4


def test_parse_pane() -> None:
    pane = parse_pane(
        FIELD_SEPARATOR.join(
            [
                "%17",
                "agentgrid",
                "project-a",
                "@3",
                "1",
                "0",
                "12345",
                "bash",
                "/dev/ttys012",
                "1",
                "0",
                "/repo",
                "shell",
            ]
        )
    )

    assert pane.pane_id == "%17"
    assert pane.session == "agentgrid"
    assert pane.window == "project-a"
    assert pane.pid == 12345
    assert pane.command == "bash"
    assert pane.active is True
    assert pane.dead is False
