from __future__ import annotations

import sqlite3
from pathlib import Path

from agentgrid_project_manager.models import Project, ProjectState


class ProjectManager:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".agentgrid" / "projects.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def open_project(self, project_id: str, path: str, name: str | None = None, repository: str | None = None) -> Project:
        try:
            project = self.get_project(project_id)
            project.path = path
            project.name = name or project.name
            project.repository = repository or project.repository
            project.state = ProjectState.OPEN
            project.touch()
        except KeyError:
            project = Project(id=project_id, path=path, name=name, repository=repository)
        self.save(project)
        return project

    def get_project(self, project_id: str) -> Project:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(f"project not found: {project_id}")
        return Project.from_json(row[0])

    def list_projects(self, include_closed: bool = False) -> list[Project]:
        sql = "SELECT data FROM projects"
        params: list[object] = []
        if not include_closed:
            sql += " WHERE state != ?"
            params.append(ProjectState.CLOSED.value)
        sql += " ORDER BY last_activity_at DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [Project.from_json(row[0]) for row in rows]

    def close_project(self, project_id: str) -> Project:
        project = self.get_project(project_id)
        project.state = ProjectState.CLOSED
        project.touch()
        self.save(project)
        return project

    def get_last_active_project(self) -> Project | None:
        projects = self.list_projects()
        return projects[0] if projects else None

    def save(self, project: Project) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO projects(id, state, last_activity_at, data) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET state = excluded.state, last_activity_at = excluded.last_activity_at, data = excluded.data",
                (project.id, project.state.value, project.last_activity_at, project.to_json()),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, state TEXT NOT NULL, last_activity_at REAL NOT NULL, data TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_projects_activity ON projects(state, last_activity_at)")
