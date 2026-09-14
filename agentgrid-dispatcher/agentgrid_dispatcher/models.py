from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class DispatchDecision(StrEnum):
    ACK = "ACK"
    PARK = "PARK"
    REQUEUE = "REQUEUE"


@dataclass(frozen=True)
class DispatchResult:
    delivered: bool
    decision: DispatchDecision | None = None
    event_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if self.decision is not None:
            data["decision"] = self.decision.value
        return data
