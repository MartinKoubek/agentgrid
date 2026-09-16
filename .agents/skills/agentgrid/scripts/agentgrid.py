#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = run(args)
    except subprocess.CalledProcessError as exc:
        payload = {
            "ok": False,
            "error": f"command failed with exit code {exc.returncode}",
            "command": exc.cmd,
            "stdout": parse_json_or_text(exc.stdout),
            "stderr": exc.stderr,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return exc.returncode or 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(to_jsonable(output), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentgrid-skill")
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--socket-name", required=True)
    parser.add_argument("--agent-adapter", default="codex")
    parser.add_argument("--agent-session", default="agentgrid-agents")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--project-id")

    projects = sub.add_parser("projects")
    projects.add_argument("--include-closed", action="store_true")

    agents = sub.add_parser("agents")
    agents.add_argument("--project-id")

    inspect_agent = sub.add_parser("inspect-agent")
    inspect_agent.add_argument("agent_id")

    read_agent = sub.add_parser("read-agent")
    read_agent.add_argument("agent_id")
    read_agent.add_argument("--lines", type=int, default=120)

    request = sub.add_parser("request")
    request.add_argument("--project-id", required=True)
    request.add_argument("--text", required=True)
    request.add_argument("--request-id")

    send = sub.add_parser("send-agent")
    send.add_argument("--project-id", required=True)
    send.add_argument("--agent-id", required=True)
    send.add_argument("--text", required=True)
    send.add_argument("--request-id")

    cont = sub.add_parser("continue")
    cont.add_argument("--project-id", required=True)
    cont.add_argument("--agent-id", required=True)
    cont.add_argument("--text", required=True)
    cont.add_argument("--confirm-ready", action="store_true")
    cont.add_argument("--request-id")

    sub.add_parser("scan-dispatch")

    stop = sub.add_parser("stop-agent")
    stop.add_argument("agent_id")

    return parser


def run(args: argparse.Namespace) -> Any:
    if args.command == "status":
        return {
            "ok": True,
            "runtime_root": args.runtime_root,
            "socket_name": args.socket_name,
            "agent_adapter": args.agent_adapter,
            "project": get_project(args.project_id, args) if args.project_id else None,
            "agents": list_agents(args),
            "events": orchestrator(args, "scan"),
        }
    if args.command == "projects":
        command = [str(REPO_ROOT / "bin" / "agentgrid-project-manager"), "--store", project_store(args), "list", "--json"]
        if args.include_closed:
            command.append("--include-closed")
        return run_json(command)
    if args.command == "agents":
        agents = list_agents(args)
        if args.project_id:
            project = get_project(args.project_id, args)
            owned = set(project.get("agents", [])) if isinstance(project, dict) else set()
            agents = [agent for agent in agents if agent.get("id") in owned]
        return agents
    if args.command == "inspect-agent":
        return agent(args, "inspect", args.agent_id)
    if args.command == "read-agent":
        inspected = agent(args, "inspect", args.agent_id)
        text = agent(args, "read", args.agent_id)
        if isinstance(text, str) and args.lines is not None:
            text = "\n".join(text.splitlines()[-args.lines:])
        return {"agent": inspected, "output": text}
    if args.command == "request":
        request_id = args.request_id or new_request_id()
        result = orchestrator(args, "request", args.text, "--project-id", args.project_id)
        return {"request_id": request_id, "result": result}
    if args.command == "send-agent":
        ensure_agent_owned(args.project_id, args.agent_id, args)
        sent = agent(args, "send", args.agent_id, args.text)
        return {"ok": True, "action": "SEND_AGENT", "request_id": args.request_id or new_request_id(), "agent": sent}
    if args.command == "continue":
        if not args.confirm_ready:
            return {
                "ok": False,
                "action": "PARK",
                "project_id": args.project_id,
                "agent_id": args.agent_id,
                "reason": "worker readiness is unknown; rerun with --confirm-ready after inspection",
            }
        ensure_agent_owned(args.project_id, args.agent_id, args)
        inspected = agent(args, "inspect", args.agent_id)
        if inspected.get("state") != "RUNNING":
            return {
                "ok": False,
                "action": "PARK",
                "project_id": args.project_id,
                "agent_id": args.agent_id,
                "reason": "selected worker is not running",
                "agent": inspected,
            }
        sent = agent(args, "send", args.agent_id, args.text)
        return {"ok": True, "action": "CONTINUE_AGENT", "request_id": args.request_id or new_request_id(), "agent": sent}
    if args.command == "scan-dispatch":
        events = orchestrator(args, "scan")
        dispatches = []
        for _ in range(10):
            dispatched = orchestrator(args, "dispatch")
            dispatches.append(dispatched)
            if not dispatched.get("delivered") or dispatched.get("decision") in {"PARK", "REQUEUE"}:
                break
        return {"events": events, "dispatches": dispatches}
    if args.command == "stop-agent":
        return agent(args, "stop", args.agent_id)
    raise ValueError(args.command)


def orchestrator(args: argparse.Namespace, *parts: str) -> Any:
    return run_json([
        str(REPO_ROOT / "bin" / "agentgrid-orchestrator"),
        "--runtime-root", args.runtime_root,
        "--socket-name", args.socket_name,
        "--agent-adapter", args.agent_adapter,
        "--agent-session", args.agent_session,
        *parts,
        "--json",
    ])


def agent(args: argparse.Namespace, *parts: str) -> Any:
    return run_json([
        str(REPO_ROOT / "bin" / "agentgrid-agent"),
        "--registry", str(Path(args.runtime_root) / "agents.sqlite3"),
        "--socket-name", args.socket_name,
        *parts,
        "--json",
    ])


def list_agents(args: argparse.Namespace) -> list[dict[str, Any]]:
    value = agent(args, "list")
    return value if isinstance(value, list) else []


def get_project(project_id: str, args: argparse.Namespace) -> Any:
    return run_json([
        str(REPO_ROOT / "bin" / "agentgrid-project-manager"),
        "--store", project_store(args),
        "inspect", project_id,
        "--json",
    ])


def ensure_agent_owned(project_id: str, agent_id: str, args: argparse.Namespace) -> None:
    project = get_project(project_id, args)
    agents = project.get("agents", []) if isinstance(project, dict) else []
    if agent_id not in agents:
        raise ValueError(f"agent {agent_id} does not belong to project {project_id}")


def project_store(args: argparse.Namespace) -> str:
    return str(Path(args.runtime_root) / "projects.sqlite3")


def run_json(command: list[str]) -> Any:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command, completed.stdout, completed.stderr)
    return parse_json_or_text(completed.stdout)


def parse_json_or_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def new_request_id() -> str:
    return f"skill-{uuid.uuid4().hex}"


if __name__ == "__main__":
    raise SystemExit(main())
