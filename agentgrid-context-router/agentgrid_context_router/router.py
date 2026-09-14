from __future__ import annotations

import re

from agentgrid_context_router.models import RouteDecision, RouteType


STOP_WORDS = {
    "about",
    "agent",
    "build",
    "change",
    "code",
    "continue",
    "debug",
    "feature",
    "fix",
    "implement",
    "investigate",
    "issue",
    "please",
    "project",
    "request",
    "task",
    "test",
    "update",
    "work",
}


class ContextRouter:
    def route(self, request: str, context: dict[str, object]) -> RouteDecision:
        request_tokens = set(_tokens(request))
        agents = context.get("agents") or []
        for agent in agents:
            haystack = " ".join(str(value) for value in agent.values())
            overlap = request_tokens & set(_tokens(haystack))
            if agent.get("state") == "RUNNING" and overlap:
                return RouteDecision(
                    RouteType.CONTINUE_AGENT,
                    context.get("project_id"),
                    str(agent.get("id")),
                    0.75,
                    "request overlaps a running agent",
                )
        if context.get("project"):
            return RouteDecision(RouteType.START_AGENT, context.get("project_id"), confidence=0.6, reason="known current project")
        return RouteDecision(RouteType.CREATE_PROJECT, confidence=0.4, reason="no project context available")


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 3 and token not in STOP_WORDS]
