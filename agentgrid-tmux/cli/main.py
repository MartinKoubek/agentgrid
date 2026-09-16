from __future__ import annotations

import argparse
import json
import sys

from tmuxio.client import TmuxClient, to_jsonable
from tmuxio.errors import TmuxError


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    parser = argparse.ArgumentParser(prog="tmuxio")
    parser.add_argument("--socket-name", help="tmux socket name for isolated servers")
    parser.add_argument("--socket-path", help="tmux socket path for isolated servers")
    parser.add_argument("--tmux", default="tmux", help="tmux executable path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sessions", parents=[common], help="list tmux sessions")

    windows = subparsers.add_parser("windows", parents=[common], help="list tmux windows")
    windows.add_argument("--session", help="limit results to a session")

    panes = subparsers.add_parser("panes", parents=[common], help="list tmux panes")
    panes.add_argument("--session", help="limit results to a session")

    inspect = subparsers.add_parser("inspect", parents=[common], help="inspect a pane")
    inspect.add_argument("pane_id")

    handshake = subparsers.add_parser("handshake", parents=[common], help="verify a pane is reachable")
    handshake.add_argument("pane_id")
    handshake.add_argument("--active", action="store_true", help="check a controlled endpoint ID")
    handshake.add_argument("--endpoint-id", help="expected AGENTGRID_ENDPOINT_ID for active handshake")

    read = subparsers.add_parser("read", parents=[common], help="read current pane output")
    read.add_argument("pane_id")
    read.add_argument("--lines", type=int, help="number of recent lines to capture")

    write = subparsers.add_parser("write", parents=[common], help="write text to a pane")
    write.add_argument("pane_id")
    write.add_argument("text")
    write.add_argument("--no-enter", action="store_true", help="do not press ENTER after text")

    paste = subparsers.add_parser("paste", parents=[common], help="paste multiline text to a pane")
    paste.add_argument("pane_id")
    paste.add_argument("text")
    paste.add_argument("--no-bracketed", action="store_true", help="disable bracketed paste mode")

    key = subparsers.add_parser("key", parents=[common], help="send a key to a pane")
    key.add_argument("pane_id")
    key.add_argument("key")

    follow = subparsers.add_parser("follow", parents=[common], help="stream future pane output through pipe-pane")
    follow.add_argument("pane_id")
    follow.add_argument("--output", help="append output to this file instead of a temporary file")

    stop_follow = subparsers.add_parser("stop-follow", parents=[common], help="stop streaming pane output")
    stop_follow.add_argument("pane_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = TmuxClient(executable=args.tmux, socket_name=args.socket_name, socket_path=args.socket_path)

    try:
        output = run_command(client, args)
    except TmuxError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(to_jsonable(output), indent=2))
    elif output is not None:
        print_human(output)
    return 0


def run_command(client: TmuxClient, args: argparse.Namespace) -> object:
    if args.command == "sessions":
        return client.list_sessions()
    if args.command == "windows":
        return client.list_windows(session=args.session)
    if args.command == "panes":
        return client.list_panes(session=args.session)
    if args.command == "inspect":
        return client.inspect_pane(args.pane_id)
    if args.command == "handshake":
        return client.handshake(args.pane_id, active=args.active, expected_endpoint_id=args.endpoint_id)
    if args.command == "read":
        return client.read(args.pane_id, lines=args.lines)
    if args.command == "write":
        client.write(args.pane_id, args.text, enter=not args.no_enter)
        return {"ok": True}
    if args.command == "paste":
        client.paste_text(args.pane_id, args.text, bracketed=not args.no_bracketed)
        return {"ok": True}
    if args.command == "key":
        client.send_key(args.pane_id, args.key)
        return {"ok": True}
    if args.command == "follow":
        output_path = client.follow(args.pane_id, output_path=args.output)
        return {"ok": True, "output": output_path}
    if args.command == "stop-follow":
        client.stop_follow(args.pane_id)
        return {"ok": True}
    raise ValueError(f"unknown command: {args.command}")


def print_human(output: object) -> None:
    if isinstance(output, str):
        print(output, end="")
    elif isinstance(output, list):
        for item in output:
            print(json.dumps(to_jsonable(item), sort_keys=True))
    else:
        print(json.dumps(to_jsonable(output), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
