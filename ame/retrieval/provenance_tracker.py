"""Provenance tracking builder for Architecture Memory Engine.
Traces and annotates context elements with snapshot IDs, line ranges, and relationship paths.
"""

from typing import List, Optional
from ame.models.provenance import ProvenanceRecord, RelationshipBreadcrumb
from ame.models.schema import Edge, Node


class ProvenanceTracker:
    """Constructs verifiable provenance records for retrieved architectural items."""

    def build_record(
        self,
        node: Node,
        snapshot_id: str,
        commit_id: Optional[str] = None,
        breadcrumbs: Optional[List[RelationshipBreadcrumb]] = None,
        confidence: float = 1.0,
    ) -> ProvenanceRecord:
        return ProvenanceRecord(
            node_id=node.id,
            file_path=node.file_path,
            start_line=node.start_line,
            end_line=node.end_line,
            snapshot_id=snapshot_id,
            commit_id=commit_id,
            breadcrumbs=breadcrumbs or [],
            confidence=confidence,
        )

    def edge_to_breadcrumb(self, edge: Edge) -> RelationshipBreadcrumb:
        return RelationshipBreadcrumb(
            source_node=edge.source.split(":")[-1],
            relation=edge.relation.value,
            target_node=edge.target.split(":")[-1],
            confidence=edge.confidence,
            source_type=edge.source_type.value,
        )
