from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from time import time


@dataclass(frozen=True)
class ProjectContext:
    project_id: str
    level: str = "summary"
    query: str | None = None
    project: dict[str, object] | None = None
    agents: list[dict[str, object]] = field(default_factory=list)
    memory: list[dict[str, object]] = field(default_factory=list)
    shell_logs: list[dict[str, object]] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    git: dict[str, object] = field(default_factory=dict)
    tests: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)
