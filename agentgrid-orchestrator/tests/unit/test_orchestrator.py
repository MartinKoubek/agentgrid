from agentgrid_orchestrator import Orchestrator
from agentgrid_orchestrator.runtime import enqueue_monitor_events, map_orchestrator_decision, orchestrator_event_handler
from agentgrid_dispatcher import DispatchDecision
from agentgrid_event_queue import EventQueue, EventStatus
from agentgrid_monitor import Event, EventType


class FakeRoute:
    route = "START_AGENT"
    reason = "known project"
    project_id = "demo"
    agent_id = None


class FakeRouter:
    def route(self, request, context):
        return FakeRoute()


class ContinueRoute:
    route = "CONTINUE_AGENT"
    reason = "related request"
    project_id = "demo"
    agent_id = "ag-001"


class ContinueRouter:
    def route(self, request, context):
        return ContinueRoute()


class FakePolicy:
    def decide(self, action, details=None):
        return "ALLOW"


class FakeProject:
    def __init__(self) -> None:
        self.touched = False
        self.path = "/tmp/demo-project"
        self.agents = []
        self.config = {}

    def touch(self) -> None:
        self.touched = True

    def add_agent(self, agent_id):
        self.agents.append(agent_id)


class FakeProjectManager:
    def __init__(self) -> None:
        self.project = FakeProject()
        self.saved = []

    def get_project(self, project_id):
        return self.project

    def save(self, project):
        self.saved.append(project)


class RecordingAgentManager:
    def __init__(
        self,
        agent=None,
        send_error: Exception | None = None,
        stop_error: Exception | None = None,
        alive: bool = False,
    ) -> None:
        self.started = []
        self.sent = []
        self.stopped = []
        self.agent = agent or type("Agent", (), {"id": "ag-001"})()
        self.send_error = send_error
        self.stop_error = stop_error
        self.alive = alive

    def start(self, **kwargs):
        self.started.append(kwargs)
        return self.agent

    def send(self, agent_id, text):
        if self.send_error:
            raise self.send_error
        self.sent.append((agent_id, text))

    def stop(self, agent_id):
        self.stopped.append(agent_id)
        if self.stop_error:
            raise self.stop_error
        return type("Agent", (), {"id": agent_id, "state": "STOPPED"})()

    def is_alive(self, agent_id):
        return self.alive


def test_orchestrator_delegates_routing_and_policy() -> None:
    decision = Orchestrator(router=FakeRouter(), policy_engine=FakePolicy()).handle_request("fix bug", "demo")
    assert decision.action == "START_AGENT"
    assert decision.project_id == "demo"


def test_orchestrator_starts_agent_with_project_cwd() -> None:
    agent_manager = RecordingAgentManager()
    project_manager = FakeProjectManager()

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=project_manager,
        agent_adapter="codex",
    ).handle_request("fix bug", "demo")

    assert decision.action == "START_AGENT"
    assert agent_manager.started == [
        {"adapter": "codex", "session": "agentgrid-agents", "cwd": "/tmp/demo-project"}
    ]
    assert agent_manager.sent == [("ag-001", "fix bug")]
    assert project_manager.project.agents == ["ag-001"]
    assert project_manager.project.config["agent_tasks"] == {"ag-001": "fix bug"}


def test_orchestrator_keeps_failed_start_project_owned_and_does_not_send() -> None:
    failed_agent = type("Agent", (), {"id": "ag-001", "state": "FAILED", "error": "startup boom"})()
    agent_manager = RecordingAgentManager(agent=failed_agent)
    project_manager = FakeProjectManager()

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=project_manager,
    ).handle_request("fix bug", "demo")

    assert decision.action == "AGENT_START_FAILED"
    assert decision.project_id == "demo"
    assert decision.agent_id == "ag-001"
    assert decision.details["error"] == "startup boom"
    assert agent_manager.sent == []
    assert project_manager.project.agents == ["ag-001"]
    assert project_manager.project.config["agent_tasks"] == {"ag-001": "fix bug"}


def test_orchestrator_retains_agent_ownership_when_initial_send_fails() -> None:
    agent_manager = RecordingAgentManager(send_error=RuntimeError("send boom"))
    project_manager = FakeProjectManager()

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=project_manager,
    ).handle_request("fix bug", "demo")

    assert decision.action == "AGENT_SEND_FAILED"
    assert decision.agent_id == "ag-001"
    assert decision.details["error"] == "send boom"
    assert decision.details["delivery_uncertain"] is True
    assert project_manager.project.agents == ["ag-001"]
    assert project_manager.project.config["agent_tasks"] == {"ag-001": "fix bug"}


def test_orchestrator_missing_project_preflight_does_not_start_worker() -> None:
    class MissingProjectManager(FakeProjectManager):
        def get_project(self, project_id):
            raise KeyError(project_id)

    agent_manager = RecordingAgentManager()
    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=MissingProjectManager(),
    ).handle_request("fix bug", "missing")

    assert decision.action == "AGENT_START_FAILED"
    assert decision.project_id == "demo"
    assert "project lookup failed" in decision.details["error"]
    assert agent_manager.started == []
    assert agent_manager.sent == []


def test_orchestrator_project_save_failure_after_allocation_cleans_unassociated_worker() -> None:
    class SaveFailingProjectManager(FakeProjectManager):
        def save(self, project):
            raise RuntimeError("save boom")

    agent_manager = RecordingAgentManager()

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=SaveFailingProjectManager(),
    ).handle_request("fix bug", "demo")

    assert decision.action == "AGENT_START_FAILED"
    assert decision.agent_id == "ag-001"
    assert "save boom" in decision.details["project_association_error"]
    assert agent_manager.sent == []
    assert agent_manager.stopped == ["ag-001"]
    assert decision.details["cleanup"] == {"attempted": True, "state": "STOPPED", "alive": False}


def test_orchestrator_reports_orphan_risk_when_association_cleanup_leaves_worker_alive() -> None:
    class SaveFailingProjectManager(FakeProjectManager):
        def save(self, project):
            raise RuntimeError("save boom")

    agent_manager = RecordingAgentManager(alive=True)

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=SaveFailingProjectManager(),
    ).handle_request("fix bug", "demo")

    assert decision.action == "AGENT_START_FAILED"
    assert decision.details["cleanup"]["alive"] is True
    assert decision.details["cleanup"]["orphan_risk"] is True
    assert agent_manager.sent == []


def test_orchestrator_reports_cleanup_exception_after_association_failure() -> None:
    class SaveFailingProjectManager(FakeProjectManager):
        def save(self, project):
            raise RuntimeError("save boom")

    agent_manager = RecordingAgentManager(stop_error=RuntimeError("stop boom"))

    decision = Orchestrator(
        router=FakeRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=SaveFailingProjectManager(),
    ).handle_request("fix bug", "demo")

    assert decision.action == "AGENT_START_FAILED"
    assert decision.details["cleanup"]["stop_error"] == "stop boom"
    assert decision.details["cleanup"]["alive"] is False


def test_orchestrator_continues_agent_and_records_task() -> None:
    agent_manager = RecordingAgentManager()
    project_manager = FakeProjectManager()
    project_manager.project.add_agent("ag-001")
    project_manager.project.config["agent_tasks"] = {"ag-001": "fix scheduler"}

    decision = Orchestrator(
        router=ContinueRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=project_manager,
    ).handle_request("add scheduler test", "demo")

    assert decision.action == "CONTINUE_AGENT"
    assert decision.agent_id == "ag-001"
    assert agent_manager.sent == [("ag-001", "add scheduler test")]
    assert project_manager.project.config["agent_task_attempts"] == {"ag-001": ["add scheduler test"]}
    assert project_manager.project.config["agent_tasks"] == {"ag-001": "fix scheduler\nadd scheduler test"}


def test_orchestrator_parks_continue_send_failure_with_attempt_recorded() -> None:
    agent_manager = RecordingAgentManager(send_error=RuntimeError("send boom"))
    project_manager = FakeProjectManager()
    project_manager.project.add_agent("ag-001")
    project_manager.project.config["agent_tasks"] = {"ag-001": "fix scheduler"}

    decision = Orchestrator(
        router=ContinueRouter(),
        policy_engine=FakePolicy(),
        agent_manager=agent_manager,
        project_manager=project_manager,
    ).handle_request("add scheduler test", "demo")

    assert decision.action == "AGENT_SEND_FAILED"
    assert decision.agent_id == "ag-001"
    assert decision.details["error"] == "send boom"
    assert decision.details["delivery_uncertain"] is True
    assert project_manager.project.config["agent_task_attempts"] == {"ag-001": ["add scheduler test"]}
    assert project_manager.project.config["agent_tasks"] == {"ag-001": "fix scheduler"}


def test_orchestrator_accepts_event() -> None:
    decision = Orchestrator().handle_event({"type": "AGENT_EXITED", "agent_id": "ag-001"})
    assert decision.action == "AGENT_EXITED"
    assert decision.agent_id == "ag-001"


def test_orchestrator_acknowledges_core_runtime_events() -> None:
    orchestrator = Orchestrator()

    assert orchestrator.handle_event({"type": "AGENT_STARTED", "agent_id": "ag-001"}).action == "AGENT_STARTED"
    assert orchestrator.handle_event({"type": "AGENT_OUTPUT_CHANGED", "agent_id": "ag-001"}).action == "AGENT_OUTPUT_CHANGED"
    assert orchestrator.handle_event({"type": "PROCESS_EXITED", "agent_id": "ag-001"}).action == "PROCESS_EXITED"


def test_orchestrator_returns_failure_decision() -> None:
    decision = Orchestrator().handle_event({"type": "AGENT_FAILED", "agent_id": "ag-001", "error": "boom"})

    assert decision.action == "AGENT_FAILED"
    assert decision.details["error"] == "boom"


def test_orchestrator_reads_nested_failure_error() -> None:
    decision = Orchestrator().handle_event({"type": "AGENT_FAILED", "agent_id": "ag-001", "details": {"error": "boom"}})

    assert decision.action == "AGENT_FAILED"
    assert decision.details["error"] == "boom"


def test_orchestrator_waiting_input_asks_user() -> None:
    decision = Orchestrator().handle_event({"type": "AGENT_WAITING_INPUT", "agent_id": "ag-001"})

    assert decision.action == "ASK_USER"


def test_orchestrator_unknown_event_is_received() -> None:
    decision = Orchestrator().handle_event({"type": "SOMETHING_ELSE", "agent_id": "ag-001"})

    assert decision.action == "EVENT_RECEIVED"


def test_orchestrator_event_updates_project_activity() -> None:
    project_manager = FakeProjectManager()

    decision = Orchestrator(project_manager=project_manager).handle_event(
        {"type": "AGENT_STARTED", "project_id": "demo", "agent_id": "ag-001"}
    )

    assert decision.action == "AGENT_STARTED"
    assert project_manager.project.touched is True
    assert project_manager.saved == [project_manager.project]


def test_monitor_events_enqueue_with_dedupe(tmp_path) -> None:
    queue = EventQueue(tmp_path / "events.sqlite3")
    event = Event(EventType.AGENT_EXITED, agent_id="ag-001", pane_id="%1", runtime_pid=123, priority=80)

    first = enqueue_monitor_events([event], queue, lambda agent_id: "demo")
    second = enqueue_monitor_events([event], queue, lambda agent_id: "demo")

    assert first[0].id == second[0].id
    assert len(queue.list()) == 1
    assert queue.get(first[0].id).payload["project_id"] == "demo"


def test_orchestrator_event_handler_maps_decisions(tmp_path) -> None:
    class WaitingOrchestrator:
        def handle_event(self, event):
            return type("Decision", (), {"action": "ASK_USER"})()

    queue = EventQueue(tmp_path / "events.sqlite3")
    event = queue.enqueue("WAITING_USER")

    assert orchestrator_event_handler(WaitingOrchestrator())(event) == DispatchDecision.PARK


def test_orchestrator_decision_mapping_is_explicit() -> None:
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_STARTED"})()) == DispatchDecision.ACK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_FAILED"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_START_FAILED"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_SEND_FAILED"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_OUTPUT_CHANGED"})()) == DispatchDecision.ACK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_EXITED"})()) == DispatchDecision.ACK
    assert map_orchestrator_decision(type("Decision", (), {"action": "ASK_USER"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "WAITING_USER"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "AGENT_WAITING_INPUT"})()) == DispatchDecision.PARK
    assert map_orchestrator_decision(type("Decision", (), {"action": "TEMPORARY_FAILURE"})()) == DispatchDecision.REQUEUE
    assert map_orchestrator_decision(type("Decision", (), {"action": "RETRY"})()) == DispatchDecision.REQUEUE
    assert map_orchestrator_decision(type("Decision", (), {"action": "REQUEUE"})()) == DispatchDecision.REQUEUE
