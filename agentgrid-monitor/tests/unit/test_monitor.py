from __future__ import annotations

from agentgrid_agent.models import Agent, AgentState
from agentgrid_monitor.models import EventType
from agentgrid_monitor.monitor import Monitor


class InMemoryStateStore:
    def __init__(self) -> None:
        self.snapshots = {}

    def get_snapshot(self, agent_id: str):
        return self.snapshots.get(agent_id)

    def save_snapshot(self, snapshot) -> None:
        self.snapshots[snapshot.agent_id] = snapshot

    def reset(self) -> None:
        self.snapshots.clear()


class FakeAgentManager:
    def __init__(self, agent: Agent, output: str) -> None:
        self.agent = agent
        self.output = output

    def list(self) -> list[Agent]:
        return [self.agent]

    def read(self, agent_id: str) -> str:
        return self.output


def make_agent(state: AgentState = AgentState.RUNNING) -> Agent:
    return Agent(
        id="ag-001",
        adapter="fake",
        pane_id="%1",
        pid=123,
        state=state,
        runtime_pid=456,
        endpoint_id="endpoint-1",
    )


def test_first_running_agent_emits_started() -> None:
    monitor = Monitor(FakeAgentManager(make_agent(), "ready"), state_store=InMemoryStateStore())

    events = monitor.scan()

    assert [event.type for event in events] == [EventType.AGENT_STARTED]
    assert events[0].agent_id == "ag-001"


def test_output_change_emits_output_changed() -> None:
    state_store = InMemoryStateStore()
    manager = FakeAgentManager(make_agent(), "ready")
    monitor = Monitor(manager, state_store=state_store)

    assert [event.type for event in monitor.scan()] == [EventType.AGENT_STARTED]
    manager.output = "ready\nnew output"

    assert [event.type for event in monitor.scan()] == [EventType.AGENT_OUTPUT_CHANGED]


def test_running_to_stopped_emits_exit_events() -> None:
    state_store = InMemoryStateStore()
    agent = make_agent()
    manager = FakeAgentManager(agent, "ready")
    monitor = Monitor(manager, state_store=state_store)
    monitor.scan()

    agent.mark(AgentState.STOPPED)
    events = monitor.scan()

    assert [event.type for event in events] == [EventType.AGENT_EXITED, EventType.PROCESS_EXITED]


def test_failed_agent_emits_failed_event() -> None:
    state_store = InMemoryStateStore()
    agent = make_agent()
    manager = FakeAgentManager(agent, "ready")
    monitor = Monitor(manager, state_store=state_store)
    monitor.scan()

    agent.mark(AgentState.FAILED, "boom")
    events = monitor.scan()

    assert [event.type for event in events] == [EventType.AGENT_FAILED]
    assert events[0].details == {"error": "boom"}
