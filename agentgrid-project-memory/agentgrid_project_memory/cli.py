from __future__ import annotations

import argparse, json, sys
from agentgrid_project_memory import ProjectMemory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentgrid-project-memory")
    parser.add_argument("--store"); parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add"); add.add_argument("project_id"); add.add_argument("category"); add.add_argument("content")
    list_p = sub.add_parser("list"); list_p.add_argument("project_id"); list_p.add_argument("--category"); list_p.add_argument("--limit", type=int, default=50)
    search = sub.add_parser("search"); search.add_argument("project_id"); search.add_argument("query"); search.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv); memory = ProjectMemory(args.store)
    try:
        output = run(memory, args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}) if args.json else f"error: {exc}", file=sys.stderr); return 1
    print(json.dumps(to_jsonable(output), indent=2 if args.json else None, sort_keys=not args.json)); return 0


def run(memory: ProjectMemory, args: argparse.Namespace) -> object:
    if args.command == "add": return memory.add(args.project_id, args.category, args.content)
    if args.command == "list": return memory.list(args.project_id, args.category, args.limit)
    if args.command == "search": return memory.search(args.project_id, args.query, args.limit)
    raise ValueError(args.command)


def to_jsonable(value: object) -> object:
    if hasattr(value, "to_dict"): return value.to_dict()
    if isinstance(value, list): return [to_jsonable(item) for item in value]
    return value


if __name__ == "__main__": raise SystemExit(main())
