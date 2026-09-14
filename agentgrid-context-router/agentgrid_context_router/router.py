from __future__ import annotations

from agentgrid_context_router.models import RouteDecision, RouteType


class ContextRouter:
    def route(self, request: str, context: dict[str, object]) -> RouteDecision:
        request_l = request.lower()
        agents = context.get("agents") or []
        for agent in agents:
            haystack = " ".join(str(value).lower() for value in agent.values())
            if agent.get("state") == "RUNNING" and any(token in haystack for token in request_l.split() if len(token) > 3):
                return RouteDecision(RouteType.CONTINUE_AGENT, context.get("project_id"), str(agent.get("id")), 0.75, "request overlaps a running agent")
        if context.get("project"):
            return RouteDecision(RouteType.START_AGENT, context.get("project_id"), confidence=0.6, reason="known current project")
        return RouteDecision(RouteType.CREATE_PROJECT, confidence=0.4, reason="no project context available")
