from agentgrid_project_memory import ProjectMemory


def test_project_memory_add_list_search(tmp_path) -> None:
    memory = ProjectMemory(tmp_path / "memory.sqlite3")
    memory.add("demo", ProjectMemory.PROJECT_STATE, "Tests use pytest")
    memory.add("demo", ProjectMemory.LESSONS_LEARNED, "Avoid fixed sleeps")

    assert len(memory.list("demo")) == 2
    assert memory.list("demo", ProjectMemory.PROJECT_STATE)[0].content == "Tests use pytest"
    assert memory.search("demo", "sleeps")[0].category == ProjectMemory.LESSONS_LEARNED
