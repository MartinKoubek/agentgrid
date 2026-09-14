from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from time import time


class EventType(StrEnum):
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_OUTPUT_CHANGED = "AGENT_OUTPUT_CHANGED"
    AGENT_EXITED = "AGENT_EXITED"
    AGENT_FAILED = "AGENT_FAILED"
    PROCESS_EXITED = "PROCESS_EXITED"


@dataclass(frozen=True)
class Event:
    type: EventType
    agent_id: str | None = None
    pane_id: str | None = None
    runtime_pid: int | None = None
    priority: int = 50
    timestamp: float = field(default_factory=time)
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True)
class AgentSnapshot:
    agent_id: str
    pane_id: str
    state: str
    runtime_pid: int | None
    output_digest: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AgentSnapshot:
        return cls(
            agent_id=str(data["agent_id"]),
            pane_id=str(data["pane_id"]),
            state=str(data["state"]),
            runtime_pid=int(data["runtime_pid"]) if data.get("runtime_pid") is not None else None,
            output_digest=str(data["output_digest"]),
        )
