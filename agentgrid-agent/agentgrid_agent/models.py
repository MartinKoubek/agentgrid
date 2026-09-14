from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from time import time


class AgentState(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AgentConfig:
    adapter: str
    command: str | None = None
    pane_id: str | None = None
    session: str = "agentgrid-agents"
    window: str | None = None
    cwd: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class Agent:
    id: str
    adapter: str
    pane_id: str
    pid: int | None
    state: AgentState
    command: str | None = None
    endpoint_id: str | None = None
    session: str | None = None
    window: str | None = None
    cwd: str | None = None
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    error: str | None = None

    def mark(self, state: AgentState, error: str | None = None) -> None:
        self.state = state
        self.error = error
        self.updated_at = time()

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Agent:
        values = dict(data)
        values["state"] = AgentState(str(values["state"]))
        return cls(**values)
