from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TmuxCommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Session:
    session_id: str
    name: str
    windows: int
    created: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Window:
    window_id: str
    session: str
    name: str
    index: int
    active: bool
    panes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Pane:
    pane_id: str
    session: str
    window: str
    window_id: str
    window_index: int
    pane_index: int
    pid: int | None
    command: str
    tty: str
    active: bool
    dead: bool
    current_path: str
    title: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HandshakeResult:
    reachable: bool
    pane_id: str
    session: str | None = None
    window: str | None = None
    pid: int | None = None
    command: str | None = None
    tty: str | None = None
    active: bool | None = None
    dead: bool | None = None
    active_handshake: bool = False
    expected_endpoint_id: str | None = None
    matched_endpoint_id: bool | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
