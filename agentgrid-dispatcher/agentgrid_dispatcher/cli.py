from __future__ import annotations

import argparse
import json
import subprocess
import sys

from agentgrid_dispatcher.dispatcher import Dispatcher
from agentgrid_dispatcher.models import DispatchDecision
from agentgrid_event_queue import EventQueue


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser = argparse.ArgumentParser(prog="agentgrid-dispatcher")
    parser.add_argument("--queue", help="path to event queue SQLite database")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    subparsers.add_parser("next", parents=[common], help="claim and print next event")
    dispatch = subparsers.add_parser("dispatch", parents=[common], help="dispatch next event")
    dispatch.add_argument("--handler-command", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatcher = Dispatcher(EventQueue(args.queue))
    try:
        output = run_command(dispatcher, args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(to_jsonable(output), indent=2))
    elif output is not None:
        print(json.dumps(to_jsonable(output), sort_keys=True))
    return 0


def run_command(dispatcher: Dispatcher, args: argparse.Namespace) -> object:
    if args.command_name == "next":
        return dispatcher.next()
    if args.command_name == "dispatch":
        return dispatcher.dispatch_next(lambda event: run_handler(args.handler_command, event))
    raise ValueError(f"unknown command: {args.command_name}")


def run_handler(command: str, event) -> DispatchDecision:
    completed = subprocess.run(
        command,
        input=event.to_json(),
        text=True,
        shell=True,
        check=False,
    )
    if completed.returncode == 0:
        return DispatchDecision.ACK
    if completed.returncode == 75:
        return DispatchDecision.PARK
    return DispatchDecision.REQUEUE


def to_jsonable(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
