from agentgrid_project_manager import ProjectManager, ProjectState


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
