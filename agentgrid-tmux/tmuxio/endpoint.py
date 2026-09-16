from __future__ import annotations

from typing import TYPE_CHECKING

from tmuxio.models import HandshakeResult, Pane

if TYPE_CHECKING:
    from tmuxio.client import TmuxClient


class PaneEndpoint:
    def __init__(self, client: TmuxClient, pane_id: str) -> None:
        self.client = client
        self.pane_id = pane_id

    def info(self) -> Pane:
        return self.client.inspect_pane(self.pane_id)

    def is_alive(self) -> bool:
        try:
            return not self.info().dead
        except Exception:
            return False

    def handshake(self, active: bool = False, expected_endpoint_id: str | None = None) -> HandshakeResult:
        return self.client.handshake(
            self.pane_id,
            active=active,
            expected_endpoint_id=expected_endpoint_id,
        )

    def read(self, lines: int | None = None) -> str:
        return self.client.read(self.pane_id, lines=lines)

    def send_text(self, text: str) -> None:
        self.client.send_text(self.pane_id, text)

    def send_key(self, key: str) -> None:
        self.client.send_key(self.pane_id, key)

    def paste_text(self, text: str, bracketed: bool = True) -> None:
        self.client.paste_text(self.pane_id, text, bracketed=bracketed)

    def write(self, text: str, enter: bool = True) -> None:
        self.client.write(self.pane_id, text, enter=enter)

    def follow(self, output_path: str | None = None) -> str:
        return self.client.follow(self.pane_id, output_path=output_path)

    def stop_follow(self) -> None:
        self.client.stop_follow(self.pane_id)
