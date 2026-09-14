from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConnectorEvent:
    connector: str
    type: str
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]: return asdict(self)


class Connector(Protocol):
    name: str
    def poll(self) -> list[ConnectorEvent]: ...


class StubConnector:
    def __init__(self, name: str, events: list[ConnectorEvent] | None = None) -> None:
        self.name = name; self.events = list(events or [])
    def poll(self) -> list[ConnectorEvent]: return list(self.events)


class ConnectorRegistry:
    def __init__(self) -> None:
        self.connectors: dict[str, Connector] = {}
    def register(self, connector: Connector) -> None:
        self.connectors[connector.name] = connector
    def poll_all(self) -> list[ConnectorEvent]:
        events: list[ConnectorEvent] = []
        for connector in self.connectors.values(): events.extend(connector.poll())
        return events


def default_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    for name in ["email", "slack", "github", "calendar"]:
        registry.register(StubConnector(name))
    return registry
