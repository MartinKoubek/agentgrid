from __future__ import annotations

from abc import ABC, abstractmethod

from agentgrid_agent.models import Agent, AgentConfig


class AgentAdapter(ABC):
    name: str

    @abstractmethod
    def default_command(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def start(self, pane, config: AgentConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def send(self, agent: Agent, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self, agent: Agent) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_alive(self, agent: Agent) -> bool:
        raise NotImplementedError

    @abstractmethod
    def stop(self, agent: Agent) -> None:
        raise NotImplementedError
