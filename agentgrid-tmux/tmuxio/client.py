from __future__ import annotations

import subprocess
from dataclasses import asdict, is_dataclass
from shlex import quote
from time import monotonic, sleep
from typing import Iterable

from tmuxio.discovery import parse_pane, parse_session, parse_window
from tmuxio.endpoint import PaneEndpoint
from tmuxio.errors import PaneNotFoundError, TmuxCommandError, TmuxNotFoundError, UnsafePaneError
from tmuxio.handshake import handshake
from tmuxio.models import HandshakeResult, Pane, Session, TmuxCommandResult, Window
from tmuxio.reader import read_pane
from tmuxio.stream import follow_pane
from tmuxio.writer import send_key, send_text, write_text


FIELD_SEPARATOR = "\t"


class TmuxClient:
    def __init__(
        self,
        executable: str = "tmux",
        socket_name: str | None = None,
        socket_path: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        if socket_name and socket_path:
            raise ValueError("socket_name and socket_path are mutually exclusive")
        self.executable = executable
        self.socket_name = socket_name
        self.socket_path = socket_path
        self.timeout = timeout

    def base_command(self) -> list[str]:
        command = [self.executable]
        if self.socket_name:
            command.extend(["-L", self.socket_name])
        if self.socket_path:
            command.extend(["-S", self.socket_path])
        return command

    def run(self, args: Iterable[str], timeout: float | None = None) -> TmuxCommandResult:
        command = [*self.base_command(), *args]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout if timeout is None else timeout,
            )
        except FileNotFoundError as exc:
            raise TmuxNotFoundError("tmux executable not found") from exc

        result = TmuxCommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if completed.returncode != 0:
            raise TmuxCommandError(command, completed.returncode, completed.stderr)
        return result

    def list_sessions(self) -> list[Session]:
        fmt = FIELD_SEPARATOR.join(["#{session_id}", "#{session_name}", "#{session_windows}", "#{session_created}"])
        result = self.run(["list-sessions", "-F", fmt])
        return [parse_session(line) for line in result.stdout.splitlines() if line]

    def list_windows(self, session: str | None = None) -> list[Window]:
        fmt = FIELD_SEPARATOR.join(
            [
                "#{window_id}",
                "#{session_name}",
                "#{window_name}",
                "#{window_index}",
                "#{window_active}",
                "#{window_panes}",
            ]
        )
        args = ["list-windows"]
        if session:
            args.extend(["-t", session])
        else:
            args.append("-a")
        args.extend(["-F", fmt])
        result = self.run(args)
        return [parse_window(line) for line in result.stdout.splitlines() if line]

    def list_panes(self, session: str | None = None) -> list[Pane]:
        fmt = FIELD_SEPARATOR.join(
            [
                "#{pane_id}",
                "#{session_name}",
                "#{window_name}",
                "#{window_id}",
                "#{window_index}",
                "#{pane_index}",
                "#{pane_pid}",
                "#{pane_current_command}",
                "#{pane_tty}",
                "#{pane_active}",
                "#{pane_dead}",
                "#{pane_current_path}",
                "#{pane_title}",
            ]
        )
        args = ["list-panes"]
        if session:
            args.extend(["-t", session])
        else:
            args.append("-a")
        args.extend(["-F", fmt])
        result = self.run(args)
        return [parse_pane(line) for line in result.stdout.splitlines() if line]

    def inspect_pane(self, pane_id: str) -> Pane:
        fmt = FIELD_SEPARATOR.join(
            [
                "#{pane_id}",
                "#{session_name}",
                "#{window_name}",
                "#{window_id}",
                "#{window_index}",
                "#{pane_index}",
                "#{pane_pid}",
                "#{pane_current_command}",
                "#{pane_tty}",
                "#{pane_active}",
                "#{pane_dead}",
                "#{pane_current_path}",
                "#{pane_title}",
            ]
        )
        try:
            result = self.run(["display-message", "-p", "-t", pane_id, fmt])
        except TmuxCommandError as exc:
            raise PaneNotFoundError(pane_id) from exc
        output = result.stdout.strip("\n")
        if not output:
            raise PaneNotFoundError(pane_id)
        return parse_pane(output)

    def start_process(
        self,
        command: str,
        session: str = "agentgrid",
        window: str | None = None,
        cwd: str | None = None,
        endpoint_id: str | None = None,
    ) -> Pane:
        args: list[str]
        if self._session_exists(session):
            args = ["new-window", "-d", "-P", "-F", "#{pane_id}", "-t", session]
            if window:
                args.extend(["-n", window])
        else:
            args = ["new-session", "-d", "-P", "-F", "#{pane_id}", "-s", session]
            if window:
                args.extend(["-n", window])
        if cwd:
            args.extend(["-c", cwd])
        launch_command = self._runtime_wrapper(command, endpoint_id) if endpoint_id else command
        args.append(launch_command)
        result = self.run(args)
        pane_id = result.stdout.strip()
        if endpoint_id:
            self.wait_for_pane_option(pane_id, "@agentgrid_runtime_pid")
        return self.inspect_pane(pane_id)

    def start_process_in_pane(
        self,
        pane_id: str,
        command: str,
        endpoint_id: str | None = None,
        require_idle_shell: bool = True,
    ) -> Pane:
        pane = self.inspect_pane(pane_id)
        if require_idle_shell and not self.is_idle_shell(pane):
            raise UnsafePaneError(
                f"refusing to start process in pane {pane_id}: current command is {pane.command!r}, not an idle shell"
            )
        runtime_command = self._runtime_wrapper(command, endpoint_id) if endpoint_id else command
        self.write(pane_id, runtime_command)
        if endpoint_id:
            self.wait_for_pane_option(pane_id, "@agentgrid_runtime_pid")
        return self.inspect_pane(pane_id)

    def is_idle_shell(self, pane: Pane) -> bool:
        return not pane.dead and pane.command in {"bash", "zsh", "sh", "fish"}

    def wait_for_pane_option(self, pane_id: str, name: str, timeout: float = 3.0) -> str:
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            value = self.get_pane_option(pane_id, name)
            if value:
                return value
            sleep(0.05)
        return ""

    def _runtime_wrapper(self, command: str, endpoint_id: str | None) -> str:
        option_commands = ["tmux set-option -p -t \"$TMUX_PANE\" @agentgrid_runtime_pid \"$$\""]
        if endpoint_id:
            option_commands.append(
                "tmux set-option -p -t \"$TMUX_PANE\" @agentgrid_endpoint_id " + quote(endpoint_id)
            )
        script = "; ".join([*option_commands, "exec " + command])
        env_prefix = f"AGENTGRID_ENDPOINT_ID={quote(endpoint_id)} " if endpoint_id else ""
        return f"{env_prefix}sh -c {quote(script)}"

    def _session_exists(self, session: str) -> bool:
        try:
            self.run(["has-session", "-t", session])
            return True
        except TmuxCommandError:
            return False

    def kill_server(self, ignore_missing: bool = True) -> None:
        try:
            self.run(["kill-server"])
        except TmuxCommandError:
            if not ignore_missing:
                raise

    def get_pane_option(self, pane_id: str, name: str) -> str:
        return self.run(["display-message", "-p", "-t", pane_id, f"#{{{name}}}"]).stdout.strip("\n")

    def set_pane_option(self, pane_id: str, name: str, value: str) -> None:
        self.run(["set-option", "-p", "-t", pane_id, name, value])

    def get_pane(self, pane_id: str) -> PaneEndpoint:
        return PaneEndpoint(self, pane_id)

    def handshake(
        self,
        pane_id: str,
        active: bool = False,
        expected_endpoint_id: str | None = None,
    ) -> HandshakeResult:
        return handshake(self, pane_id, active=active, expected_endpoint_id=expected_endpoint_id)

    def read(self, pane_id: str, lines: int | None = None) -> str:
        return read_pane(self, pane_id, lines=lines)

    def send_text(self, pane_id: str, text: str) -> None:
        send_text(self, pane_id, text)

    def send_key(self, pane_id: str, key: str) -> None:
        send_key(self, pane_id, key)

    def write(self, pane_id: str, text: str, enter: bool = True) -> None:
        write_text(self, pane_id, text, enter=enter)

    def follow(self, pane_id: str, output_path: str | None = None) -> str:
        return follow_pane(self, pane_id, output_path=output_path)

    def stop_follow(self, pane_id: str) -> None:
        self.run(["pipe-pane", "-t", pane_id])


def to_jsonable(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value
