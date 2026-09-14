from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExecutionResult:
    command: list[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        data = asdict(self); data["succeeded"] = self.succeeded; return data
