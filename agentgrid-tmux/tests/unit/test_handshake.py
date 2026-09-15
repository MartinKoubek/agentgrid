from __future__ import annotations

from tmuxio.errors import TmuxCommandError
from tmuxio.handshake import handshake
from tmuxio.models import Pane


class DisappearingPaneClient:
    def inspect_pane(self, pane_id: str) -> Pane:
        return Pane(
            pane_id=pane_id,
            session="agentgrid",
            window="worker",
            window_id="@1",
            window_index=0,
            pane_index=0,
            pid=123,
            command="bash",
            tty="/dev/ttys001",
            active=True,
            dead=False,
            current_path="/tmp",
            title="worker",
        )

    def get_pane_option(self, pane_id: str, name: str) -> str:
        raise TmuxCommandError(["tmux", "display-message", "-p", "-t", pane_id, name], 1, "server exited unexpectedly")


def test_handshake_returns_unreachable_when_pane_disappears_after_inspect() -> None:
    result = handshake(DisappearingPaneClient(), "%1", active=True, expected_endpoint_id="endpoint-1")

    assert result.reachable is False
    assert result.pane_alive is False
    assert result.agent_alive is False
    assert "server exited unexpectedly" in result.error
