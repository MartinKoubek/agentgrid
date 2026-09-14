from agentgrid_context_router import ContextRouter, RouteType


def test_router_continues_matching_running_agent() -> None:
    decision = ContextRouter().route("add scheduler test", {"project_id": "demo", "agents": [{"id": "ag-001", "state": "RUNNING", "task": "scheduler"}]})
    assert decision.route == RouteType.CONTINUE_AGENT
    assert decision.agent_id == "ag-001"


def test_router_starts_agent_for_known_project() -> None:
    decision = ContextRouter().route("fix bug", {"project_id": "demo", "project": {"id": "demo"}, "agents": []})
    assert decision.route == RouteType.START_AGENT
