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
        policy_decision = self._policy_decision(request, target_project_id)
        if policy_decision is not None:
            return policy_decision
        if route is None:
            return OrchestratorDecision("NOOP", "no router configured", project_id=target_project_id)
        return self.execute_route(request, route, target_project_id, enforce_policy=False)

    def execute_route(
        self,
        request: str,
        route,
        target_project_id: str | None = None,
        enforce_policy: bool = True,
    ) -> OrchestratorDecision:
        target_project_id = target_project_id or getattr(route, "project_id", None) or "default"
        route_type = getattr(route.route, "value", route.route)

        if enforce_policy:
            policy_decision = self._policy_decision(
                request,
                target_project_id,
                route_type=route_type,
                agent_id=getattr(route, "agent_id", None),
            )
            if policy_decision is not None:
                return policy_decision

        if route_type == "CONTINUE_AGENT" and route.agent_id:
            if self.agent_manager:
                route_project_id = route.project_id or target_project_id
                attempt_error = self._remember_agent_attempt(route_project_id, route.agent_id, request)
                if attempt_error is not None:
                    return OrchestratorDecision(
                        "AGENT_SEND_FAILED",
                        "continuation agent task attempt could not be recorded",
                        project_id=route_project_id,
                        agent_id=route.agent_id,
                        details={
                            "request": request,
                            "error": attempt_error,
                            "delivery_uncertain": False,
                        },
                    )
                try:
                    self.agent_manager.send(route.agent_id, request)
                except Exception as exc:
                    return OrchestratorDecision(
                        "AGENT_SEND_FAILED",
                        "continuation agent prompt failed",
                        project_id=route_project_id,
                        agent_id=route.agent_id,
                        details={
                            "request": request,
                            "error": str(exc),
                            "delivery_uncertain": True,
                        },
                    )
                task_error = self._remember_agent_task(route_project_id, route.agent_id, request)
                if task_error is not None:
                    return OrchestratorDecision(
                        "AGENT_SEND_FAILED",
                        "continuation agent task delivery could not be recorded",
                        project_id=route_project_id,
                        agent_id=route.agent_id,
                        details={
                            "request": request,
                            "error": task_error,
                            "delivery_uncertain": True,
                        },
                    )
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
            route_project_id = route.project_id or target_project_id
            project, project_error = self._project(route_project_id)
            if project_error is not None:
                return OrchestratorDecision(
                    "AGENT_START_FAILED",
                    "project is unavailable for agent startup",
                    project_id=route_project_id,
                    details={"request": request, "error": project_error},
                )
            agent = self.agent_manager.start(
                adapter=self.agent_adapter,
                session=self.agent_session,
                cwd=getattr(project, "path", None),
            )
            association_error = self._attach_agent(route_project_id, agent.id, request)
            agent_state = _state_value(getattr(agent, "state", None))
            agent_error = getattr(agent, "error", None)
            if association_error is not None:
                cleanup = self._cleanup_unassociated_agent(agent.id)
                return OrchestratorDecision(
                    "AGENT_START_FAILED",
                    "agent project association failed",
                    project_id=route_project_id,
                    agent_id=agent.id,
                    details={
                        "request": request,
                        "agent_state": agent_state,
                        "error": association_error,
                        "project_association_error": association_error,
                        "cleanup": cleanup,
                    },
                )
            if agent_state == "FAILED":
                return OrchestratorDecision(
                    "AGENT_START_FAILED",
                    "agent startup failed",
                    project_id=route_project_id,
                    agent_id=agent.id,
                    details={
                        "request": request,
                        "agent_state": agent_state,
                        "error": agent_error,
                        "project_association_error": association_error,
                    },
                )
            try:
                self.agent_manager.send(agent.id, request)
            except Exception as exc:
                return OrchestratorDecision(
                    "AGENT_SEND_FAILED",
                    "initial agent prompt failed",
                    project_id=route_project_id,
                    agent_id=agent.id,
                    details={
                        "request": request,
                        "error": str(exc),
                        "project_association_error": association_error,
                        "delivery_uncertain": True,
                    },
                )
            return OrchestratorDecision(
                route_type,
                route.reason,
                project_id=route_project_id,
                agent_id=agent.id,
                details={"request": request, "project_association_error": association_error},
            )

        return OrchestratorDecision(route_type, route.reason, project_id=route.project_id, agent_id=route.agent_id)

    def handle_event(self, event: dict[str, object]) -> OrchestratorDecision:
        event_type = str(event.get("type", ""))
        agent_id = _str_or_none(event.get("agent_id"))
        project_id = _str_or_none(event.get("project_id"))
        runtime_state = self._agent_runtime_state(agent_id)

        if project_id:
            self._touch_project(project_id)

        if event_type == "AGENT_STARTED":
            return OrchestratorDecision(
                "AGENT_STARTED",
                "agent start event acknowledged",
                project_id=project_id,
                agent_id=agent_id,
                details={"event": event, "runtime_state": runtime_state},
            )
        if event_type == "AGENT_OUTPUT_CHANGED":
            return OrchestratorDecision(
                "AGENT_OUTPUT_CHANGED",
                "agent output change recorded",
                project_id=project_id,
                agent_id=agent_id,
                details={"event": event, "runtime_state": runtime_state},
            )
        if event_type in {"AGENT_EXITED", "PROCESS_EXITED"}:
            return OrchestratorDecision(
                event_type,
                "agent/process exit acknowledged",
                project_id=project_id,
                agent_id=agent_id,
                details={"event": event, "runtime_state": runtime_state},
            )
        if event_type == "AGENT_FAILED":
            event_details = event.get("details", {})
            error = event.get("error")
            if error is None and isinstance(event_details, dict):
                error = event_details.get("error")
            return OrchestratorDecision(
                "AGENT_FAILED",
                "agent failure requires attention",
                project_id=project_id,
                agent_id=agent_id,
                details={"event": event, "runtime_state": runtime_state, "error": error},
            )
        if event_type in {"AGENT_WAITING_INPUT", "WAITING_USER"}:
            return OrchestratorDecision(
                "ASK_USER",
                "agent is waiting for user input",
                project_id=project_id,
                agent_id=agent_id,
                details={"event": event, "runtime_state": runtime_state},
            )
        return OrchestratorDecision(
            "EVENT_RECEIVED",
            "event accepted without specialized handling",
            project_id=project_id,
            agent_id=agent_id,
            details=event,
        )

    def _context(self, project_id: str, request: str) -> dict[str, object]:
        if not self.context_builder:
            return {"project_id": project_id, "agents": []}
        context = self.context_builder.get_context(project_id, query=request, level="summary")
        return context.to_dict() if hasattr(context, "to_dict") else dict(context)

    def _policy_decision(
        self,
        request: str,
        project_id: str,
        route_type: str | None = None,
        agent_id: str | None = None,
    ) -> OrchestratorDecision | None:
        if not self.policy_engine:
            return None
        details = {"request": request, "project_id": project_id}
        if route_type is not None:
            details["route_type"] = route_type
        if agent_id is not None:
            details["agent_id"] = agent_id
        policy = self.policy_engine.decide("delegate user request", details)
        policy_value = getattr(policy, "value", policy)
        if policy_value == "DENY":
            return OrchestratorDecision(
                "DENY",
                "policy denied request",
                project_id=project_id,
                agent_id=agent_id,
                details={"request": request, "route_type": route_type},
            )
        if policy_value == "ASK_USER":
            return OrchestratorDecision(
                "ASK_USER",
                "policy requires user approval",
                project_id=project_id,
                agent_id=agent_id,
                details={"request": request, "route_type": route_type},
            )
        return None

    def _attach_agent(self, project_id: str, agent_id: str, request: str) -> str | None:
        if not self.project_manager:
            return "project manager is not configured"
        try:
            project = self.project_manager.get_project(project_id)
            project.add_agent(agent_id)
            project.config.setdefault("agent_tasks", {})[agent_id] = request
            project.touch()
            self.project_manager.save(project)
        except Exception as exc:
            return f"project association failed: {exc}"
        return None

    def _cleanup_unassociated_agent(self, agent_id: str) -> dict[str, object]:
        if not self.agent_manager:
            return {"attempted": False, "error": "agent manager is not configured"}
        result: dict[str, object] = {"attempted": True}
        try:
            stopped = self.agent_manager.stop(agent_id)
            result["state"] = _state_value(getattr(stopped, "state", None))
        except Exception as exc:
            result["stop_error"] = str(exc)
        try:
            result["alive"] = bool(self.agent_manager.is_alive(agent_id))
        except Exception as exc:
            result["liveness_error"] = str(exc)
            result["alive"] = "unknown"
        if result.get("alive") is True:
            result["orphan_risk"] = True
        return result

    def _project(self, project_id: str):
        if not self.project_manager:
            return None, "project manager is not configured"
        try:
            return self.project_manager.get_project(project_id), None
        except Exception as exc:
            return None, f"project lookup failed: {exc}"

    def _project_path(self, project_id: str) -> str | None:
        if not self.project_manager:
            return None
        try:
            project = self.project_manager.get_project(project_id)
        except Exception:
            return None
        return getattr(project, "path", None)

    def _remember_agent_task(self, project_id: str, agent_id: str, request: str) -> str | None:
        if not self.project_manager:
            return "project manager is not configured"
        try:
            project = self.project_manager.get_project(project_id)
            project.add_agent(agent_id)
            existing = str(project.config.setdefault("agent_tasks", {}).get(agent_id, ""))
            if request not in existing:
                project.config["agent_tasks"][agent_id] = f"{existing}\n{request}".strip()
            project.touch()
            self.project_manager.save(project)
        except Exception as exc:
            return f"agent task persistence failed: {exc}"
        return None

    def _remember_agent_attempt(self, project_id: str, agent_id: str, request: str) -> str | None:
        if not self.project_manager:
            return "project manager is not configured"
        try:
            project = self.project_manager.get_project(project_id)
            attempts = project.config.setdefault("agent_task_attempts", {})
            agent_attempts = attempts.setdefault(agent_id, [])
            if request not in agent_attempts:
                agent_attempts.append(request)
            project.touch()
            self.project_manager.save(project)
        except Exception as exc:
            return f"agent task attempt persistence failed: {exc}"
        return None

    def _agent_runtime_state(self, agent_id: str | None) -> str | None:
        if not agent_id or not self.agent_manager:
            return None
        try:
            agent = self.agent_manager.inspect(agent_id)
        except Exception:
            return None
        state = getattr(agent, "state", None)
        return getattr(state, "value", state)

    def _touch_project(self, project_id: str) -> None:
        if not self.project_manager:
            return
        try:
            project = self.project_manager.get_project(project_id)
        except Exception:
            return
        project.touch()
        self.project_manager.save(project)


def _str_or_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _state_value(state: object) -> str | None:
    return str(getattr(state, "value", state)) if state is not None else None
