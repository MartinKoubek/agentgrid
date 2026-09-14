from __future__ import annotations

import argparse, json
from agentgrid_cross_context import CrossSystemContextResolver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-cross-context"); parser.add_argument("event_json"); parser.add_argument("--projects-json", default="[]"); parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv); result = CrossSystemContextResolver().resolve(json.loads(args.event_json), json.loads(args.projects_json))
    print(json.dumps(result.to_dict(), indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
