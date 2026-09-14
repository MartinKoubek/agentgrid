from agentgrid_execution import DriverRegistry, ExecutionManager, LocalCommandDriver


def test_execution_manager_runs_command() -> None:
    result = ExecutionManager().run(["python3.11", "-c", "print('ok')"])
    assert result.succeeded is True
    assert result.stdout == "ok\n"


def test_local_e2e_driver_runs_command() -> None:
    manager = ExecutionManager()
    registry = DriverRegistry()
    registry.register(LocalCommandDriver(manager))
    result = registry.get("local").run(["python3.11", "-c", "print('driver')"])
    assert result.succeeded is True
    assert result.stdout == "driver\n"
