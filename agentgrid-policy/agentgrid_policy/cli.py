from __future__ import annotations

import argparse, json
from agentgrid_policy import PolicyEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentgrid-policy")
    parser.add_argument("action"); parser.add_argument("--details-json", default="{}"); parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    decision = PolicyEngine().decide(args.action, json.loads(args.details_json))
    payload = {"decision": decision.value}
    print(json.dumps(payload, indent=2 if args.json else None, sort_keys=not args.json)); return 0


if __name__ == "__main__": raise SystemExit(main())
