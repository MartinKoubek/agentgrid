from __future__ import annotations

from dataclasses import asdict, is_dataclass

from agentgrid_project_context.models import ProjectContext


class ProjectContextBuilder:
    def __init__(self, project_manager=None, agent_manager=None, project_memory=None, shell_logger=None, event_queue=None) -> None:
        self.project_manager = project_manager
        self.agent_manager = agent_manager
        self.project_memory = project_memory
        self.shell_logger = shell_logger
        self.event_queue = event_queue

    def get_context(self, project_id: str, query: str | None = None, level: str = "summary") -> ProjectContext:
        project = self._project(project_id)
        return ProjectContext(
            project_id=project_id,
            query=query,
            level=level,
            project=project,
            agents=self._agents(project),
            memory=self._memory(project_id, query, level),
            shell_logs=self._shell_logs(project_id, project, level),
            events=self._events(project_id, project, level),
        )

    def _project(self, project_id: str) -> dict[str, object] | None:
        if not self.project_manager:
            return None
        try:
            return to_dict(self.project_manager.get_project(project_id))
        except Exception:
            return None

    def _agents(self, project: dict[str, object] | None) -> list[dict[str, object]]:
        if not self.agent_manager:
            return []
        try:
            agents = [to_dict(agent) for agent in self.agent_manager.list()]
        except Exception:
            return []

        if project is None:
            return []

        active_agents = {str(agent_id) for agent_id in project.get("active_agents") or []}
        agent_tasks = project.get("config", {}).get("agent_tasks", {}) if isinstance(project.get("config"), dict) else {}
        scoped_agents = []
        for agent in agents:
            agent_id = str(agent.get("id"))
            if agent_id not in active_agents:
                continue
            if isinstance(agent_tasks, dict) and agent_id in agent_tasks:
                agent["task"] = agent_tasks[agent_id]
            scoped_agents.append(agent)
        return scoped_agents

    def _memory(self, project_id: str, query: str | None, level: str) -> list[dict[str, object]]:
        if not self.project_memory:
            return []
        try:
            entries = self.project_memory.search(project_id, query) if query else self.project_memory.list(project_id)
            limit = 5 if level == "summary" else 20 if level == "normal" else 100
            return [to_dict(entry) for entry in entries[:limit]]
        except Exception:
            return []

    def _shell_logs(self, project_id: str, project: dict[str, object] | None, level: str) -> list[dict[str, object]]:
        if not self.shell_logger:
            return []
        try:
            records = [to_dict(record) for record in self.shell_logger.list(limit=5 if level == "summary" else 20)]
        except Exception:
            return []

        pane_ids = set()
        if project is None:
            return []
        if isinstance(project.get("workspace"), dict):
            panes = project["workspace"].get("pane_ids")
            if isinstance(panes, list):
                pane_ids = {str(pane_id) for pane_id in panes}
        return [
            record
            for record in records
            if record.get("project_id") == project_id or (pane_ids and record.get("pane_id") in pane_ids)
        ]

    def _events(self, project_id: str, project: dict[str, object] | None, level: str) -> list[dict[str, object]]:
        if not self.event_queue:
            return []
        try:
            events = [to_dict(event) for event in self.event_queue.list(limit=10 if level == "summary" else 50)]
        except Exception:
            return []

        if project is None:
            return []
        active_agents = {str(agent_id) for agent_id in project.get("active_agents") or []}
        scoped_events = []
        for event in events:
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if payload.get("project_id") == project_id:
                scoped_events.append(event)
            elif active_agents and str(payload.get("agent_id")) in active_agents:
                scoped_events.append(event)
        return scoped_events


def to_dict(value: object) -> dict[str, object]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return dict(value)
