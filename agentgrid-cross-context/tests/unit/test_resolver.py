from agentgrid_cross_context import CrossSystemContextResolver


def test_resolver_matches_project_name() -> None:
    result = CrossSystemContextResolver().resolve({"subject": "demo failed"}, [{"id": "demo", "name": "Demo"}])
    assert result.project_id == "demo"
    assert result.ask_user is False


def test_resolver_asks_when_confidence_low() -> None:
    result = CrossSystemContextResolver().resolve({"subject": "unknown"}, [{"id": "demo"}])
    assert result.ask_user is True
