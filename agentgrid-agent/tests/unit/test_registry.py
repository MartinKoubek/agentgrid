from agentgrid_agent.models import Agent, AgentState
from agentgrid_agent.registry import FileAgentRegistry


def test_registry_allocates_stable_incrementing_ids(tmp_path) -> None:
    registry = FileAgentRegistry(tmp_path / "agents.json")

    assert registry.next_id() == "ag-001"

    registry.save(Agent(id="ag-001", adapter="fake", pane_id="%1", pid=123, state=AgentState.RUNNING))

    assert registry.next_id() == "ag-002"


def test_registry_round_trips_agent_state(tmp_path) -> None:
    registry = FileAgentRegistry(tmp_path / "agents.json")
    agent = Agent(id="ag-001", adapter="fake", pane_id="%1", pid=123, state=AgentState.RUNNING)

    registry.save(agent)
    loaded = registry.get("ag-001")

    assert loaded.id == "ag-001"
    assert loaded.adapter == "fake"
    assert loaded.pane_id == "%1"
    assert loaded.state == AgentState.RUNNING
