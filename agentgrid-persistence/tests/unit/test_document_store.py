from agentgrid_persistence import DocumentStore


def test_document_store_put_get_list_delete(tmp_path) -> None:
    store = DocumentStore(tmp_path / "store.sqlite3")
    store.put("projects", "demo", {"path": "/repo"})
    assert store.get("projects", "demo") == {"path": "/repo"}
    assert store.list("projects")[0]["key"] == "demo"
    store.delete("projects", "demo")
    assert store.get("projects", "demo") is None
