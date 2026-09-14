from concurrent.futures import ThreadPoolExecutor

from agentgrid_agent.models import Agent, AgentState
from agentgrid_agent.registry import FileAgentRegistry


def test_registry_allocates_stable_incrementing_ids(tmp_path) -> None:
    registry = FileAgentRegistry(tmp_path / "agents.sqlite3")

    assert registry.allocate_id() == "ag-001"

    registry.save(Agent(id="ag-001", adapter="fake", pane_id="%1", pid=123, state=AgentState.RUNNING))

    assert registry.allocate_id() == "ag-002"


def test_registry_round_trips_agent_state(tmp_path) -> None:
    registry = FileAgentRegistry(tmp_path / "agents.sqlite3")
    agent = Agent(id="ag-001", adapter="fake", pane_id="%1", pid=123, state=AgentState.RUNNING, runtime_pid=456)

    registry.save(agent)
    loaded = registry.get("ag-001")

    assert loaded.id == "ag-001"
    assert loaded.adapter == "fake"
    assert loaded.pane_id == "%1"
    assert loaded.runtime_pid == 456
    assert loaded.state == AgentState.RUNNING


def test_registry_allocates_unique_ids_concurrently(tmp_path) -> None:
    registry_path = tmp_path / "agents.sqlite3"

    def allocate() -> str:
        return FileAgentRegistry(registry_path).allocate_id()

    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(lambda _: allocate(), range(25)))

    assert len(ids) == 25
    assert len(set(ids)) == 25
    assert sorted(ids) == [f"ag-{index:03d}" for index in range(1, 26)]
