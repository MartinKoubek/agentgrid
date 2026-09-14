from __future__ import annotations

import argparse, json
from agentgrid_recovery import RecoveryManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-recovery"); parser.add_argument("--json", action="store_true"); parser.add_argument("command", choices=["reconcile"])
    args = parser.parse_args(argv); report = RecoveryManager().reconcile()
    print(json.dumps(report.to_dict(), indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
