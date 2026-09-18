"""Provenance tracking models for Architecture Memory Engine.
Explains the origin, chain of reasoning, and confidence behind every context item.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class RelationshipBreadcrumb(BaseModel):
    source_node: str = Field(..., description="Starting node in relationship")
    relation: str = Field(..., description="Edge relation (e.g. CALLS, USES, TESTED_BY)")
    target_node: str = Field(..., description="Ending node in relationship")
    confidence: float = Field(default=1.0, description="Confidence of this specific link")
    source_type: str = Field(default="static_analysis", description="Static or inferred")

    def __str__(self) -> str:
        return f"{self.source_node} --[{self.relation} ({self.confidence:.2f})]-> {self.target_node}"


class ProvenanceRecord(BaseModel):
    node_id: str = Field(..., description="Target node ID")
    file_path: Optional[str] = Field(default=None, description="Source file path")
    start_line: Optional[int] = Field(default=None, description="Start line in file")
    end_line: Optional[int] = Field(default=None, description="End line in file")
    snapshot_id: str = Field(..., description="Snapshot version from which this was retrieved")
    commit_id: Optional[str] = Field(default=None, description="Commit hash if committed")
    breadcrumbs: List[RelationshipBreadcrumb] = Field(
        default_factory=list,
        description="Chain of architectural relationships connecting this item to the seed query"
    )
    confidence: float = Field(default=1.0, description="Composite confidence score")

    def formatted_summary(self) -> str:
        chain = " -> ".join([b.relation for b in self.breadcrumbs]) if self.breadcrumbs else "Direct seed"
        lines = f":L{self.start_line}-{self.end_line}" if self.start_line and self.end_line else ""
        return f"[{self.node_id}] from {self.file_path or 'unknown'}{lines} via {chain} (conf: {self.confidence:.2f})"
