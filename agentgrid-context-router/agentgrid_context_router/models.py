from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class RouteType(StrEnum):
    CONTINUE_AGENT = "CONTINUE_AGENT"
    START_AGENT = "START_AGENT"
    SELECT_PROJECT = "SELECT_PROJECT"
    CREATE_PROJECT = "CREATE_PROJECT"


@dataclass(frozen=True)
class RouteDecision:
    route: RouteType
    project_id: str | None = None
    agent_id: str | None = None
    confidence: float = 0.5
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self); data["route"] = self.route.value; return data
