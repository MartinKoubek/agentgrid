from tmuxio.writer import send_key, send_text, write_text


class FakeClient:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, args: list[str]) -> None:
        self.commands.append(args)


def test_send_text_uses_literal_mode() -> None:
    client = FakeClient()

    send_text(client, "%17", "hello ENTER")

    assert client.commands == [["send-keys", "-t", "%17", "-l", "hello ENTER"]]


def test_send_key_sends_key_name() -> None:
    client = FakeClient()

    send_key(client, "%17", "C-c")

    assert client.commands == [["send-keys", "-t", "%17", "C-c"]]


def test_write_text_can_append_enter() -> None:
    client = FakeClient()

    write_text(client, "%17", "echo hello")

    assert client.commands == [
        ["send-keys", "-t", "%17", "-l", "echo hello"],
        ["send-keys", "-t", "%17", "ENTER"],
    ]
