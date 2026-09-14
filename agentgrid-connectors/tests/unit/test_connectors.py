from agentgrid_connectors import ConnectorEvent, ConnectorRegistry, StubConnector


def test_connector_registry_polls_registered_connectors() -> None:
    event = ConnectorEvent("email", "EMAIL_RECEIVED", {"subject": "hello"})
    registry = ConnectorRegistry(); registry.register(StubConnector("email", [event]))
    assert registry.poll_all() == [event]
