from __future__ import annotations

import argparse
import json
import sys

from agentgrid_event_queue.queue import EventQueue


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser = argparse.ArgumentParser(prog="agentgrid-event-queue")
    parser.add_argument("--store", help="path to event queue SQLite database")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    enqueue = subparsers.add_parser("enqueue", parents=[common], help="enqueue an event")
    enqueue.add_argument("type")
    enqueue.add_argument("--priority", type=int, default=50)
    enqueue.add_argument("--agent-id")
    enqueue.add_argument("--pane-id")
    enqueue.add_argument("--dedupe-key")
    enqueue.add_argument("--payload-json", default="{}")

    subparsers.add_parser("next", parents=[common], help="claim next pending event")
    list_parser = subparsers.add_parser("list", parents=[common], help="list events")
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=100)
    for command_name in ["ack", "park", "unpark", "inspect"]:
        command = subparsers.add_parser(command_name, parents=[common])
        command.add_argument("event_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    queue = EventQueue(args.store)
    try:
        output = run_command(queue, args)
    except Exception as exc:
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


def run_command(queue: EventQueue, args: argparse.Namespace) -> object:
    if args.command_name == "enqueue":
        return queue.enqueue(
            args.type,
            priority=args.priority,
            payload=json.loads(args.payload_json),
            dedupe_key=args.dedupe_key,
            agent_id=args.agent_id,
            pane_id=args.pane_id,
        )
    if args.command_name == "next":
        return queue.next()
    if args.command_name == "list":
        return queue.list(status=args.status, limit=args.limit)
    if args.command_name == "inspect":
        return queue.get(args.event_id)
    if args.command_name == "ack":
        return queue.ack(args.event_id)
    if args.command_name == "park":
        return queue.park(args.event_id)
    if args.command_name == "unpark":
        return queue.unpark(args.event_id)
    raise ValueError(f"unknown command: {args.command_name}")


def to_jsonable(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def print_human(output: object) -> None:
    if isinstance(output, list):
        for item in output:
            print(json.dumps(to_jsonable(item), sort_keys=True))
    else:
        print(json.dumps(to_jsonable(output), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
