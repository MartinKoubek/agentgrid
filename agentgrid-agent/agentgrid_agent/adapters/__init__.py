from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.adapters.codex import CodexAgentAdapter, CodexStartupError
from agentgrid_agent.adapters.fake import FakeAgentAdapter


def default_adapters(tmux) -> dict[str, AgentAdapter]:
    return {"fake": FakeAgentAdapter(tmux), "codex": CodexAgentAdapter(tmux)}


__all__ = ["AgentAdapter", "CodexAgentAdapter", "CodexStartupError", "FakeAgentAdapter", "default_adapters"]
