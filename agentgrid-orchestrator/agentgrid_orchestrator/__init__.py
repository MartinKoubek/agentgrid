from agentgrid_orchestrator.models import OrchestratorDecision
from agentgrid_orchestrator.orchestrator import Orchestrator

__all__ = ["AgentGridRuntime", "Orchestrator", "OrchestratorDecision"]


def __getattr__(name: str):
    if name == "AgentGridRuntime":
        from agentgrid_orchestrator.runtime import AgentGridRuntime

        return AgentGridRuntime
    raise AttributeError(name)
