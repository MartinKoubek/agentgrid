from __future__ import annotations

import argparse, json
from pathlib import Path

from agentgrid_orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="agentgrid-orchestrator")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--runtime-root")
    parser.add_argument("--socket-name")
    parser.add_argument("--agent-adapter", default="fake")
    parser.add_argument("--agent-session", default="agentgrid-agents")
    sub = parser.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request", parents=[common]); request.add_argument("text"); request.add_argument("--project-id")
    event = sub.add_parser("event", parents=[common]); event.add_argument("event_json")
    open_project = sub.add_parser("open-project", parents=[common]); open_project.add_argument("project_id"); open_project.add_argument("--path", default="."); open_project.add_argument("--name")
    sub.add_parser("scan", parents=[common])
    sub.add_parser("dispatch", parents=[common])
    args = parser.parse_args(argv)
    if args.runtime_root:
        from agentgrid_orchestrator.runtime import AgentGridRuntime

        runtime = AgentGridRuntime(
            Path(args.runtime_root),
            socket_name=args.socket_name,
            agent_adapter=args.agent_adapter,
            agent_session=args.agent_session,
        )
        if args.command == "request":
            output = runtime.orchestrator.handle_request(args.text, args.project_id)
        elif args.command == "event":
            output = runtime.orchestrator.handle_event(json.loads(args.event_json))
        elif args.command == "open-project":
            output = runtime.project_manager.open_project(args.project_id, args.path, args.name)
        elif args.command == "scan":
            output = runtime.enqueue_monitor_events()
        elif args.command == "dispatch":
            output = runtime.dispatch_next()
        else:
            raise ValueError(args.command)
    else:
        if args.command not in {"request", "event"}:
            parser.error(f"{args.command} requires --runtime-root")
        orchestrator = Orchestrator()
        output = orchestrator.handle_request(args.text, args.project_id) if args.command == "request" else orchestrator.handle_event(json.loads(args.event_json))
    print(json.dumps(to_jsonable(output), indent=2 if args.json else None, sort_keys=not args.json))
    return 0


def to_jsonable(value: object) -> object:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


if __name__ == "__main__": raise SystemExit(main())
