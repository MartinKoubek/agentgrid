from __future__ import annotations

import argparse, json, sys
from agentgrid_persistence import DocumentStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentgrid-persistence")
    parser.add_argument("--store")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    put = sub.add_parser("put")
    put.add_argument("namespace"); put.add_argument("key"); put.add_argument("value_json")
    get = sub.add_parser("get")
    get.add_argument("namespace"); get.add_argument("key")
    delete = sub.add_parser("delete")
    delete.add_argument("namespace"); delete.add_argument("key")
    list_p = sub.add_parser("list")
    list_p.add_argument("namespace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = DocumentStore(args.store)
    try:
        output = run(store, args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}) if args.json else f"error: {exc}", file=sys.stderr)
        return 1
    if output is not None:
        print(json.dumps(output, indent=2 if args.json else None, sort_keys=not args.json))
    return 0


def run(store: DocumentStore, args: argparse.Namespace) -> object:
    if args.command == "put":
        store.put(args.namespace, args.key, json.loads(args.value_json)); return {"ok": True}
    if args.command == "get":
        return store.get(args.namespace, args.key)
    if args.command == "delete":
        store.delete(args.namespace, args.key); return {"ok": True}
    if args.command == "list":
        return store.list(args.namespace)
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
