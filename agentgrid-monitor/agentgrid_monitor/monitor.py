from __future__ import annotations

import hashlib

from agentgrid_agent.models import Agent, AgentState

from agentgrid_monitor.models import AgentSnapshot, Event, EventType
from agentgrid_monitor.state import MonitorStateStore


class Monitor:
    def __init__(self, agent_manager, state_path: str | None = None, state_store: MonitorStateStore | None = None) -> None:
        self.agent_manager = agent_manager
        self.state_store = state_store or MonitorStateStore(state_path)

    def scan(self) -> list[Event]:
        events: list[Event] = []
        for agent in self.agent_manager.list():
            output = self._safe_read(agent)
            snapshot = AgentSnapshot(
                agent_id=agent.id,
                pane_id=agent.pane_id,
                state=agent.state.value,
                runtime_pid=agent.runtime_pid,
                output_digest=self._digest(output),
            )
            previous = self.state_store.get_snapshot(agent.id)
            events.extend(self._events_for(agent, previous, snapshot))
            self.state_store.save_snapshot(snapshot)
        return events

    def reset(self) -> None:
        self.state_store.reset()

    def _events_for(
        self,
        agent: Agent,
        previous: AgentSnapshot | None,
        current: AgentSnapshot,
    ) -> list[Event]:
        events: list[Event] = []
        if previous is None and agent.state == AgentState.RUNNING:
            events.append(self._event(EventType.AGENT_STARTED, agent, priority=60))
            return events

        if previous is None:
            return events

        if previous.output_digest != current.output_digest:
            events.append(self._event(EventType.AGENT_OUTPUT_CHANGED, agent, priority=50))

        if previous.state == AgentState.RUNNING.value and agent.state == AgentState.STOPPED:
            events.append(self._event(EventType.AGENT_EXITED, agent, priority=80))
            events.append(self._event(EventType.PROCESS_EXITED, agent, priority=80))

        if previous.state != AgentState.FAILED.value and agent.state == AgentState.FAILED:
            events.append(self._event(EventType.AGENT_FAILED, agent, priority=90, error=agent.error))

        return events

    def _safe_read(self, agent: Agent) -> str:
        try:
            return self.agent_manager.read(agent.id)
        except Exception:
            return ""

    def _event(self, event_type: EventType, agent: Agent, priority: int, **details: object) -> Event:
        return Event(
            type=event_type,
            agent_id=agent.id,
            pane_id=agent.pane_id,
            runtime_pid=agent.runtime_pid,
            priority=priority,
            details={key: value for key, value in details.items() if value is not None},
        )

    def _digest(self, output: str) -> str:
        return hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
