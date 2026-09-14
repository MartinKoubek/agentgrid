from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CommandRecord:
    id: str
    command: list[str]
    cwd: str
    stdout: str
    stderr: str
    exit_code: int
    started_at: float
    finished_at: float
    duration_seconds: float
    pane_id: str | None = None
    project_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> CommandRecord:
        values = json.loads(data)
        values.setdefault("project_id", None)
        return cls(**values)
