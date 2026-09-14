from __future__ import annotations

import argparse, json, sys
from agentgrid_project_manager.manager import ProjectManager


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="agentgrid-project-manager")
    parser.add_argument("--store")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    open_p = sub.add_parser("open", parents=[common])
    open_p.add_argument("project_id")
    open_p.add_argument("--path", required=True)
    open_p.add_argument("--name")
    open_p.add_argument("--repository")
    sub.add_parser("list", parents=[common]).add_argument("--include-closed", action="store_true")
    inspect = sub.add_parser("inspect", parents=[common])
    inspect.add_argument("project_id")
    close = sub.add_parser("close", parents=[common])
    close.add_argument("project_id")
    sub.add_parser("last", parents=[common])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = ProjectManager(args.store)
    try:
        output = run(manager, args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(to_jsonable(output), indent=2 if args.json else None, sort_keys=not args.json))
    return 0


def run(manager: ProjectManager, args: argparse.Namespace) -> object:
    if args.command == "open":
        return manager.open_project(args.project_id, args.path, args.name, args.repository)
    if args.command == "list":
        return manager.list_projects(include_closed=args.include_closed)
    if args.command == "inspect":
        return manager.get_project(args.project_id)
    if args.command == "close":
        return manager.close_project(args.project_id)
    if args.command == "last":
        return manager.get_last_active_project()
    raise ValueError(args.command)


def to_jsonable(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
