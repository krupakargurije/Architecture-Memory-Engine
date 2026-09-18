from ame.graph.embedded_store import EmbeddedGraphStore
from ame.incremental.updater import IncrementalGraphUpdater
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.models.snapshot import ChangeType, RepositorySnapshot, SnapshotType, UncommittedChange


def test_incremental_workspace_update(tmp_path):
    store = EmbeddedGraphStore(tmp_path / "ame_inc.db")
    updater = IncrementalGraphUpdater(store)

    snap1 = RepositorySnapshot(
        repo_id="test-repo",
        snapshot_type=SnapshotType.COMMIT,
        commit_id="c1",
    )

    n1 = Node(id="service:ServiceA", name="ServiceA", entity_type=EntityType.SERVICE, file_path="ServiceA.java")
    n2 = Node(id="service:ServiceB", name="ServiceB", entity_type=EntityType.SERVICE, file_path="ServiceB.java")
    e1 = Edge(source="service:ServiceA", target="service:ServiceB", relation=RelationType.CALLS, confidence=1.0, source_type=SourceType.STATIC_ANALYSIS)

    store.save_snapshot(snap1, [n1, n2], [e1])

    # Modify ServiceB in uncommitted workspace buffer
    updated_service_b = """
    package com.example;
    import org.springframework.stereotype.Service;

    @Service
    public class ServiceB {
        public void newMethod() {}
    }
    """
    changes = {
        "ServiceB.java": UncommittedChange(
            file_path="ServiceB.java",
            change_type=ChangeType.MODIFIED,
            content=updated_service_b,
        )
    }

    new_snap, stats = updater.apply_workspace_changes(
        base_snapshot_id=snap1.snapshot_id,
        changed_files=changes,
    )

    assert new_snap.snapshot_id != snap1.snapshot_id
    assert new_snap.snapshot_type == SnapshotType.WORKSPACE
    assert new_snap.is_dirty

    # ServiceA should still be retained
    new_nodes = store.get_nodes(new_snap.snapshot_id)
    names = {n.name for n in new_nodes}
    assert "ServiceA" in names
    assert "ServiceB" in names
