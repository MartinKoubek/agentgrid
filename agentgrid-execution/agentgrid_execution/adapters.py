from __future__ import annotations

from abc import ABC, abstractmethod

from agentgrid_execution.models import ExecutionResult


class E2EDriverAdapter(ABC):
    name: str

    @abstractmethod
    def run(self, command: list[str], cwd: str | None = None, timeout: float | None = None) -> ExecutionResult:
        raise NotImplementedError


class LocalCommandDriver(E2EDriverAdapter):
    name = "local"

    def __init__(self, execution_manager) -> None:
        self.execution_manager = execution_manager

    def run(self, command: list[str], cwd: str | None = None, timeout: float | None = None) -> ExecutionResult:
        return self.execution_manager.run(command, cwd=cwd, timeout=timeout)


class DriverRegistry:
    def __init__(self, drivers: dict[str, E2EDriverAdapter] | None = None) -> None:
        self.drivers = dict(drivers or {})

    def register(self, driver: E2EDriverAdapter) -> None:
        self.drivers[driver.name] = driver

    def get(self, name: str) -> E2EDriverAdapter:
        try:
            return self.drivers[name]
        except KeyError as exc:
            raise ValueError(f"unknown E2E driver: {name}") from exc
