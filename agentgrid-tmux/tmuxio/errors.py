class TmuxError(Exception):
    """Base error for tmux communication failures."""


class TmuxNotFoundError(TmuxError):
    """Raised when the tmux executable is not available."""


class TmuxCommandError(TmuxError):
    """Raised when a tmux command exits unsuccessfully."""

    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"tmux command failed with exit code {returncode}: {' '.join(command)}: {stderr.strip()}"
        )


class PaneNotFoundError(TmuxError):
    """Raised when a requested tmux pane cannot be found."""

    def __init__(self, pane_id: str) -> None:
        self.pane_id = pane_id
        super().__init__(f"tmux pane not found: {pane_id}")


class UnsafePaneError(TmuxError):
    """Raised when launching into an existing pane would be unsafe."""
