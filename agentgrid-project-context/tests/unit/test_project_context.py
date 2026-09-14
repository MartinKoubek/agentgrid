from agentgrid_project_context import ProjectContextBuilder


def test_context_builder_returns_compact_context() -> None:
    context = ProjectContextBuilder().get_context("demo", query="tests")
    assert context.project_id == "demo"
    assert context.query == "tests"
    assert context.agents == []
