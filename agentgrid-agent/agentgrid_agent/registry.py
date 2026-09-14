from __future__ import annotations

import json
from pathlib import Path

from agentgrid_agent.models import Agent


class FileAgentRegistry:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "agents.json"

    def list(self) -> list[Agent]:
        return list(self._load().values())

    def get(self, agent_id: str) -> Agent:
        agents = self._load()
        if agent_id not in agents:
            raise KeyError(f"agent not found: {agent_id}")
        return agents[agent_id]

    def save(self, agent: Agent) -> None:
        agents = self._load()
        agents[agent.id] = agent
        self._save(agents)

    def delete(self, agent_id: str) -> None:
        agents = self._load()
        agents.pop(agent_id, None)
        self._save(agents)

    def next_id(self) -> str:
        highest = 0
        for agent in self.list():
            if not agent.id.startswith("ag-"):
                continue
            try:
                highest = max(highest, int(agent.id[3:]))
            except ValueError:
                continue
        return f"ag-{highest + 1:03d}"

    def _load(self) -> dict[str, Agent]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as registry_file:
            raw = json.load(registry_file)
        return {agent_id: Agent.from_dict(agent_data) for agent_id, agent_data in raw.get("agents", {}).items()}

    def _save(self, agents: dict[str, Agent]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"agents": {agent_id: agent.to_dict() for agent_id, agent in agents.items()}}
        with self.path.open("w", encoding="utf-8") as registry_file:
            json.dump(payload, registry_file, indent=2, sort_keys=True)
            registry_file.write("\n")
