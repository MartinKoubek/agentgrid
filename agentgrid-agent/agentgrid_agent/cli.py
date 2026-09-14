from __future__ import annotations

import argparse
import json
import sys

from tmuxio import TmuxClient

from agentgrid_agent.adapters import default_adapters
from agentgrid_agent.manager import AgentManager
from agentgrid_agent.registry import FileAgentRegistry


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    parser = argparse.ArgumentParser(prog="agentgrid-agent")
    parser.add_argument("--registry", help="path to agent registry JSON")
    parser.add_argument("--socket-name", help="tmux socket name")
    parser.add_argument("--socket-path", help="tmux socket path")
    parser.add_argument("--tmux", default="tmux", help="tmux executable path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    start = subparsers.add_parser("start", parents=[common], help="start an agent")
    start.add_argument("--adapter", default="fake")
    start.add_argument("--command")
    start.add_argument("--pane")
    start.add_argument("--session", default="agentgrid-agents")
    start.add_argument("--window")
    start.add_argument("--cwd")

    subparsers.add_parser("list", parents=[common], help="list agents")

    inspect = subparsers.add_parser("inspect", parents=[common], help="inspect an agent")
    inspect.add_argument("agent_id")

    send = subparsers.add_parser("send", parents=[common], help="send text to an agent")
    send.add_argument("agent_id")
    send.add_argument("text")

    read = subparsers.add_parser("read", parents=[common], help="read agent output")
    read.add_argument("agent_id")

    stop = subparsers.add_parser("stop", parents=[common], help="stop an agent")
    stop.add_argument("agent_id")

    restart = subparsers.add_parser("restart", parents=[common], help="restart an agent")
    restart.add_argument("agent_id")

    alive = subparsers.add_parser("is-alive", parents=[common], help="check whether an agent is alive")
    alive.add_argument("agent_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tmux = TmuxClient(executable=args.tmux, socket_name=args.socket_name, socket_path=args.socket_path)
    manager = AgentManager(tmux=tmux, registry=FileAgentRegistry(args.registry), adapters=default_adapters(tmux))

    try:
        output = run_command(manager, args)
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


def run_command(manager: AgentManager, args: argparse.Namespace) -> object:
    if args.command_name == "start":
        return manager.start(
            adapter=args.adapter,
            command=args.command,
            pane_id=args.pane,
            session=args.session,
            window=args.window,
            cwd=args.cwd,
        )
    if args.command_name == "list":
        return manager.list()
    if args.command_name == "inspect":
        return manager.inspect(args.agent_id)
    if args.command_name == "send":
        return manager.send(args.agent_id, args.text)
    if args.command_name == "read":
        return manager.read(args.agent_id)
    if args.command_name == "stop":
        return manager.stop(args.agent_id)
    if args.command_name == "restart":
        return manager.restart(args.agent_id)
    if args.command_name == "is-alive":
        return {"alive": manager.is_alive(args.agent_id)}
    raise ValueError(f"unknown command: {args.command_name}")


def to_jsonable(value: object) -> object:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


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
