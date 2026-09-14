from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Resolution:
    project_id: str | None
    confidence: float
    ask_user: bool
    reason: str
    def to_dict(self) -> dict[str, object]: return asdict(self)


class CrossSystemContextResolver:
    def resolve(self, event: dict[str, object], projects: list[dict[str, object]]) -> Resolution:
        text = " ".join(str(value).lower() for value in event.values())
        for project in projects:
            project_id = str(project.get("id", ""))
            name = str(project.get("name", project_id)).lower()
            if project_id.lower() in text or name in text:
                return Resolution(project_id, 0.9, False, "event text mentions project")
        return Resolution(None, 0.0, True, "no confident project match")
