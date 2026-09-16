from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentgrid_agent import AgentManager, FileAgentRegistry
from agentgrid_agent.adapters import default_adapters
from agentgrid_context_router import ContextRouter
from agentgrid_dispatcher import DispatchDecision, Dispatcher
from agentgrid_event_queue import EventQueue, EventRecord
from agentgrid_monitor import Event, Monitor
from agentgrid_orchestrator.orchestrator import Orchestrator
from agentgrid_policy import PolicyEngine
from agentgrid_project_context import ProjectContextBuilder
from agentgrid_project_manager import ProjectManager
from agentgrid_project_memory import ProjectMemory
from tmuxio import TmuxClient


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    agents: Path
    events: Path
    monitor: Path
    projects: Path
    memory: Path

    @classmethod
    def under(cls, root: str | Path) -> RuntimePaths:
        base = Path(root)
        return cls(
            root=base,
            agents=base / "agents.sqlite3",
            events=base / "events.sqlite3",
            monitor=base / "monitor.sqlite3",
            projects=base / "projects.sqlite3",
            memory=base / "project-memory.sqlite3",
        )


class AgentGridRuntime:
    def __init__(
        self,
        root: str | Path,
        socket_name: str | None = None,
        tmux: TmuxClient | None = None,
        agent_adapter: str = "fake",
        agent_session: str = "agentgrid-agents",
        adapters: dict | None = None,
    ) -> None:
        self.paths = RuntimePaths.under(root)
        self.paths.root.mkdir(parents=True, exist_ok=True)

        self.tmux = tmux or TmuxClient(socket_name=socket_name)
        runtime_adapters = default_adapters(self.tmux)
        if adapters:
            runtime_adapters.update(adapters)
        self.agent_manager = AgentManager(
            tmux=self.tmux,
            registry=FileAgentRegistry(self.paths.agents),
            adapters=runtime_adapters,
        )
        self.monitor = Monitor(agent_manager=self.agent_manager, state_path=self.paths.monitor)
        self.event_queue = EventQueue(self.paths.events)
        self.dispatcher = Dispatcher(self.event_queue)
        self.project_manager = ProjectManager(self.paths.projects)
        self.project_memory = ProjectMemory(self.paths.memory)
        self.project_context = ProjectContextBuilder(
            project_manager=self.project_manager,
            agent_manager=self.agent_manager,
            project_memory=self.project_memory,
            event_queue=self.event_queue,
        )
        self.context_router = ContextRouter()
        self.policy_engine = PolicyEngine()
        self.orchestrator = Orchestrator(
            context_builder=self.project_context,
            router=self.context_router,
            policy_engine=self.policy_engine,
            agent_manager=self.agent_manager,
            project_manager=self.project_manager,
            agent_adapter=agent_adapter,
            agent_session=agent_session,
        )

    def enqueue_monitor_events(self) -> list[EventRecord]:
        return enqueue_monitor_events(self.monitor.scan(), self.event_queue, self.project_owner_for_agent)

    def dispatch_next(self):
        return self.dispatcher.dispatch_next(orchestrator_event_handler(self.orchestrator))

    def project_owner_for_agent(self, agent_id: str | None) -> str | None:
        if agent_id is None:
            return None
        for project in self.project_manager.list_projects(include_closed=True):
            if agent_id in project.agents:
                return project.id
        return None


def enqueue_monitor_events(
    events: list[Event],
    event_queue: EventQueue,
    project_owner_for_agent=None,
) -> list[EventRecord]:
    records = []
    for event in events:
        payload = event.to_dict()
        payload.pop("type", None)
        project_id = project_owner_for_agent(event.agent_id) if project_owner_for_agent else None
        if project_id is not None:
            payload["project_id"] = project_id
        records.append(
            event_queue.enqueue(
                event_type=event.type.value,
                priority=event.priority,
                payload=payload,
                agent_id=event.agent_id,
                pane_id=event.pane_id,
                dedupe_key=monitor_event_dedupe_key(event),
            )
        )
    return records


def monitor_event_dedupe_key(event: Event) -> str:
    if event.type.value == "AGENT_OUTPUT_CHANGED":
        digest = event.details.get("output_digest") or event.timestamp
        return f"{event.type.value}:{event.agent_id}:{digest}"
    if event.runtime_pid is not None:
        return f"{event.type.value}:{event.agent_id}:{event.runtime_pid}"
    return f"{event.type.value}:{event.agent_id}:{event.pane_id}"


def orchestrator_event_handler(orchestrator: Orchestrator):
    def handle(event: EventRecord) -> DispatchDecision:
        decision = orchestrator.handle_event({"id": event.id, "type": event.type, **event.payload})
        return map_orchestrator_decision(decision)

    return handle


def map_orchestrator_decision(decision) -> DispatchDecision:
    if decision.action in {"ASK_USER", "WAITING_USER", "AGENT_WAITING_INPUT", "AGENT_FAILED"}:
        return DispatchDecision.PARK
    if decision.action in {"REQUEUE", "RETRY", "TEMPORARY_FAILURE"}:
        return DispatchDecision.REQUEUE
    return DispatchDecision.ACK
