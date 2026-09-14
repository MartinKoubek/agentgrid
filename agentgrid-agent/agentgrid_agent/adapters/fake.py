from __future__ import annotations

from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.models import Agent, AgentConfig


class FakeAgentAdapter(AgentAdapter):
    name = "fake"

    def __init__(self, tmux) -> None:
        self.tmux = tmux

    def default_command(self) -> str:
        return (
            "python3.11 -u -c \""
            "import sys, time; "
            "print('FAKE_AGENT_READY', flush=True); "
            "\nfor line in sys.stdin:"
            "\n    text=line.rstrip('\\n')"
            "\n    if text == 'exit':"
            "\n        print('BYE', flush=True); time.sleep(0.5); break"
            "\n    print('ACK: ' + text, flush=True)"
            "\""
        )

    def start(self, pane, config: AgentConfig) -> None:
        return None

    def send(self, agent: Agent, text: str) -> None:
        self.tmux.write(agent.pane_id, text)

    def read(self, agent: Agent) -> str:
        return self.tmux.read(agent.pane_id)

    def is_alive(self, agent: Agent) -> bool:
        result = self.tmux.handshake(agent.pane_id, active=True, expected_endpoint_id=agent.endpoint_id)
        runtime_matches = agent.runtime_pid is not None and result.runtime_pid == agent.runtime_pid
        return result.pane_alive is True and result.agent_alive is True and result.matched_endpoint_id is True and runtime_matches

    def stop(self, agent: Agent) -> None:
        if self.is_alive(agent):
            self.send(agent, "exit")
