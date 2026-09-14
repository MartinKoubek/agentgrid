from agentgrid_observability import DiagnosticLogger


def test_diagnostic_logger_writes_jsonl(tmp_path) -> None:
    logger = DiagnosticLogger(tmp_path / "diagnostics.jsonl")
    logger.log("AGENT_FAILED", project_id="demo", agent_id="ag-001", error="boom")
    records = logger.read()
    assert records[0]["event"] == "AGENT_FAILED"
    assert records[0]["details"] == {"error": "boom"}
