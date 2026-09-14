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
        return ProjectContext(
            project_id=project_id,
            query=query,
            level=level,
            project=self._project(project_id),
            agents=self._agents(),
            memory=self._memory(project_id, query, level),
            shell_logs=self._shell_logs(level),
            events=self._events(level),
        )

    def _project(self, project_id: str) -> dict[str, object] | None:
        if not self.project_manager:
            return None
        try:
            return to_dict(self.project_manager.get_project(project_id))
        except Exception:
            return None

    def _agents(self) -> list[dict[str, object]]:
        if not self.agent_manager:
            return []
        try:
            return [to_dict(agent) for agent in self.agent_manager.list()]
        except Exception:
            return []

    def _memory(self, project_id: str, query: str | None, level: str) -> list[dict[str, object]]:
        if not self.project_memory:
            return []
        try:
            entries = self.project_memory.search(project_id, query) if query else self.project_memory.list(project_id)
            limit = 5 if level == "summary" else 20 if level == "normal" else 100
            return [to_dict(entry) for entry in entries[:limit]]
        except Exception:
            return []

    def _shell_logs(self, level: str) -> list[dict[str, object]]:
        if not self.shell_logger:
            return []
        try:
            return [to_dict(record) for record in self.shell_logger.list(limit=5 if level == "summary" else 20)]
        except Exception:
            return []

    def _events(self, level: str) -> list[dict[str, object]]:
        if not self.event_queue:
            return []
        try:
            return [to_dict(event) for event in self.event_queue.list(limit=10 if level == "summary" else 50)]
        except Exception:
            return []


def to_dict(value: object) -> dict[str, object]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return dict(value)
