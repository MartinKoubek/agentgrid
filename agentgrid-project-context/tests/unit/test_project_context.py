from agentgrid_project_context import ProjectContextBuilder

from agentgrid_event_queue import EventQueue
from agentgrid_shell_logger import ShellLogger


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


def test_context_builder_filters_events_by_project_before_limit(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")

    for index in range(3):
        queue.enqueue("PROJECT_A_EVENT", priority=10, project_id="project-a", payload={"index": index})
    for index in range(20):
        queue.enqueue("OTHER_EVENT", priority=90, project_id=f"project-{index}")

    context = ProjectContextBuilder(project_manager=ProjectManager(), event_queue=queue).get_context(
        "project-a",
        level="summary",
    )

    assert len(context.events) == 3
    assert {event["payload"]["project_id"] for event in context.events} == {"project-a"}


def test_context_builder_filters_shell_logs_by_project_before_limit(tmp_path) -> None:
    logger = ShellLogger(store_path=tmp_path / "shell-log.sqlite3")

    for index in range(3):
        logger.run(["python3.11", "-c", f"print('a-{index}')"], project_id="project-a")
    for index in range(8):
        logger.run(["python3.11", "-c", f"print('b-{index}')"], project_id="project-b")

    context = ProjectContextBuilder(project_manager=ProjectManager(), shell_logger=logger).get_context(
        "project-a",
        level="summary",
    )

    assert len(context.shell_logs) == 3
    assert {record["project_id"] for record in context.shell_logs} == {"project-a"}
