from __future__ import annotations

from agentgrid_orchestrator.models import OrchestratorDecision


class Orchestrator:
    def __init__(
        self,
        context_builder=None,
        router=None,
        policy_engine=None,
        agent_manager=None,
        project_manager=None,
        agent_adapter: str = "fake",
        agent_session: str = "agentgrid-agents",
    ) -> None:
        self.context_builder = context_builder
        self.router = router
        self.policy_engine = policy_engine
        self.agent_manager = agent_manager
        self.project_manager = project_manager
        self.agent_adapter = agent_adapter
        self.agent_session = agent_session

    def handle_request(self, request: str, project_id: str | None = None) -> OrchestratorDecision:
        target_project_id = project_id or "default"
        context = self._context(target_project_id, request)
        route = self.router.route(request, context) if self.router else None
        policy = self.policy_engine.decide("delegate user request", {"request": request}) if self.policy_engine else "ALLOW"
        policy_value = getattr(policy, "value", policy)
        if policy_value == "DENY":
            return OrchestratorDecision("DENY", "policy denied request", project_id=target_project_id)
        if policy_value == "ASK_USER":
            return OrchestratorDecision("ASK_USER", "policy requires user approval", project_id=target_project_id)
        if route is None:
            return OrchestratorDecision("NOOP", "no router configured", project_id=target_project_id)
        route_type = getattr(route.route, "value", route.route)

        if route_type == "CONTINUE_AGENT" and route.agent_id:
            if self.agent_manager:
                self.agent_manager.send(route.agent_id, request)
                self._remember_agent_task(route.project_id or target_project_id, route.agent_id, request)
            return OrchestratorDecision(
                route_type,
                route.reason,
                project_id=route.project_id or target_project_id,
                agent_id=route.agent_id,
                details={"request": request},
            )

        if route_type == "START_AGENT":
            if not self.agent_manager:
                return OrchestratorDecision(route_type, route.reason, project_id=route.project_id or target_project_id)
            agent = self.agent_manager.start(adapter=self.agent_adapter, session=self.agent_session)
            self.agent_manager.send(agent.id, request)
            self._attach_agent(route.project_id or target_project_id, agent.id, request)
            return OrchestratorDecision(
                route_type,
                route.reason,
                project_id=route.project_id or target_project_id,
                agent_id=agent.id,
                details={"request": request},
            )

        return OrchestratorDecision(route_type, route.reason, project_id=route.project_id, agent_id=route.agent_id)

    def handle_event(self, event: dict[str, object]) -> OrchestratorDecision:
        return OrchestratorDecision(
            "EVENT_RECEIVED",
            "event accepted for high-level handling",
            project_id=_str_or_none(event.get("project_id")),
            agent_id=_str_or_none(event.get("agent_id")),
            details=event,
        )

    def _context(self, project_id: str, request: str) -> dict[str, object]:
        if not self.context_builder:
            return {"project_id": project_id, "agents": []}
        context = self.context_builder.get_context(project_id, query=request, level="summary")
        return context.to_dict() if hasattr(context, "to_dict") else dict(context)

    def _attach_agent(self, project_id: str, agent_id: str, request: str) -> None:
        if not self.project_manager:
            return
        try:
            project = self.project_manager.get_project(project_id)
        except Exception:
            return
        if agent_id not in project.active_agents:
            project.active_agents.append(agent_id)
        project.config.setdefault("agent_tasks", {})[agent_id] = request
        project.touch()
        self.project_manager.save(project)

    def _remember_agent_task(self, project_id: str, agent_id: str, request: str) -> None:
        if not self.project_manager:
            return
        try:
            project = self.project_manager.get_project(project_id)
        except Exception:
            return
        if agent_id not in project.active_agents:
            project.active_agents.append(agent_id)
        existing = str(project.config.setdefault("agent_tasks", {}).get(agent_id, ""))
        if request not in existing:
            project.config["agent_tasks"][agent_id] = f"{existing}\n{request}".strip()
        project.touch()
        self.project_manager.save(project)


def _str_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
