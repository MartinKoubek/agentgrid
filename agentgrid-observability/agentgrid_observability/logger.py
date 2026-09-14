from __future__ import annotations

import json
from pathlib import Path
from time import time


class DiagnosticLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, project_id: str | None = None, agent_id: str | None = None, **details: object) -> dict[str, object]:
        record = {"timestamp": time(), "event": event, "project_id": project_id, "agent_id": agent_id, "details": details}
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def read(self) -> list[dict[str, object]]:
        if not self.path.exists(): return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
