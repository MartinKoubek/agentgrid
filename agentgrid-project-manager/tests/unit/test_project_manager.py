from agentgrid_project_manager import Project, ProjectManager, ProjectState


def test_project_manager_open_list_close(tmp_path) -> None:
    manager = ProjectManager(tmp_path / "projects.sqlite3")
    project = manager.open_project("demo", path="/repo", name="Demo")

    assert project.id == "demo"
    assert project.state == ProjectState.OPEN
    assert manager.get_project("demo").path == "/repo"
    assert manager.get_last_active_project().id == "demo"

    closed = manager.close_project("demo")
    assert closed.state == ProjectState.CLOSED
    assert manager.list_projects() == []
    assert manager.list_projects(include_closed=True)[0].id == "demo"


def test_project_tracks_agent_membership_not_liveness(tmp_path) -> None:
    manager = ProjectManager(tmp_path / "projects.sqlite3")
    manager.open_project("demo", path="/repo", name="Demo")

    project = manager.add_agent("demo", "ag-001")
    project = manager.add_agent("demo", "ag-001")

    assert project.agents == ["ag-001"]
    assert project.to_dict()["agents"] == ["ag-001"]
    assert "active_agents" not in project.to_dict()


def test_project_migrates_legacy_active_agents() -> None:
    project = Project.from_json(
        '{"id":"demo","path":"/repo","state":"OPEN","active_agents":["ag-001"],"workspace":{},"config":{}}'
    )

    assert project.agents == ["ag-001"]
