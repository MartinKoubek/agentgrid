from __future__ import annotations

import argparse, json
from pathlib import Path

from agentgrid_orchestrator import Orchestrator
from agentgrid_orchestrator.master import CodexMasterProvider, FakeMasterProvider


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="agentgrid-orchestrator")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--runtime-root")
    parser.add_argument("--socket-name")
    parser.add_argument("--agent-adapter", default="fake")
    parser.add_argument("--agent-session", default="agentgrid-agents")
    parser.add_argument("--master-provider", choices=["fake", "codex"], default="fake")
    sub = parser.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request", parents=[common]); request.add_argument("text"); request.add_argument("--project-id")
    master_request = sub.add_parser("master-request", parents=[common]); master_request.add_argument("text"); master_request.add_argument("--project-id"); master_request.add_argument("--request-id"); master_request.add_argument("--allow-continue", action="store_true")
    event = sub.add_parser("event", parents=[common]); event.add_argument("event_json")
    open_project = sub.add_parser("open-project", parents=[common]); open_project.add_argument("project_id"); open_project.add_argument("--path", default="."); open_project.add_argument("--name")
    master_history = sub.add_parser("master-history", parents=[common]); master_history.add_argument("--limit", type=int, default=20)
    sub.add_parser("scan", parents=[common])
    sub.add_parser("dispatch", parents=[common])
    args = parser.parse_args(argv)
    if args.runtime_root:
        from agentgrid_orchestrator.runtime import AgentGridRuntime

        master_provider = FakeMasterProvider()
        if args.master_provider == "codex":
            master_provider = CodexMasterProvider(cwd=Path(args.runtime_root))
        runtime = AgentGridRuntime(
            Path(args.runtime_root),
            socket_name=args.socket_name,
            agent_adapter=args.agent_adapter,
            agent_session=args.agent_session,
            master_provider=master_provider,
        )
        if args.command == "request":
            output = runtime.orchestrator.handle_request(args.text, args.project_id)
        elif args.command == "master-request":
            output = runtime.master.handle_request(args.text, args.project_id, args.request_id, args.allow_continue)
        elif args.command == "event":
            output = runtime.orchestrator.handle_event(json.loads(args.event_json))
        elif args.command == "open-project":
            output = runtime.project_manager.open_project(args.project_id, args.path, args.name)
        elif args.command == "master-history":
            output = runtime.master_requests.list(args.limit)
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
    return exit_code_for_output(output, command=args.command)


def to_jsonable(value: object) -> object:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def exit_code_for_output(value: object, command: str | None = None) -> int:
    if command in {"scan", "dispatch", "master-history", "open-project"}:
        error = getattr(value, "error", None)
        return 1 if error else 0
    action = _action_for_output(value)
    if action in {"ASK_USER", "PARK", "AGENT_WAITING_INPUT", "WAITING_USER"}:
        return 2
    if action in {
        "DENY",
        "MASTER_FAILED",
        "MASTER_DECISION_REJECTED",
        "AGENT_START_FAILED",
        "AGENT_SEND_FAILED",
        "AGENT_FAILED",
        "TEMPORARY_FAILURE",
        "REQUEUE",
        "RETRY",
    }:
        return 1
    error = getattr(value, "error", None)
    if error:
        return 1
    return 0


def _action_for_output(value: object) -> str | None:
    action = getattr(value, "action", None)
    if action is not None:
        return str(action)
    if isinstance(value, dict):
        action = value.get("action") or value.get("decision")
        return str(action) if action is not None else None
    return None


if __name__ == "__main__": raise SystemExit(main())
