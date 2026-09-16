from __future__ import annotations

import shutil
from shlex import quote
from time import monotonic, sleep

from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.models import Agent, AgentConfig
from tmuxio.errors import TmuxError


class CodexStartupError(RuntimeError):
    """Raised when the Codex TUI does not become safely input-ready."""


class CodexAgentAdapter(AgentAdapter):
    name = "codex"

    def __init__(
        self,
        tmux,
        executable: str = "codex",
        approval_policy: str = "on-request",
        sandbox: str = "workspace-write",
        extra_args: list[str] | None = None,
        readiness_timeout: float = 15.0,
        readiness_settle: float = 0.75,
        input_ready_timeout: float = 10.0,
        stop_timeout: float = 3.0,
        stop_key_interval: float = 0.5,
    ) -> None:
        self.tmux = tmux
        self.executable = executable
        self.approval_policy = approval_policy
        self.sandbox = sandbox
        self.extra_args = list(extra_args or [])
        self.readiness_timeout = readiness_timeout
        self.readiness_settle = readiness_settle
        self.input_ready_timeout = input_ready_timeout
        self.stop_timeout = stop_timeout
        self.stop_key_interval = stop_key_interval

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
        self._wait_until_input_ready(pane.pane_id, timeout=self.readiness_timeout)

    def send(self, agent: Agent, text: str) -> None:
        self._wait_until_input_ready(agent.pane_id, timeout=self.input_ready_timeout)
        self.tmux.paste_text(agent.pane_id, text, bracketed=True)
        self.tmux.send_key(agent.pane_id, "ENTER")

    def read(self, agent: Agent) -> str:
        return self.tmux.read(agent.pane_id)

    def is_alive(self, agent: Agent) -> bool:
        result = self.tmux.handshake(agent.pane_id, active=True, expected_endpoint_id=agent.endpoint_id)
        runtime_matches = agent.runtime_pid is not None and result.runtime_pid == agent.runtime_pid
        return result.pane_alive is True and result.agent_alive is True and result.matched_endpoint_id is True and runtime_matches

    def stop(self, agent: Agent) -> None:
        if not self.is_alive(agent):
            return

        deadline = monotonic() + self.stop_timeout
        for key in ("C-c", "C-d"):
            if not self.is_alive(agent):
                return
            try:
                self.tmux.send_key(agent.pane_id, key)
            except TmuxError:
                if not self.is_alive(agent):
                    return
                raise
            if self._wait_until_stopped(agent, min(deadline, monotonic() + self.stop_key_interval)):
                return

    def _wait_until_input_ready(self, pane_id: str, timeout: float) -> None:
        deadline = monotonic() + timeout
        last_output: str | None = None
        last_changed = monotonic()

        while monotonic() < deadline:
            handshake = self.tmux.handshake(pane_id, active=False)
            output = self.tmux.read(pane_id)
            blocker = self._startup_blocker(output)
            if blocker:
                raise CodexStartupError(blocker)
            if handshake.agent_alive is False:
                raise CodexStartupError(f"Codex exited before it became input-ready. Last output: {self._snippet(output)}")
            if output != last_output:
                last_output = output
                last_changed = monotonic()
            elif output.strip() and monotonic() - last_changed >= self.readiness_settle:
                return
            sleep(0.05)

        raise CodexStartupError(
            f"Codex did not become input-ready within {timeout:.1f}s. Last output: {self._snippet(last_output or '')}"
        )

    def _wait_until_stopped(self, agent: Agent, deadline: float) -> bool:
        while monotonic() < deadline:
            if not self.is_alive(agent):
                return True
            sleep(0.05)
        return not self.is_alive(agent)

    def _startup_blocker(self, output: str) -> str | None:
        normalized = output.lower()
        blockers = {
            "update available": "Codex startup is blocked by the interactive update prompt. Run codex manually and choose update, skip, or skip until next version.",
            "repair codex local data now?": "Codex startup is blocked by a local data repair prompt. Run codex manually and resolve the prompt.",
            "codex couldn't start": "Codex reported a startup failure.",
            "not logged in": "Codex is not authenticated. Run codex login manually before starting a Codex agent.",
            "please log in": "Codex is not authenticated. Run codex login manually before starting a Codex agent.",
            "login required": "Codex is not authenticated. Run codex login manually before starting a Codex agent.",
        }
        for marker, message in blockers.items():
            if marker in normalized:
                return f"{message} Last output: {self._snippet(output)}"
        return None

    def _snippet(self, output: str, limit: int = 500) -> str:
        clean = " ".join(output.split())
        if len(clean) <= limit:
            return clean
        return clean[: limit - 3] + "..."
