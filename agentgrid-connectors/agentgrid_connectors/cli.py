from __future__ import annotations

import argparse, json
from agentgrid_connectors.connectors import default_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-connectors"); parser.add_argument("--json", action="store_true"); parser.add_argument("command", choices=["poll"])
    args = parser.parse_args(argv); events = default_registry().poll_all()
    print(json.dumps([event.to_dict() for event in events], indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
