from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from time import time


class ProjectState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class Project:
    id: str
    path: str
    name: str | None = None
    repository: str | None = None
    state: ProjectState = ProjectState.OPEN
    workspace: dict[str, object] = field(default_factory=dict)
    active_agents: list[str] = field(default_factory=list)
    config: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    last_activity_at: float = field(default_factory=time)

    def touch(self) -> None:
        now = time()
        self.updated_at = now
        self.last_activity_at = now

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> Project:
        values = json.loads(data)
        values["state"] = ProjectState(values["state"])
        return cls(**values)
