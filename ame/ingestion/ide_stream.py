"""IDE / Agent in-memory workspace stream ingestion source.
Allows AI agents to submit uncommitted buffers, newly created files, or editor diffs directly.
"""

from typing import Dict, Optional
from ame.ingestion.base import BaseIngestionSource, NormalizedFile, NormalizedRepo
from ame.ingestion.local_git import LocalGitIngestion
from ame.models.snapshot import ChangeType, RepositorySnapshot, SnapshotType, UncommittedChange


class IDEStreamIngestion(BaseIngestionSource):
    """
    Combines a base local repo with active, uncommitted in-memory buffers provided by an IDE/agent.
    """

    def __init__(self):
        self.local_ingestion = LocalGitIngestion()

    def ingest(
        self,
        target: str,
        uncommitted_buffers: Optional[Dict[str, str]] = None,
        workspace_id: Optional[str] = None,
        repo_id: Optional[str] = None,
        **kwargs
    ) -> NormalizedRepo:
        """
        target: local repository root path
        uncommitted_buffers: dict of rel_path -> uncommitted file text
        """
        # Ingest base repo first
        base_repo = self.local_ingestion.ingest(target=target, repo_id=repo_id, workspace_id=workspace_id)
        if not uncommitted_buffers:
            return base_repo

        uncommitted_map = dict(base_repo.snapshot.uncommitted_changes)

        # Overlay uncommitted buffers
        for rel_path, content in uncommitted_buffers.items():
            clean_rel = rel_path.replace("\\", "/")
            is_new = clean_rel not in base_repo.files

            base_repo.files[clean_rel] = NormalizedFile(
                rel_path=clean_rel,
                content=content,
                is_uncommitted=True,
            )

            uncommitted_map[clean_rel] = UncommittedChange(
                file_path=clean_rel,
                change_type=ChangeType.ADDED if is_new else ChangeType.MODIFIED,
                content=content,
            )

        # Force snapshot type to WORKSPACE
        base_repo.snapshot = RepositorySnapshot(
            repo_id=base_repo.repo_id,
            snapshot_type=SnapshotType.WORKSPACE,
            commit_id=base_repo.commit_id,
            branch=base_repo.branch,
            workspace_id=workspace_id or base_repo.snapshot.workspace_id,
            uncommitted_changes=uncommitted_map,
        )

        return base_repo
