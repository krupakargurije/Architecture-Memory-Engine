"""Base abstractions for multi-source repository ingestion in AME.
Normalizes Local Git, GitHub, and IDE Live workspace buffers into a uniform representation.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from ame.models.snapshot import RepositorySnapshot, UncommittedChange


class NormalizedFile(BaseModel):
    rel_path: str = Field(..., description="Normalized relative file path with forward slashes")
    content: str = Field(..., description="File text content")
    is_uncommitted: bool = Field(default=False, description="Whether this file has uncommitted local changes")
    checksum: Optional[str] = Field(default=None, description="SHA256 checksum of content")


class NormalizedRepo(BaseModel):
    repo_id: str = Field(..., description="Unique repository ID")
    name: str = Field(..., description="Repository name")
    root_path: Optional[str] = Field(default=None, description="Local root path if available")
    branch: Optional[str] = Field(default=None, description="Current branch name")
    commit_id: Optional[str] = Field(default=None, description="Current commit hash")
    files: Dict[str, NormalizedFile] = Field(default_factory=dict, description="Relative path -> file")
    snapshot: RepositorySnapshot = Field(..., description="Snapshot state representation")


class BaseIngestionSource(ABC):
    """Abstract base class for all repository ingestion sources."""

    @abstractmethod
    def ingest(self, target: str, **kwargs) -> NormalizedRepo:
        """
        Ingest the given target (file path, URL, or workspace descriptor)
        and produce a NormalizedRepo ready for parsing and graph building.
        """
        pass
