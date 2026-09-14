from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from time import time


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    project_id: str
    category: str
    content: str
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: float = field(default_factory=time)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> MemoryEntry:
        return cls(**json.loads(data))
