from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import time

from agentgrid_context_router import RouteDecision, RouteType
from agentgrid_orchestrator.models import OrchestratorDecision


MASTER_INSTRUCTIONS_PATH = Path(__file__).with_name("master_instructions.md")
ALLOWED_ACTIONS = {"START_AGENT", "CONTINUE_AGENT", "ASK_USER", "PARK", "NOOP"}


class MasterProviderError(RuntimeError):
    pass


class DuplicateMasterRequest(RuntimeError):
    def __init__(self, record: MasterRequestRecord) -> None:
        super().__init__(f"duplicate master request: {record.request_id}")
        self.record = record


@dataclass(frozen=True)
class MasterDecision:
    version: int
    action: str
    project_id: str | None = None
    agent_id: str | None = None
    reason: str = ""
    confidence: float = 0.5
    uncertainty: str | None = None
    raw: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> MasterDecision:
        try:
            version = int(data.get("version", 1))
            action = str(data["action"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MasterProviderError(f"malformed master decision: {exc}") from exc
        confidence_value = data.get("confidence", 0.5)
        try:
            confidence = float(confidence_value)
        except (TypeError, ValueError):
            confidence = 0.5
        return cls(
            version=version,
            action=action,
            project_id=_optional_str(data.get("project_id")),
            agent_id=_optional_str(data.get("agent_id")),
            reason=str(data.get("reason") or ""),
            confidence=confidence,
            uncertainty=_optional_str(data.get("uncertainty")),
            raw=dict(data),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MasterRequestRecord:
    request_id: str
    request: str
    project_id: str | None = None
    status: str = "RECEIVED"
    decision: dict[str, object] | None = None
    result: dict[str, object] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> MasterRequestRecord:
        return cls(**json.loads(data))


class MasterRequestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def begin(self, request_id: str, request: str, project_id: str | None) -> MasterRequestRecord:
        record = MasterRequestRecord(request_id=request_id, request=request, project_id=project_id)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM master_requests WHERE request_id = ?", (request_id,)).fetchone()
            if row is not None:
                raise DuplicateMasterRequest(MasterRequestRecord.from_json(row[0]))
            self._upsert(connection, record)
        return record

    def finish(
        self,
        request_id: str,
        status: str,
        decision: dict[str, object] | None = None,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> MasterRequestRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT data FROM master_requests WHERE request_id = ?", (request_id,)).fetchone()
            if row is None:
                raise KeyError(f"master request not found: {request_id}")
            current = MasterRequestRecord.from_json(row[0])
            record = MasterRequestRecord(
                request_id=current.request_id,
                request=current.request,
                project_id=current.project_id,
                status=status,
                decision=decision,
                result=result,
                error=error,
                created_at=current.created_at,
                updated_at=time(),
            )
            self._upsert(connection, record)
        return record

    def get(self, request_id: str) -> MasterRequestRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM master_requests WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            raise KeyError(f"master request not found: {request_id}")
        return MasterRequestRecord.from_json(row[0])

    def list(self, limit: int = 50) -> list[MasterRequestRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM master_requests ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [MasterRequestRecord.from_json(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS master_requests("
                "request_id TEXT PRIMARY KEY, project_id TEXT, status TEXT NOT NULL, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, data TEXT NOT NULL)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_master_requests_project ON master_requests(project_id, created_at)")

    def _upsert(self, connection: sqlite3.Connection, record: MasterRequestRecord) -> None:
        connection.execute(
            "INSERT INTO master_requests(request_id, project_id, status, created_at, updated_at, data) "
            "VALUES(?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(request_id) DO UPDATE SET "
            "project_id = excluded.project_id, status = excluded.status, "
            "updated_at = excluded.updated_at, data = excluded.data",
            (record.request_id, record.project_id, record.status, record.created_at, record.updated_at, record.to_json()),
        )


class MasterProvider:
    def plan(self, request: str, snapshot: dict[str, object]) -> MasterDecision:
        raise NotImplementedError


class FakeMasterProvider(MasterProvider):
    def __init__(self, decisions: list[dict[str, object] | MasterDecision] | None = None) -> None:
        self.decisions = list(decisions or [])

    def plan(self, request: str, snapshot: dict[str, object]) -> MasterDecision:
        if self.decisions:
            decision = self.decisions.pop(0)
            return decision if isinstance(decision, MasterDecision) else MasterDecision.from_mapping(decision)
        project_id = _optional_str(snapshot.get("selected_project_id"))
        projects = snapshot.get("projects") or []
        if project_id is None and len(projects) != 1:
            return MasterDecision(1, "ASK_USER", reason="project selection is ambiguous", uncertainty="select a project")
        if project_id is None and projects:
            project_id = _optional_str(projects[0].get("id")) if isinstance(projects[0], dict) else None
        return MasterDecision(1, "START_AGENT", project_id=project_id, reason="fake master selected a new worker", confidence=0.6)


class CodexMasterProvider(MasterProvider):
    def __init__(self, executable: str = "codex", timeout: float = 120.0, cwd: str | Path | None = None) -> None:
        self.executable = executable
        self.timeout = timeout
        self.cwd = Path(cwd) if cwd else None

    def plan(self, request: str, snapshot: dict[str, object]) -> MasterDecision:
        executable = shutil.which(self.executable)
        if executable is None:
            raise MasterProviderError(f"Codex CLI executable not found: {self.executable}")
        instructions = MASTER_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
        prompt = (
            f"{instructions}\n\n"
            "AgentGrid snapshot JSON:\n"
            f"{json.dumps(snapshot, sort_keys=True)}\n\n"
            "User request:\n"
            f"{request}\n"
        )
        schema = {
            "type": "object",
            "required": ["version", "action", "reason"],
            "properties": {
                "version": {"type": "integer", "const": 1},
                "action": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
                "project_id": {"type": ["string", "null"]},
                "agent_id": {"type": ["string", "null"]},
                "reason": {"type": "string"},
                "confidence": {"type": "number"},
                "uncertainty": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        }
        with tempfile.TemporaryDirectory(prefix="agentgrid-master-") as temp_dir:
            temp_path = Path(temp_dir)
            schema_path = temp_path / "schema.json"
            output_path = temp_path / "last-message.txt"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            command = [
                executable,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ]
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout,
                    cwd=str(self.cwd) if self.cwd else None,
                )
            except subprocess.TimeoutExpired as exc:
                raise MasterProviderError(f"Codex Master timed out after {self.timeout:.1f}s") from exc
            if completed.returncode != 0:
                output = " ".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
                raise MasterProviderError(f"Codex Master failed with exit code {completed.returncode}: {_snippet(output)}")
            raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        return parse_master_decision(raw_output)


class MasterWorkflow:
    def __init__(
        self,
        provider: MasterProvider,
        orchestrator,
        project_manager,
        project_context,
        agent_manager,
        request_store: MasterRequestStore,
    ) -> None:
        self.provider = provider
        self.orchestrator = orchestrator
        self.project_manager = project_manager
        self.project_context = project_context
        self.agent_manager = agent_manager
        self.request_store = request_store

    def handle_request(
        self,
        request: str,
        project_id: str | None = None,
        request_id: str | None = None,
        allow_continue: bool = False,
    ) -> OrchestratorDecision:
        request_id = request_id or f"mr-{int(time() * 1000)}"
        try:
            self.request_store.begin(request_id, request, project_id)
        except DuplicateMasterRequest as exc:
            return OrchestratorDecision(
                "DUPLICATE_REQUEST",
                "master request was already recorded",
                project_id=exc.record.project_id,
                agent_id=_record_agent_id(exc.record),
                details={"request_id": request_id, "record": exc.record.to_dict()},
            )

        snapshot = self.snapshot(request, project_id)
        try:
            master_decision = self.provider.plan(request, snapshot)
            validation_error = self._validate(master_decision, project_id, allow_continue)
            if validation_error is not None:
                result = OrchestratorDecision(
                    validation_error["action"],
                    validation_error["reason"],
                    project_id=master_decision.project_id or project_id,
                    agent_id=master_decision.agent_id,
                    details={"request_id": request_id, "master_decision": master_decision.to_dict(), **validation_error},
                )
            elif master_decision.action in {"ASK_USER", "PARK", "NOOP"}:
                result = OrchestratorDecision(
                    master_decision.action,
                    master_decision.reason,
                    project_id=master_decision.project_id or project_id,
                    agent_id=master_decision.agent_id,
                    details={"request_id": request_id, "master_decision": master_decision.to_dict()},
                )
            else:
                route = RouteDecision(
                    RouteType(master_decision.action),
                    project_id=master_decision.project_id,
                    agent_id=master_decision.agent_id,
                    confidence=master_decision.confidence,
                    reason=master_decision.reason,
                )
                result = self.orchestrator.execute_route(request, route, master_decision.project_id or project_id)
                result.details.update({"request_id": request_id, "master_decision": master_decision.to_dict()})
            status = _status_for_result(result)
            self.request_store.finish(request_id, status, master_decision.to_dict(), result.to_dict(), result.details.get("error"))
            return result
        except MasterProviderError as exc:
            result = OrchestratorDecision(
                "MASTER_FAILED",
                "master provider failed",
                project_id=project_id,
                details={"request_id": request_id, "error": str(exc)},
            )
            self.request_store.finish(request_id, "FAILED", error=str(exc), result=result.to_dict())
            return result
        except Exception as exc:
            result = OrchestratorDecision(
                "MASTER_FAILED",
                "master provider failed",
                project_id=project_id,
                details={"request_id": request_id, "error": str(exc)},
            )
            self.request_store.finish(request_id, "FAILED", error=str(exc), result=result.to_dict())
            return result

    def snapshot(self, request: str, project_id: str | None = None) -> dict[str, object]:
        projects = [project.to_dict() for project in self.project_manager.list_projects(include_closed=True)]
        context = None
        if project_id is not None:
            built = self.project_context.get_context(project_id, query=request, level="summary")
            context = built.to_dict() if hasattr(built, "to_dict") else dict(built)
        return {
            "request": request,
            "selected_project_id": project_id,
            "projects": projects,
            "context": context,
        }

    def _validate(self, decision: MasterDecision, requested_project_id: str | None, allow_continue: bool) -> dict[str, object] | None:
        if decision.version != 1:
            return {"action": "MASTER_DECISION_REJECTED", "reason": "unsupported master decision version"}
        if decision.action not in ALLOWED_ACTIONS:
            return {"action": "MASTER_DECISION_REJECTED", "reason": "unsupported master action"}
        if decision.project_id is not None:
            try:
                self.project_manager.get_project(decision.project_id)
            except Exception as exc:
                return {"action": "MASTER_DECISION_REJECTED", "reason": "unknown project id", "error": str(exc)}
        if requested_project_id and decision.project_id and requested_project_id != decision.project_id:
            return {"action": "MASTER_DECISION_REJECTED", "reason": "master selected a different project"}
        if decision.action == "START_AGENT" and not decision.project_id:
            return {"action": "ASK_USER", "reason": "master did not select a project"}
        if decision.action == "CONTINUE_AGENT":
            if not decision.project_id or not decision.agent_id:
                return {"action": "MASTER_DECISION_REJECTED", "reason": "continue requires project_id and agent_id"}
            owner = self._owner_for_agent(decision.agent_id)
            if owner != decision.project_id:
                return {"action": "MASTER_DECISION_REJECTED", "reason": "agent does not belong to selected project"}
            try:
                agent = self.agent_manager.inspect(decision.agent_id)
            except Exception as exc:
                return {"action": "MASTER_DECISION_REJECTED", "reason": "unknown agent id", "error": str(exc)}
            state = getattr(getattr(agent, "state", None), "value", getattr(agent, "state", None))
            if state != "RUNNING":
                return {"action": "PARK", "reason": "agent is not running", "runtime_state": state}
            if not allow_continue:
                return {
                    "action": "PARK",
                    "reason": "continuation needs explicit confirmation until worker readiness is available",
                    "runtime_state": state,
                }
        return None

    def _owner_for_agent(self, agent_id: str) -> str | None:
        for project in self.project_manager.list_projects(include_closed=True):
            if agent_id in project.agents:
                return project.id
        return None


def parse_master_decision(output: str) -> MasterDecision:
    text = output.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MasterProviderError(f"master returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MasterProviderError("master returned non-object JSON")
    return MasterDecision.from_mapping(data)


def _status_for_result(result: OrchestratorDecision) -> str:
    if result.action in {"ASK_USER", "PARK", "AGENT_START_FAILED", "AGENT_SEND_FAILED", "MASTER_DECISION_REJECTED"}:
        return "PARKED"
    if result.action == "MASTER_FAILED":
        return "FAILED"
    return "EXECUTED"


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return None if text.lower() == "null" else text


def _record_agent_id(record: MasterRequestRecord) -> str | None:
    if record.result and record.result.get("agent_id") is not None:
        return str(record.result["agent_id"])
    return None


def _snippet(output: str, limit: int = 500) -> str:
    clean = " ".join(output.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."
