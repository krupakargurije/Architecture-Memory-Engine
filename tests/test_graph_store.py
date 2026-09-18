from ame.graph.embedded_store import EmbeddedGraphStore
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.models.snapshot import RepositorySnapshot, SnapshotType


def test_embedded_graph_store_save_and_retrieve(tmp_path):
    db_path = tmp_path / "test_ame.db"
    store = EmbeddedGraphStore(db_path)

    snapshot = RepositorySnapshot(
        repo_id="my-repo",
        snapshot_type=SnapshotType.COMMIT,
        commit_id="abc1234",
    )

    node1 = Node(
        id="controller:OrderController",
        name="OrderController",
        entity_type=EntityType.CONTROLLER,
        file_path="OrderController.java",
    )
    node2 = Node(
        id="service:OrderService",
        name="OrderService",
        entity_type=EntityType.SERVICE,
        file_path="OrderService.java",
    )
    edge = Edge(
        source="controller:OrderController",
        target="service:OrderService",
        relation=RelationType.CALLS,
        confidence=0.95,
        source_type=SourceType.STATIC_ANALYSIS,
    )

    store.save_snapshot(snapshot, [node1, node2], [edge])

    # Verify retrieval
    retrieved_snap = store.get_snapshot(snapshot.snapshot_id)
    assert retrieved_snap is not None
    assert retrieved_snap.commit_id == "abc1234"

    nodes = store.get_nodes(snapshot.snapshot_id)
    assert len(nodes) == 2

    edges = store.get_edges(snapshot.snapshot_id)
    assert len(edges) == 1
    assert edges[0].source == "controller:OrderController"
    assert edges[0].target == "service:OrderService"

    # Verify NetworkX graph construction
    G = store.get_graph(snapshot.snapshot_id)
    assert G.has_edge("controller:OrderController", "service:OrderService")
