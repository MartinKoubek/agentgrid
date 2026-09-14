from tmuxio.endpoint import PaneEndpoint


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def inspect_pane(self, pane_id: str) -> object:
        self.calls.append(("inspect", pane_id))
        return type("Pane", (), {"dead": False})()

    def read(self, pane_id: str, lines: int | None = None) -> str:
        self.calls.append(("read", (pane_id, lines)))
        return "output"

    def write(self, pane_id: str, text: str, enter: bool = True) -> None:
        self.calls.append(("write", (pane_id, text, enter)))

    def send_key(self, pane_id: str, key: str) -> None:
        self.calls.append(("key", (pane_id, key)))

    def send_text(self, pane_id: str, text: str) -> None:
        self.calls.append(("text", (pane_id, text)))


def test_endpoint_delegates_to_client() -> None:
    client = FakeClient()
    endpoint = PaneEndpoint(client, "%17")

    assert endpoint.is_alive() is True
    assert endpoint.read(lines=10) == "output"
    endpoint.write("ls", enter=False)
    endpoint.send_key("ENTER")
    endpoint.send_text("hello")

    assert client.calls == [
        ("inspect", "%17"),
        ("read", ("%17", 10)),
        ("write", ("%17", "ls", False)),
        ("key", ("%17", "ENTER")),
        ("text", ("%17", "hello")),
    ]
