from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RecoveryReport:
    running_agents: list[str] = field(default_factory=list)
    stale_agents: list[str] = field(default_factory=list)
    failed_agents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]: return asdict(self)


class RecoveryManager:
    def __init__(self, agent_manager=None) -> None:
        self.agent_manager = agent_manager

    def reconcile(self) -> RecoveryReport:
        if not self.agent_manager:
            return RecoveryReport()
        running, stale, failed = [], [], []
        for agent in self.agent_manager.list():
            if agent.state == "FAILED" or getattr(agent.state, "value", None) == "FAILED":
                failed.append(agent.id)
            elif self.agent_manager.is_alive(agent.id):
                running.append(agent.id)
            else:
                stale.append(agent.id)
        return RecoveryReport(running, stale, failed)
