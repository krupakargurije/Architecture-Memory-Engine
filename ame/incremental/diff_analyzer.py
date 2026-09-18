"""Diff and workspace delta analyzer for Architecture Memory Engine.
Detects added, modified, and deleted files to calculate invalidated graph components.
"""

from typing import Dict, List, Set
from ame.models.schema import Node
from ame.models.snapshot import ChangeType, UncommittedChange


class DiffAnalyzer:
    """Analyzes workspace deltas to determine which graph nodes and edges are affected."""

    def compute_invalidated_node_ids(
        self,
        existing_nodes: List[Node],
        changed_files: Dict[str, UncommittedChange],
    ) -> Set[str]:
        """
        Identify node IDs belonging to modified or deleted files that must be removed/recomputed.
        """
        changed_path_set = {
            f.replace("\\", "/") for f in changed_files.keys()
        }

        invalidated_ids: Set[str] = set()
        for node in existing_nodes:
            if node.file_path and node.file_path.replace("\\", "/") in changed_path_set:
                invalidated_ids.add(node.id)

        return invalidated_ids
