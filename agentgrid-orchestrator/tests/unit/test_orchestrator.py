from agentgrid_orchestrator import Orchestrator


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
