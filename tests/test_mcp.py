import json
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.mcp.server import MCPServer
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.models.snapshot import RepositorySnapshot, SnapshotType


def test_mcp_server_protocol(tmp_path):
    store = EmbeddedGraphStore(tmp_path / "ame_mcp.db")
    server = MCPServer(store)

    # 1. initialize
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = server.handle_request(init_req)
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "Architecture Memory Engine"

    # 2. tools/list
    list_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = server.handle_request(list_req)
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    assert "retrieve_context" in tool_names
    assert "find_impact" in tool_names
    assert "get_repository_architecture" in tool_names

    # Seed store with data
    snap = RepositorySnapshot(repo_id="mcp-test-repo", snapshot_type=SnapshotType.COMMIT)
    n1 = Node(id="controller:OrderController", name="OrderController", entity_type=EntityType.CONTROLLER)
    n2 = Node(id="service:OrderService", name="OrderService", entity_type=EntityType.SERVICE)
    e = Edge(source="controller:OrderController", target="service:OrderService", relation=RelationType.CALLS, confidence=1.0, source_type=SourceType.STATIC_ANALYSIS)
    store.save_snapshot(snap, [n1, n2], [e])

    # 3. tools/call get_repository_architecture
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_repository_architecture",
            "arguments": {"repo_id": "mcp-test-repo"}
        }
    }
    resp = server.handle_request(call_req)
    assert resp["id"] == 3
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert data["repo_id"] == "mcp-test-repo"
    assert "OrderController" in data["controllers"]
    assert "OrderService" in data["services"]
