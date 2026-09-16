from __future__ import annotations

import shutil
from shlex import quote

from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.models import Agent, AgentConfig


class CodexAgentAdapter(AgentAdapter):
    name = "codex"

    def __init__(
        self,
        tmux,
        executable: str = "codex",
        approval_policy: str = "on-request",
        sandbox: str = "workspace-write",
        extra_args: list[str] | None = None,
    ) -> None:
        self.tmux = tmux
        self.executable = executable
        self.approval_policy = approval_policy
        self.sandbox = sandbox
        self.extra_args = list(extra_args or [])

    def default_command(self) -> str:
        executable = shutil.which(self.executable)
        if executable is None:
            raise FileNotFoundError(f"Codex CLI executable not found: {self.executable}")
        args = [
            executable,
            "--no-alt-screen",
            "--ask-for-approval",
            self.approval_policy,
            "--sandbox",
            self.sandbox,
            *self.extra_args,
        ]
        return " ".join(quote(arg) for arg in args)

    def start(self, pane, config: AgentConfig) -> None:
        return None

    def send(self, agent: Agent, text: str) -> None:
        self.tmux.send_text(agent.pane_id, text)
        self.tmux.send_key(agent.pane_id, "ENTER")

    def read(self, agent: Agent) -> str:
        return self.tmux.read(agent.pane_id)

    def is_alive(self, agent: Agent) -> bool:
        result = self.tmux.handshake(agent.pane_id, active=True, expected_endpoint_id=agent.endpoint_id)
        runtime_matches = agent.runtime_pid is not None and result.runtime_pid == agent.runtime_pid
        return result.pane_alive is True and result.agent_alive is True and result.matched_endpoint_id is True and runtime_matches

    def stop(self, agent: Agent) -> None:
        if self.is_alive(agent):
            self.tmux.send_key(agent.pane_id, "C-c")
            self.tmux.send_key(agent.pane_id, "C-d")
