"""Incremental graph updater for Architecture Memory Engine.
Selectively invalidates and re-indexes modified components without re-parsing unchanged repository files.
"""

from typing import Dict, List, Optional, Set, Tuple
from ame.graph.base import BaseGraphStore
from ame.incremental.diff_analyzer import DiffAnalyzer
from ame.models.schema import Edge, Node
from ame.models.snapshot import ChangeType, RepositorySnapshot, SnapshotType, UncommittedChange
from ame.parser.inferrer import RelationshipInferrer, default_inferrer
from ame.parser.registry import ParserRegistry, default_parser_registry


class IncrementalGraphUpdater:
    """Applies file-level changes onto existing snapshots to produce updated graph states."""

    def __init__(
        self,
        store: BaseGraphStore,
        diff_analyzer: Optional[DiffAnalyzer] = None,
        parser_registry: Optional[ParserRegistry] = None,
        inferrer: Optional[RelationshipInferrer] = None,
    ):
        self.store = store
        self.diff_analyzer = diff_analyzer or DiffAnalyzer()
        self.parser_registry = parser_registry or default_parser_registry
        self.inferrer = inferrer or default_inferrer

    def apply_workspace_changes(
        self,
        base_snapshot_id: str,
        changed_files: Dict[str, UncommittedChange],
        new_commit_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Tuple[RepositorySnapshot, Dict[str, int]]:
        """
        Incrementally updates the graph for changed files.
        Returns (new_snapshot, update_stats).
        """
        base_snapshot = self.store.get_snapshot(base_snapshot_id)
        if not base_snapshot:
            raise ValueError(f"Base snapshot {base_snapshot_id} not found")

        existing_nodes = self.store.get_nodes(base_snapshot_id)
        existing_edges = self.store.get_edges(base_snapshot_id)

        # 1. Compute invalidated nodes
        invalidated_node_ids = self.diff_analyzer.compute_invalidated_node_ids(
            existing_nodes, changed_files
        )

        # 2. Retain untouched nodes and clean edges
        retained_nodes = [n for n in existing_nodes if n.id not in invalidated_node_ids]
        retained_edges = [
            e for e in existing_edges
            if e.source not in invalidated_node_ids and e.target not in invalidated_node_ids
        ]

        # 3. Parse only added/modified files
        new_nodes: List[Node] = []
        new_edges: List[Edge] = []

        for rel_path, change in changed_files.items():
            if change.change_type == ChangeType.DELETED:
                continue

            if not change.content:
                continue

            parser = self.parser_registry.get_parser(rel_path)
            if not parser:
                continue

            try:
                parsed_nodes, parsed_edges = parser.parse(rel_path, change.content)
                new_nodes.extend(parsed_nodes)
                new_edges.extend(parsed_edges)
            except Exception:
                continue

        # 4. Merge retained and new nodes
        merged_nodes = retained_nodes + new_nodes
        new_node_ids = {n.id for n in new_nodes}

        # Reconnect incoming edges from untouched nodes that target recreated nodes (e.g. callers, tests)
        reconnected_edges = [
            e for e in existing_edges
            if e.source not in invalidated_node_ids and e.target in new_node_ids
        ]

        merged_edges = retained_edges + reconnected_edges + new_edges

        # 5. Re-run inference across components
        final_nodes, final_edges = self.inferrer.resolve_and_enrich(merged_nodes, merged_edges)

        # 6. Create new snapshot
        snap_type = SnapshotType.COMMIT if (new_commit_id and not changed_files) else SnapshotType.WORKSPACE
        updated_uncommitted = dict(base_snapshot.uncommitted_changes)
        for k, v in changed_files.items():
            if v.change_type == ChangeType.DELETED:
                updated_uncommitted.pop(k, None)
            else:
                updated_uncommitted[k] = v

        new_snapshot = RepositorySnapshot(
            repo_id=base_snapshot.repo_id,
            snapshot_type=snap_type,
            commit_id=new_commit_id or base_snapshot.commit_id,
            branch=base_snapshot.branch,
            workspace_id=workspace_id or base_snapshot.workspace_id,
            uncommitted_changes=updated_uncommitted,
        )

        # 7. Persist new snapshot
        self.store.save_snapshot(new_snapshot, final_nodes, final_edges)

        stats = {
            "invalidated_nodes": len(invalidated_node_ids),
            "added_nodes": len(new_nodes),
            "total_nodes": len(final_nodes),
            "total_edges": len(final_edges),
        }
        return new_snapshot, stats
