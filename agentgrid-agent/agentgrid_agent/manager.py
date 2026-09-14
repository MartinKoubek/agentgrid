from __future__ import annotations

import uuid
from time import monotonic, sleep

from tmuxio import TmuxClient

from agentgrid_agent.adapters.base import AgentAdapter
from agentgrid_agent.models import Agent, AgentConfig, AgentState
from agentgrid_agent.registry import FileAgentRegistry


class AgentManager:
    def __init__(
        self,
        tmux: TmuxClient | None = None,
        registry: FileAgentRegistry | None = None,
        adapters: dict[str, AgentAdapter] | None = None,
    ) -> None:
        self.tmux = tmux or TmuxClient()
        self.registry = registry or FileAgentRegistry()
        self.adapters = dict(adapters or {})

    def register_adapter(self, name: str, adapter: AgentAdapter) -> None:
        self.adapters[name] = adapter

    def list(self) -> list[Agent]:
        agents = self.registry.list()
        for agent in agents:
            self._refresh_state(agent)
        return agents

    def start(
        self,
        adapter: str = "fake",
        command: str | None = None,
        pane_id: str | None = None,
        session: str = "agentgrid-agents",
        window: str | None = None,
        cwd: str | None = None,
    ) -> Agent:
        return self._start(
            agent_id=self.registry.allocate_id(),
            adapter=adapter,
            command=command,
            pane_id=pane_id,
            session=session,
            window=window,
            cwd=cwd,
        )

    def _start(
        self,
        agent_id: str,
        adapter: str = "fake",
        command: str | None = None,
        pane_id: str | None = None,
        session: str = "agentgrid-agents",
        window: str | None = None,
        cwd: str | None = None,
    ) -> Agent:
        config = AgentConfig(adapter=adapter, command=command, pane_id=pane_id, session=session, window=window, cwd=cwd)
        adapter_impl = self._adapter(config.adapter)
        endpoint_id = f"agentgrid-agent-{agent_id}-{uuid.uuid4().hex}"
        launch_command = config.command or adapter_impl.default_command()

        if config.pane_id:
            pane = self.tmux.start_process_in_pane(config.pane_id, launch_command, endpoint_id=endpoint_id)
        else:
            pane = self.tmux.start_process(
                launch_command,
                session=config.session,
                window=config.window or agent_id,
                cwd=config.cwd,
                endpoint_id=endpoint_id,
            )

        handshake = self.tmux.handshake(pane.pane_id, active=True, expected_endpoint_id=endpoint_id)
        agent = Agent(
            id=agent_id,
            adapter=config.adapter,
            pane_id=pane.pane_id,
            pid=pane.pid,
            state=AgentState.STARTING,
            runtime_pid=handshake.runtime_pid,
            command=launch_command,
            endpoint_id=endpoint_id,
            session=pane.session,
            window=pane.window,
            cwd=config.cwd,
        )
        try:
            adapter_impl.start(self.tmux.get_pane(pane.pane_id), config)
            agent.mark(AgentState.RUNNING)
        except Exception as exc:
            agent.mark(AgentState.FAILED, str(exc))
        self.registry.save(agent)
        return agent

    def inspect(self, agent_id: str) -> Agent:
        agent = self.registry.get(agent_id)
        self._refresh_state(agent)
        return agent

    def send(self, agent_id: str, text: str) -> Agent:
        agent = self.inspect(agent_id)
        if agent.state in {AgentState.STOPPED, AgentState.FAILED}:
            raise RuntimeError(f"agent is not running: {agent_id} ({agent.state.value})")
        self._adapter(agent.adapter).send(agent, text)
        self._refresh_state(agent)
        return agent

    def read(self, agent_id: str) -> str:
        agent = self.inspect(agent_id)
        return self._adapter(agent.adapter).read(agent)

    def is_alive(self, agent_id: str) -> bool:
        agent = self.registry.get(agent_id)
        alive = self._adapter(agent.adapter).is_alive(agent)
        if not alive and agent.state != AgentState.FAILED:
            agent.mark(AgentState.STOPPED)
            self.registry.save(agent)
        return alive

    def stop(self, agent_id: str) -> Agent:
        agent = self.registry.get(agent_id)
        self._adapter(agent.adapter).stop(agent)
        deadline = monotonic() + 3.0
        while monotonic() < deadline and self._adapter(agent.adapter).is_alive(agent):
            sleep(0.05)
        agent.mark(AgentState.RUNNING if self._adapter(agent.adapter).is_alive(agent) else AgentState.STOPPED)
        self.registry.save(agent)
        return agent

    def restart(self, agent_id: str) -> Agent:
        old_agent = self.registry.get(agent_id)
        self.stop(agent_id)
        return self._start(
            agent_id=old_agent.id,
            adapter=old_agent.adapter,
            command=old_agent.command,
            session=old_agent.session or "agentgrid-agents",
            window=old_agent.window,
            cwd=old_agent.cwd,
        )

    def _adapter(self, name: str) -> AgentAdapter:
        try:
            return self.adapters[name]
        except KeyError as exc:
            raise ValueError(f"unknown agent adapter: {name}") from exc

    def _refresh_state(self, agent: Agent) -> None:
        try:
            handshake = self.tmux.handshake(agent.pane_id, active=True, expected_endpoint_id=agent.endpoint_id)
            agent.pid = handshake.pid
            if agent.runtime_pid is None:
                agent.runtime_pid = handshake.runtime_pid
            alive = self._adapter(agent.adapter).is_alive(agent)
            if alive and agent.state != AgentState.FAILED:
                agent.mark(AgentState.RUNNING)
            elif not alive and agent.state != AgentState.FAILED:
                agent.mark(AgentState.STOPPED)
        except Exception as exc:
            agent.mark(AgentState.FAILED, str(exc))
        self.registry.save(agent)
