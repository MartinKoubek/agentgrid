from __future__ import annotations

import argparse, json, sys
from agentgrid_execution import ExecutionManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-execution"); parser.add_argument("--json", action="store_true")
    parser.add_argument("--cwd"); parser.add_argument("--timeout", type=float); parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv); command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        print("error: command required", file=sys.stderr); return 1
    result = ExecutionManager().run(command, cwd=args.cwd, timeout=args.timeout)
    print(json.dumps(result.to_dict(), indent=2 if args.json else None, sort_keys=not args.json)); return result.exit_code


if __name__ == "__main__": raise SystemExit(main())
