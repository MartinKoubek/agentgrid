from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class OrchestratorDecision:
    action: str
    reason: str
    project_id: str | None = None
    agent_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
