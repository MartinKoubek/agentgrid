from __future__ import annotations

import json
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
    runtime_pid: int | None = None
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

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Agent:
        values = dict(data)
        values["state"] = AgentState(str(values["state"]))
        values.setdefault("runtime_pid", None)
        return cls(**values)

    @classmethod
    def from_json(cls, data: str) -> Agent:
        return cls.from_dict(json.loads(data))
