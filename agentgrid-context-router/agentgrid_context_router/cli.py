from __future__ import annotations

import argparse, json
from agentgrid_context_router import ContextRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-context-router")
    parser.add_argument("request"); parser.add_argument("--context-json", default="{}"); parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    decision = ContextRouter().route(args.request, json.loads(args.context_json))
    print(json.dumps(decision.to_dict(), indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
