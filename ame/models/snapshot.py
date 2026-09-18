"""Repository and Snapshot state models for Architecture Memory Engine.
Central hierarchy:
Repository -> (Commit Snapshot | Branch Snapshot | Workspace Snapshot [committed + uncommitted]) -> Graph
"""

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SnapshotType(str, Enum):
    COMMIT = "commit"
    BRANCH = "branch"
    WORKSPACE = "workspace"


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


class UncommittedChange(BaseModel):
    file_path: str = Field(..., description="Relative file path")
    change_type: ChangeType = Field(..., description="Type of change: added, modified, deleted")
    content: Optional[str] = Field(default=None, description="Current in-memory content if available")
    diff: Optional[str] = Field(default=None, description="Unified git diff if available")


class RepositorySnapshot(BaseModel):
    snapshot_id: str = Field(
        default_factory=lambda: f"snap-{uuid.uuid4().hex[:12]}",
        description="Unique identifier for this snapshot"
    )
    repo_id: str = Field(..., description="Unique ID of the parent repository")
    snapshot_type: SnapshotType = Field(default=SnapshotType.WORKSPACE, description="Type of snapshot")
    commit_id: Optional[str] = Field(default=None, description="Git commit hash if applicable")
    branch: Optional[str] = Field(default=None, description="Git branch name if applicable")
    workspace_id: Optional[str] = Field(default=None, description="Local IDE or agent workspace identifier")
    timestamp: float = Field(default_factory=time.time, description="Creation timestamp")
    uncommitted_changes: Dict[str, UncommittedChange] = Field(
        default_factory=dict,
        description="Map of relative file paths to active uncommitted changes"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary snapshot metadata")

    @property
    def is_dirty(self) -> bool:
        """True if the snapshot contains uncommitted workspace modifications."""
        return len(self.uncommitted_changes) > 0


class Repository(BaseModel):
    repo_id: str = Field(..., description="Unique repository identifier")
    name: str = Field(..., description="Repository name")
    source_url_or_path: str = Field(..., description="Local folder path or GitHub URL")
    default_branch: str = Field(default="main", description="Default branch name")
    created_at: float = Field(default_factory=time.time, description="Registered timestamp")
    snapshots: List[str] = Field(default_factory=list, description="List of snapshot IDs associated with this repo")


class RepositoryIngestionResult(BaseModel):
    repo_id: str = Field(..., description="Repository ID")
    snapshot_id: str = Field(..., description="Generated snapshot ID")
    commit_id: Optional[str] = Field(default=None, description="Resolved commit SHA")
    branch: Optional[str] = Field(default=None, description="Branch ingested")
    files_analyzed: int = Field(default=0, description="Total source files parsed")
    nodes_created: int = Field(default=0, description="Total architectural nodes")
    edges_created: int = Field(default=0, description="Total architectural edges")
    languages: List[str] = Field(default_factory=list, description="Languages detected and analyzed")
    status: str = Field(default="completed", description="Status of ingestion")
    storage_mode: str = Field(default="in_memory_transient_no_clone", description="Confirms zero local disk clone")
    architecture_summary: Optional[Dict[str, Any]] = Field(default=None, description="Deterministic architectural breakdown")

