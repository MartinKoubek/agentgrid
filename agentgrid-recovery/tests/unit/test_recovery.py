from agentgrid_recovery import RecoveryManager


def test_recovery_empty_without_agent_manager() -> None:
    assert RecoveryManager().reconcile().to_dict() == {"running_agents": [], "stale_agents": [], "failed_agents": []}
