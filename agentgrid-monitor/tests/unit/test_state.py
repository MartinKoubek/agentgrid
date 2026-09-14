from agentgrid_monitor.models import AgentSnapshot
from agentgrid_monitor.state import MonitorStateStore


def test_state_store_round_trips_snapshot(tmp_path) -> None:
    store = MonitorStateStore(tmp_path / "monitor.sqlite3")
    snapshot = AgentSnapshot(
        agent_id="ag-001",
        pane_id="%1",
        state="RUNNING",
        runtime_pid=456,
        output_digest="abc",
    )

    store.save_snapshot(snapshot)
    loaded = store.get_snapshot("ag-001")

    assert loaded == snapshot

    store.reset()
    assert store.get_snapshot("ag-001") is None
