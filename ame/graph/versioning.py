"""Repository versioning and snapshot manager for Architecture Memory Engine.
Tracks snapshot lineage across Git commits, branches, and active workspace states.
"""

from typing import Dict, List, Optional, Set, Tuple
from ame.graph.base import BaseGraphStore
from ame.models.schema import Edge, Node
from ame.models.snapshot import ChangeType, RepositorySnapshot, SnapshotType, UncommittedChange


class VersionManager:
    """Manages snapshot creation, lineage, and structural diffing between graph states."""

    def __init__(self, store: BaseGraphStore):
        self.store = store

    def create_snapshot(
        self,
        repo_id: str,
        snapshot_type: SnapshotType = SnapshotType.WORKSPACE,
        commit_id: Optional[str] = None,
        branch: Optional[str] = None,
        workspace_id: Optional[str] = None,
        uncommitted_changes: Optional[Dict[str, UncommittedChange]] = None,
    ) -> RepositorySnapshot:
        snapshot = RepositorySnapshot(
            repo_id=repo_id,
            snapshot_type=snapshot_type,
            commit_id=commit_id,
            branch=branch,
            workspace_id=workspace_id,
            uncommitted_changes=uncommitted_changes or {},
        )
        return snapshot

    def diff_snapshots(
        self, base_snapshot_id: str, target_snapshot_id: str
    ) -> Dict[str, List[str]]:
        """
        Computes structural difference between two graph snapshots:
        returns added_nodes, removed_nodes, added_edges, removed_edges.
        """
        base_nodes = {n.id for n in self.store.get_nodes(base_snapshot_id)}
        target_nodes = {n.id for n in self.store.get_nodes(target_snapshot_id)}

        base_edges = {(e.source, e.target, e.relation.value) for e in self.store.get_edges(base_snapshot_id)}
        target_edges = {(e.source, e.target, e.relation.value) for e in self.store.get_edges(target_snapshot_id)}

        return {
            "added_nodes": list(target_nodes - base_nodes),
            "removed_nodes": list(base_nodes - target_nodes),
            "added_edges": [f"{s} --[{r}]--> {t}" for s, t, r in (target_edges - base_edges)],
            "removed_edges": [f"{s} --[{r}]--> {t}" for s, t, r in (base_edges - target_edges)],
        }
