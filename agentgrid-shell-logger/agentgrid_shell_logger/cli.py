from __future__ import annotations

import argparse
import json
import sys

from agentgrid_shell_logger.logger import ShellLogger


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    parser = argparse.ArgumentParser(prog="agentgrid-shell-logger")
    parser.add_argument("--store", help="path to shell log SQLite database")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    run = subparsers.add_parser("run", parents=[common], help="run and log a command")
    run.add_argument("--cwd", help="working directory for the command")
    run.add_argument("--pane", help="tmux pane ID associated with this command")
    run.add_argument("command", nargs=argparse.REMAINDER)

    list_parser = subparsers.add_parser("list", parents=[common], help="list command records")
    list_parser.add_argument("--limit", type=int, default=50)

    inspect = subparsers.add_parser("inspect", parents=[common], help="inspect one command record")
    inspect.add_argument("record_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = ShellLogger(store_path=args.store)

    try:
        output = run_command(logger, args)
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
    if args.command_name == "run":
        return output.exit_code
    return 0


def run_command(logger: ShellLogger, args: argparse.Namespace) -> object:
    if args.command_name == "run":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise ValueError("run requires a command after --")
        return logger.run(command, cwd=args.cwd, pane_id=args.pane)
    if args.command_name == "list":
        return logger.list(limit=args.limit)
    if args.command_name == "inspect":
        return logger.inspect(args.record_id)
    raise ValueError(f"unknown command: {args.command_name}")


def to_jsonable(value: object) -> object:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def print_human(output: object) -> None:
    if hasattr(output, "stdout"):
        print(output.stdout, end="")
        print(output.stderr, end="", file=sys.stderr)
    elif isinstance(output, list):
        for item in output:
            print(json.dumps(to_jsonable(item), sort_keys=True))
    else:
        print(json.dumps(to_jsonable(output), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
