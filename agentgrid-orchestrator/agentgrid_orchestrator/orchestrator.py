from __future__ import annotations

from agentgrid_orchestrator.models import OrchestratorDecision


class Orchestrator:
    def __init__(self, context_builder=None, router=None, policy_engine=None, agent_manager=None) -> None:
        self.context_builder = context_builder
        self.router = router
        self.policy_engine = policy_engine
        self.agent_manager = agent_manager

    def handle_request(self, request: str, project_id: str | None = None) -> OrchestratorDecision:
        context = self._context(project_id or "default", request)
        route = self.router.route(request, context) if self.router else None
        policy = self.policy_engine.decide("delegate user request", {"request": request}) if self.policy_engine else "ALLOW"
        policy_value = getattr(policy, "value", policy)
        if policy_value == "DENY":
            return OrchestratorDecision("DENY", "policy denied request", project_id=project_id)
        if policy_value == "ASK_USER":
            return OrchestratorDecision("ASK_USER", "policy requires user approval", project_id=project_id)
        if route is None:
            return OrchestratorDecision("NOOP", "no router configured", project_id=project_id)
        route_type = getattr(route.route, "value", route.route)
        return OrchestratorDecision(route_type, route.reason, project_id=route.project_id, agent_id=route.agent_id)

    def handle_event(self, event: dict[str, object]) -> OrchestratorDecision:
        return OrchestratorDecision("EVENT_RECEIVED", "event accepted for high-level handling", agent_id=event.get("agent_id"), details=event)

    def _context(self, project_id: str, request: str) -> dict[str, object]:
        if not self.context_builder:
            return {"project_id": project_id, "agents": []}
        context = self.context_builder.get_context(project_id, query=request, level="summary")
        return context.to_dict() if hasattr(context, "to_dict") else dict(context)
