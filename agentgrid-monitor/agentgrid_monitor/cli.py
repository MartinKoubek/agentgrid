from __future__ import annotations

import argparse
import json
import sys

from agentgrid_agent.adapters import default_adapters
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.registry import FileAgentRegistry
from agentgrid_monitor.monitor import Monitor
from tmuxio import TmuxClient


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    parser = argparse.ArgumentParser(prog="agentgrid-monitor")
    parser.add_argument("--registry", help="path to agent registry SQLite database")
    parser.add_argument("--state", help="path to monitor state SQLite database")
    parser.add_argument("--socket-name", help="tmux socket name")
    parser.add_argument("--socket-path", help="tmux socket path")
    parser.add_argument("--tmux", default="tmux", help="tmux executable path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    subparsers.add_parser("scan", parents=[common], help="scan runtime state and emit events")
    subparsers.add_parser("reset", parents=[common], help="reset stored monitor snapshots")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tmux = TmuxClient(executable=args.tmux, socket_name=args.socket_name, socket_path=args.socket_path)
    manager = AgentManager(tmux=tmux, registry=FileAgentRegistry(args.registry), adapters=default_adapters(tmux))
    monitor = Monitor(agent_manager=manager, state_path=args.state)

    try:
        output = run_command(monitor, args)
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


def run_command(monitor: Monitor, args: argparse.Namespace) -> object:
    if args.command_name == "scan":
        return monitor.scan()
    if args.command_name == "reset":
        monitor.reset()
        return {"ok": True}
    raise ValueError(f"unknown command: {args.command_name}")


def to_jsonable(value: object) -> object:
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
