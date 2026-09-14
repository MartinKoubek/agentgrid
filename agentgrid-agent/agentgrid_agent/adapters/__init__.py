from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.adapters.fake import FakeAgentAdapter


def default_adapters(tmux) -> dict[str, AgentAdapter]:
    return {"fake": FakeAgentAdapter(tmux)}


__all__ = ["AgentAdapter", "FakeAgentAdapter", "default_adapters"]
