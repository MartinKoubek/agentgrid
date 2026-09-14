from __future__ import annotations

from tmuxio.models import Pane, Session, Window

FIELD_SEPARATOR = "\t"


def parse_bool(value: str) -> bool:
    return value == "1"


def parse_int(value: str) -> int:
    return int(value or "0")


def parse_optional_int(value: str) -> int | None:
    return int(value) if value else None


def split_fields(line: str, expected: int) -> list[str]:
    parts = line.split(FIELD_SEPARATOR)
    if len(parts) < expected:
        parts.extend([""] * (expected - len(parts)))
    return parts[:expected]


def parse_session(line: str) -> Session:
    session_id, name, windows, created = split_fields(line, 4)
    return Session(
        session_id=session_id,
        name=name,
        windows=parse_int(windows),
        created=parse_optional_int(created),
    )


def parse_window(line: str) -> Window:
    window_id, session, name, index, active, panes = split_fields(line, 6)
    return Window(
        window_id=window_id,
        session=session,
        name=name,
        index=parse_int(index),
        active=parse_bool(active),
        panes=parse_int(panes),
    )


def parse_pane(line: str) -> Pane:
    (
        pane_id,
        session,
        window,
        window_id,
        window_index,
        pane_index,
        pid,
        command,
        tty,
        active,
        dead,
        current_path,
        title,
    ) = split_fields(line, 13)
    return Pane(
        pane_id=pane_id,
        session=session,
        window=window,
        window_id=window_id,
        window_index=parse_int(window_index),
        pane_index=parse_int(pane_index),
        pid=parse_optional_int(pid),
        command=command,
        tty=tty,
        active=parse_bool(active),
        dead=parse_bool(dead),
        current_path=current_path,
        title=title,
    )
