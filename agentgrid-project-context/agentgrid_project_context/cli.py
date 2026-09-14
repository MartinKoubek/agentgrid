from __future__ import annotations

import argparse, json
from agentgrid_project_context import ProjectContextBuilder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-project-context")
    parser.add_argument("project_id"); parser.add_argument("--query"); parser.add_argument("--level", default="summary"); parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    context = ProjectContextBuilder().get_context(args.project_id, args.query, args.level)
    print(json.dumps(context.to_dict(), indent=2 if args.json else None, sort_keys=not args.json))
    return 0


if __name__ == "__main__": raise SystemExit(main())
