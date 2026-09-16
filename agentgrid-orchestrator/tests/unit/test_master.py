import json
import subprocess

from agentgrid_orchestrator.master import (
    CodexMasterProvider,
    FakeMasterProvider,
    MasterDecision,
    MasterProviderError,
    MasterRequestStore,
    MasterWorkflow,
    parse_master_decision,
)


class FakeProject:
    def __init__(self, project_id="project-a", agents=None) -> None:
        self.id = project_id
        self.path = f"/tmp/{project_id}"
        self.agents = list(agents or [])
        self.config = {"agent_tasks": {"ag-001": "work on scheduler"}}

    def to_dict(self):
        return {"id": self.id, "path": self.path, "agents": self.agents, "config": self.config}


class FakeProjectManager:
    def __init__(self, projects=None) -> None:
        self.projects = {project.id: project for project in projects or [FakeProject()]}

    def list_projects(self, include_closed=False):
        return list(self.projects.values())

    def get_project(self, project_id):
        try:
            return self.projects[project_id]
        except KeyError as exc:
            raise KeyError(project_id) from exc


class FakeProjectContext:
    def get_context(self, project_id, query=None, level="summary"):
        project = {"id": project_id, "path": f"/tmp/{project_id}"}
        agents = [{"id": "ag-001", "state": "RUNNING", "task": "work on scheduler"}]
        return type("Context", (), {"to_dict": lambda self: {"project": project, "agents": agents}})()


class FakeAgentManager:
    def __init__(self, state="RUNNING") -> None:
        self.state = state

    def inspect(self, agent_id):
        return type("Agent", (), {"id": agent_id, "state": self.state})()


class RecordingOrchestrator:
    def __init__(self, action="START_AGENT") -> None:
        self.routes = []
        self.action = action

    def execute_route(self, request, route, target_project_id=None):
        self.routes.append((request, route, target_project_id))
        return type(
            "Decision",
            (),
            {
                "action": self.action,
                "reason": "executed",
                "project_id": route.project_id,
                "agent_id": route.agent_id or "ag-001",
                "details": {"request": request},
                "to_dict": lambda self: {
                    "action": self.action,
                    "reason": self.reason,
                    "project_id": self.project_id,
                    "agent_id": self.agent_id,
                    "details": self.details,
                },
            },
        )()


def workflow(tmp_path, provider, project_manager=None, agent_manager=None, orchestrator=None):
    return MasterWorkflow(
        provider=provider,
        orchestrator=orchestrator or RecordingOrchestrator(),
        project_manager=project_manager or FakeProjectManager(),
        project_context=FakeProjectContext(),
        agent_manager=agent_manager or FakeAgentManager(),
        request_store=MasterRequestStore(tmp_path / "master.sqlite3"),
    )


def test_parse_master_decision_accepts_json_contract() -> None:
    decision = parse_master_decision('{"version":1,"action":"START_AGENT","project_id":"project-a","reason":"new work"}')

    assert decision.action == "START_AGENT"
    assert decision.project_id == "project-a"


def test_parse_master_decision_rejects_malformed_json() -> None:
    try:
        parse_master_decision("not json")
    except MasterProviderError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("expected parse failure")


def test_master_starts_validated_project_worker(tmp_path) -> None:
    orchestrator = RecordingOrchestrator()
    master = workflow(
        tmp_path,
        FakeMasterProvider([{"version": 1, "action": "START_AGENT", "project_id": "project-a", "reason": "new worker"}]),
        orchestrator=orchestrator,
    )

    result = master.handle_request("work on scheduler", "project-a", request_id="mr-1")

    assert result.action == "START_AGENT"
    assert len(orchestrator.routes) == 1
    assert master.request_store.get("mr-1").status == "EXECUTED"


def test_master_parks_continue_without_explicit_confirmation(tmp_path) -> None:
    master = workflow(
        tmp_path,
        FakeMasterProvider(
            [{"version": 1, "action": "CONTINUE_AGENT", "project_id": "project-a", "agent_id": "ag-001", "reason": "related"}]
        ),
        project_manager=FakeProjectManager([FakeProject(agents=["ag-001"])]),
    )

    result = master.handle_request("add scheduler test", "project-a", request_id="mr-2")

    assert result.action == "PARK"
    assert result.agent_id == "ag-001"
    assert master.request_store.get("mr-2").status == "PARKED"


def test_master_continues_when_human_confirmed(tmp_path) -> None:
    orchestrator = RecordingOrchestrator("CONTINUE_AGENT")
    master = workflow(
        tmp_path,
        FakeMasterProvider(
            [{"version": 1, "action": "CONTINUE_AGENT", "project_id": "project-a", "agent_id": "ag-001", "reason": "related"}]
        ),
        project_manager=FakeProjectManager([FakeProject(agents=["ag-001"])]),
        orchestrator=orchestrator,
    )

    result = master.handle_request("add scheduler test", "project-a", request_id="mr-3", allow_continue=True)

    assert result.action == "CONTINUE_AGENT"
    assert orchestrator.routes[0][1].agent_id == "ag-001"


def test_master_rejects_hallucinated_agent_id_without_side_effects(tmp_path) -> None:
    orchestrator = RecordingOrchestrator()
    master = workflow(
        tmp_path,
        FakeMasterProvider(
            [{"version": 1, "action": "CONTINUE_AGENT", "project_id": "project-a", "agent_id": "ag-999", "reason": "related"}]
        ),
        project_manager=FakeProjectManager([FakeProject(agents=["ag-001"])]),
        orchestrator=orchestrator,
    )

    result = master.handle_request("add scheduler test", "project-a", request_id="mr-4", allow_continue=True)

    assert result.action == "MASTER_DECISION_REJECTED"
    assert orchestrator.routes == []


def test_master_parks_stopped_agent(tmp_path) -> None:
    master = workflow(
        tmp_path,
        FakeMasterProvider(
            [{"version": 1, "action": "CONTINUE_AGENT", "project_id": "project-a", "agent_id": "ag-001", "reason": "related"}]
        ),
        project_manager=FakeProjectManager([FakeProject(agents=["ag-001"])]),
        agent_manager=FakeAgentManager(state="STOPPED"),
    )

    result = master.handle_request("add scheduler test", "project-a", request_id="mr-5", allow_continue=True)

    assert result.action == "PARK"
    assert result.details["runtime_state"] == "STOPPED"


def test_master_duplicate_request_id_does_not_dispatch_twice(tmp_path) -> None:
    orchestrator = RecordingOrchestrator()
    master = workflow(
        tmp_path,
        FakeMasterProvider([
            {"version": 1, "action": "START_AGENT", "project_id": "project-a", "reason": "new worker"},
            {"version": 1, "action": "START_AGENT", "project_id": "project-a", "reason": "duplicate"},
        ]),
        orchestrator=orchestrator,
    )

    first = master.handle_request("work on scheduler", "project-a", request_id="same")
    duplicate = master.handle_request("work on scheduler", "project-a", request_id="same")

    assert first.action == "START_AGENT"
    assert duplicate.action == "DUPLICATE_REQUEST"
    assert len(orchestrator.routes) == 1


def test_master_provider_failure_is_persisted(tmp_path) -> None:
    class BrokenProvider:
        def plan(self, request, snapshot):
            raise TimeoutError("timeout")

    master = workflow(tmp_path, BrokenProvider())

    result = master.handle_request("work on scheduler", "project-a", request_id="mr-fail")

    assert result.action == "MASTER_FAILED"
    assert master.request_store.get("mr-fail").status == "FAILED"


def test_codex_master_provider_builds_documented_exec_command(monkeypatch, tmp_path) -> None:
    calls = []

    monkeypatch.setattr("shutil.which", lambda executable: f"/bin/{executable}")

    def fake_run(command, input, capture_output, text, check, timeout, cwd):
        calls.append({"command": command, "input": input, "timeout": timeout, "cwd": cwd})
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump({"version": 1, "action": "ASK_USER", "reason": "ambiguous"}, output_file)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("subprocess.run", fake_run)

    decision = CodexMasterProvider(timeout=7.0, cwd=tmp_path).plan("work", {"projects": []})

    assert decision.action == "ASK_USER"
    assert calls[0]["command"][:3] == ["/bin/codex", "exec", "--sandbox"]
    assert calls[0]["timeout"] == 7.0
    assert calls[0]["cwd"] == str(tmp_path)
