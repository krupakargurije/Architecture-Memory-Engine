"""Local filesystem and Git repository ingestion source.
Detects Git commit, branch, and uncommitted modifications, creating a Workspace Snapshot.
"""

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from ame.ingestion.base import BaseIngestionSource, NormalizedFile, NormalizedRepo
from ame.models.snapshot import ChangeType, RepositorySnapshot, SnapshotType, UncommittedChange
from ame.security.filter import SecurityFilter, default_security_filter


class LocalGitIngestion(BaseIngestionSource):
    """Ingests a local repository or directory workspace with Git awareness."""

    def __init__(self, security_filter: Optional[SecurityFilter] = None):
        self.security_filter = security_filter or default_security_filter

    def ingest(
        self,
        target: str,
        repo_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        **kwargs
    ) -> NormalizedRepo:
        root_dir = Path(target).resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            raise ValueError(f"Directory not found: {target}")

        repo_name = root_dir.name
        r_id = repo_id or f"repo-{repo_name.lower().replace(' ', '-')}"

        commit_id = self._get_git_commit(root_dir)
        branch = self._get_git_branch(root_dir)
        uncommitted_map = self._get_uncommitted_changes(root_dir)

        # Snapshot type depends on whether there are uncommitted changes
        snapshot_type = SnapshotType.WORKSPACE if uncommitted_map else SnapshotType.COMMIT

        snapshot = RepositorySnapshot(
            repo_id=r_id,
            snapshot_type=snapshot_type,
            commit_id=commit_id,
            branch=branch,
            workspace_id=workspace_id or f"ws-{repo_name}",
            uncommitted_changes=uncommitted_map,
        )

        files_map: Dict[str, NormalizedFile] = {}

        for root, dirs, filenames in os.walk(root_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in self.security_filter.ignored_dirs and not d.startswith(".")]

            for fname in filenames:
                full_path = Path(root) / fname
                rel_path = full_path.relative_to(root_dir)

                is_safe, _ = self.security_filter.is_safe_to_index(rel_path)
                if not is_safe or self.security_filter._is_binary(full_path):
                    continue

                normalized_rel = str(rel_path).replace("\\", "/")
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                is_uncommitted = normalized_rel in uncommitted_map

                files_map[normalized_rel] = NormalizedFile(
                    rel_path=normalized_rel,
                    content=content,
                    is_uncommitted=is_uncommitted,
                    checksum=checksum,
                )

        return NormalizedRepo(
            repo_id=r_id,
            name=repo_name,
            root_path=str(root_dir),
            branch=branch,
            commit_id=commit_id,
            files=files_map,
            snapshot=snapshot,
        )

    def _get_git_commit(self, root_dir: Path) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(root_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def _get_git_branch(self, root_dir: Path) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(root_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def _get_uncommitted_changes(self, root_dir: Path) -> Dict[str, UncommittedChange]:
        """Detect modified, added, or deleted files using git status."""
        changes: Dict[str, UncommittedChange] = {}
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                return changes

            for line in res.stdout.splitlines():
                if len(line) < 3:
                    continue
                status = line[:2].strip()
                fpath = line[3:].strip().strip('"').replace("\\", "/")

                if "?" in status or "A" in status:
                    ch_type = ChangeType.ADDED
                elif "D" in status:
                    ch_type = ChangeType.DELETED
                else:
                    ch_type = ChangeType.MODIFIED

                changes[fpath] = UncommittedChange(
                    file_path=fpath,
                    change_type=ch_type,
                )
        except Exception:
            pass
        return changes
