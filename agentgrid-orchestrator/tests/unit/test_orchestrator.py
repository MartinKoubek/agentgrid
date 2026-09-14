from agentgrid_orchestrator import Orchestrator
from agentgrid_orchestrator.runtime import enqueue_monitor_events, orchestrator_event_handler
from agentgrid_dispatcher import DispatchDecision
from agentgrid_event_queue import EventQueue, EventStatus
from agentgrid_monitor import Event, EventType


class FakeRoute:
    route = "START_AGENT"
    reason = "known project"
    project_id = "demo"
    agent_id = None


class FakeRouter:
    def route(self, request, context):
        return FakeRoute()


class FakePolicy:
    def decide(self, action, details=None):
        return "ALLOW"


def test_orchestrator_delegates_routing_and_policy() -> None:
    decision = Orchestrator(router=FakeRouter(), policy_engine=FakePolicy()).handle_request("fix bug", "demo")
    assert decision.action == "START_AGENT"
    assert decision.project_id == "demo"


def test_orchestrator_accepts_event() -> None:
    decision = Orchestrator().handle_event({"type": "AGENT_EXITED", "agent_id": "ag-001"})
    assert decision.action == "EVENT_RECEIVED"
    assert decision.agent_id == "ag-001"


def test_monitor_events_enqueue_with_dedupe(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = Event(EventType.AGENT_EXITED, agent_id="ag-001", pane_id="%1", runtime_pid=123, priority=80)

    first = enqueue_monitor_events([event], queue, lambda agent_id: "demo")
    second = enqueue_monitor_events([event], queue, lambda agent_id: "demo")

    assert first[0].id == second[0].id
    assert len(queue.list()) == 1
    assert queue.get(first[0].id).payload["project_id"] == "demo"


def test_orchestrator_event_handler_maps_decisions(tmp_path) -> None:
    class WaitingOrchestrator:
        def handle_event(self, event):
            return type("Decision", (), {"action": "ASK_USER"})()

    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("WAITING_USER")

    assert orchestrator_event_handler(WaitingOrchestrator())(event) == DispatchDecision.PARK
