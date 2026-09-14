from __future__ import annotations

from agentgrid_policy.models import PolicyDecision


class PolicyEngine:
    def decide(self, action: str, details: dict[str, object] | None = None) -> PolicyDecision:
        text = f"{action} {details or {}}".lower()
        if "force-push" in text or "force push" in text:
            return PolicyDecision.DENY
        if any(word in text for word in ["delete", "remove directory", "rm -rf", "deploy", "publish"]):
            return PolicyDecision.ASK_USER
        return PolicyDecision.ALLOW
