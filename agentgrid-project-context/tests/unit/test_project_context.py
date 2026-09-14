from agentgrid_project_context import ProjectContextBuilder


class Agent:
    def __init__(self, id, state="RUNNING"):
        self.id = id
        self.state = state

    def to_dict(self):
        return {"id": self.id, "state": self.state}


class AgentManager:
    def list(self):
        return [Agent("ag-001", "STOPPED"), Agent("ag-002")]


class Project:
    def __init__(self, id, agents):
        self.id = id
        self.agents = agents
        self.config = {"agent_tasks": {"ag-001": "scheduler", "ag-002": "database"}}
        self.workspace = {}

    def to_dict(self):
        return {
            "id": self.id,
            "agents": self.agents,
            "config": self.config,
            "workspace": self.workspace,
        }


class ProjectManager:
    def get_project(self, project_id):
        if project_id == "demo":
            return Project("demo", ["ag-001"])
        return Project(project_id, ["ag-002"])


def test_context_builder_returns_compact_context() -> None:
    context = ProjectContextBuilder().get_context("demo", query="tests")
    assert context.project_id == "demo"
    assert context.query == "tests"
    assert context.agents == []


def test_context_builder_scopes_agents_to_project() -> None:
    context = ProjectContextBuilder(project_manager=ProjectManager(), agent_manager=AgentManager()).get_context("demo")

    assert [agent["id"] for agent in context.agents] == ["ag-001"]
    assert context.agents[0]["state"] == "STOPPED"
    assert context.agents[0]["task"] == "scheduler"


def test_context_builder_does_not_leak_agents_across_projects() -> None:
    context = ProjectContextBuilder(project_manager=ProjectManager(), agent_manager=AgentManager()).get_context("other")

    assert [agent["id"] for agent in context.agents] == ["ag-002"]
    assert context.agents[0]["task"] == "database"


def test_context_builder_supports_legacy_active_agents() -> None:
    class LegacyProject(Project):
        def to_dict(self):
            return {"id": self.id, "active_agents": self.agents, "config": self.config, "workspace": self.workspace}

    class LegacyProjectManager:
        def get_project(self, project_id):
            return LegacyProject(project_id, ["ag-001"])

    context = ProjectContextBuilder(project_manager=LegacyProjectManager(), agent_manager=AgentManager()).get_context("demo")

    assert [agent["id"] for agent in context.agents] == ["ag-001"]
