from __future__ import annotations

import argparse, json
from agentgrid_orchestrator import Orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-orchestrator")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request"); request.add_argument("text"); request.add_argument("--project-id")
    event = sub.add_parser("event"); event.add_argument("event_json")
    args = parser.parse_args(argv)
    orchestrator = Orchestrator()
    output = orchestrator.handle_request(args.text, args.project_id) if args.command == "request" else orchestrator.handle_event(json.loads(args.event_json))
    print(json.dumps(output.to_dict(), indent=2 if args.json else None, sort_keys=not args.json))
    return 0


if __name__ == "__main__": raise SystemExit(main())
