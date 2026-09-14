from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from time import time


class EventStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PARKED = "PARKED"
    ACKED = "ACKED"


@dataclass
class EventRecord:
    id: str
    type: str
    priority: int = 50
    status: EventStatus = EventStatus.PENDING
    payload: dict[str, object] = field(default_factory=dict)
    dedupe_key: str | None = None
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    @property
    def agent_id(self) -> str | None:
        value = self.payload.get("agent_id")
        return str(value) if value is not None else None

    def mark(self, status: EventStatus) -> None:
        self.status = status
        self.updated_at = time()

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> EventRecord:
        values = json.loads(data)
        values["status"] = EventStatus(values["status"])
        return cls(**values)
