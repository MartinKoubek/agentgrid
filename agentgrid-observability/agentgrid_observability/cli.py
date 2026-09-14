from __future__ import annotations

import argparse, json
from agentgrid_observability import DiagnosticLogger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-observability"); parser.add_argument("--log", required=True); parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True); log = sub.add_parser("log"); log.add_argument("event"); log.add_argument("--project-id"); log.add_argument("--agent-id"); sub.add_parser("read")
    args = parser.parse_args(argv); logger = DiagnosticLogger(args.log)
    output = logger.log(args.event, args.project_id, args.agent_id) if args.command == "log" else logger.read()
    print(json.dumps(output, indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
