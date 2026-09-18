"""GitHub repository connector for Architecture Memory Engine.
Temporarily clones a repository into an OS-level temporary directory,
runs architectural analysis, persists only graph metadata, then deletes
the temporary workspace — even on failure.
"""

import logging
import re
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from ame.ingestion.base import BaseIngestionSource, NormalizedRepo
from ame.ingestion.local_git import LocalGitIngestion
from ame.ingestion.pipeline import IngestionPipeline
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.models.snapshot import RepositoryIngestionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

def parse_github_url(url: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' shorthand.

    Supported formats:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        https://github.com/owner/repo/
        git@github.com:owner/repo.git
        owner/repo
    """
    url = url.strip().rstrip("/")

    # SSH format
    ssh_match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS format
    https_match = re.match(
        r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$", url
    )
    if https_match:
        return https_match.group(1), https_match.group(2)

    # owner/repo shorthand
    slash_match = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", url)
    if slash_match:
        return slash_match.group(1), slash_match.group(2)

    raise ValueError(
        f"Cannot parse GitHub repository URL: '{url}'. "
        "Expected format: https://github.com/owner/repo"
    )


# ---------------------------------------------------------------------------
# Temporary workspace context manager
# ---------------------------------------------------------------------------

@contextmanager
def temporary_repository_workspace(
    label: str = "ame-analysis",
) -> Generator[Path, None, None]:
    """Create a unique temporary directory inside the OS temp area.

    The directory is unconditionally removed on exit — even when an exception
    is raised inside the ``with`` block.
    """
    analysis_id = uuid.uuid4().hex[:12]
    workspace = Path(tempfile.mkdtemp(prefix=f"{label}-{analysis_id}-"))
    logger.info("Temporary workspace created: %s", workspace)
    try:
        yield workspace
    finally:
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
            logger.info("Temporary workspace deleted: %s", workspace)


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------

ProgressCallback = Optional[Callable[[str, Dict[str, Any]], None]]


# ---------------------------------------------------------------------------
# GitHubConnector
# ---------------------------------------------------------------------------

class GitHubConnector(BaseIngestionSource):
    """Ingests remote GitHub repositories via temporary shallow clone.

    Lifecycle:
        1.  Create temp workspace in OS temp dir.
        2.  Shallow-clone repository into workspace.
        3.  Analyze (parse, infer, build graph).
        4.  Persist graph metadata to SQLite/NetworkX.
        5.  Delete temp workspace (always, even on failure).
    """

    def __init__(
        self,
        store: Optional[EmbeddedGraphStore] = None,
        pipeline: Optional[IngestionPipeline] = None,
    ):
        self.store = store or EmbeddedGraphStore()
        self.pipeline = pipeline or IngestionPipeline()
        self.local_ingestion = LocalGitIngestion()

    # ------------------------------------------------------------------
    # BaseIngestionSource interface (kept for backward compatibility)
    # ------------------------------------------------------------------

    def ingest(
        self,
        target: str,
        repo_id: Optional[str] = None,
        branch: Optional[str] = None,
        **kwargs,
    ) -> NormalizedRepo:
        """Ingest a GitHub URL or owner/repo into a NormalizedRepo.

        The temporary workspace is created, used for analysis, then deleted.
        """
        result = self.ingest_github_repository(
            repo_url=target,
            branch=branch,
            access_token=kwargs.get("access_token"),
            progress_callback=kwargs.get("progress_callback"),
        )
        # Return the NormalizedRepo that was built during ingestion
        return result._norm_repo  # attached during processing

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def ingest_github_repository(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        commit_sha: Optional[str] = None,
        access_token: Optional[str] = None,
        progress_callback: ProgressCallback = None,
    ) -> RepositoryIngestionResult:
        """Full pipeline: clone → analyze → persist graph → delete clone.

        Returns a ``RepositoryIngestionResult`` with graph statistics.
        The temporary workspace is *always* removed — even on failure.
        """
        owner, repo_name = parse_github_url(repo_url)
        r_id = f"github-{owner}-{repo_name}".lower()

        def _progress(stage: str, data: Optional[Dict[str, Any]] = None):
            if progress_callback:
                progress_callback(stage, data or {})

        _progress("resolving", {"owner": owner, "repo": repo_name})

        # Build the clone URL (with embedded token for private repos)
        clone_url = self._build_clone_url(owner, repo_name, access_token)

        with temporary_repository_workspace(label="ame") as workspace:
            clone_dir = workspace / repo_name

            # --- Stage 1: Clone -------------------------------------------
            _progress("cloning", {"url": f"https://github.com/{owner}/{repo_name}"})
            self._shallow_clone(clone_url, clone_dir, branch)

            # --- Stage 2: Resolve metadata --------------------------------
            _progress("metadata", {})
            resolved_branch = branch or self._detect_branch(clone_dir)
            resolved_commit = commit_sha or self._detect_commit(clone_dir)

            # --- Stage 3: Scan & parse ------------------------------------
            _progress("scanning", {})
            norm_repo = self.local_ingestion.ingest(
                target=str(clone_dir),
                repo_id=r_id,
            )
            # Override branch / commit from actual Git state
            norm_repo.branch = resolved_branch
            norm_repo.commit_id = resolved_commit
            norm_repo.snapshot.branch = resolved_branch
            norm_repo.snapshot.commit_id = resolved_commit
            norm_repo.snapshot.metadata["github_owner"] = owner
            norm_repo.snapshot.metadata["github_repo"] = repo_name
            norm_repo.snapshot.metadata["source_url"] = f"https://github.com/{owner}/{repo_name}"
            norm_repo.snapshot.metadata["storage_mode"] = "temporary_workspace_deleted"

            files_discovered = len(norm_repo.files)

            _progress("parsing", {"files_discovered": files_discovered})

            # Detect languages present
            extensions: Dict[str, int] = {}
            for fpath in norm_repo.files:
                ext = Path(fpath).suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1
            lang_map = {".java": "Java", ".py": "Python", ".js": "JavaScript",
                        ".ts": "TypeScript", ".go": "Go", ".rs": "Rust",
                        ".kt": "Kotlin", ".scala": "Scala", ".rb": "Ruby",
                        ".sql": "SQL", ".yaml": "YAML", ".yml": "YAML",
                        ".xml": "XML", ".json": "JSON"}
            languages = sorted({lang_map.get(ext, ext) for ext in extensions})

            _progress("analyzing", {"files_analyzed": files_discovered, "languages": languages})

            # --- Stage 4: Build graph -------------------------------------
            _progress("building_graph", {})
            nodes, edges = self.pipeline.process(norm_repo)

            # --- Stage 5: Persist graph metadata --------------------------
            _progress("persisting", {"nodes": len(nodes), "edges": len(edges)})
            self.store.save_snapshot(norm_repo.snapshot, nodes, edges)

            # Compute entity counts for the summary
            entity_counts: Dict[str, int] = {}
            for n in nodes:
                et = n.entity_type.value
                entity_counts[et] = entity_counts.get(et, 0) + 1

            # Build architecture summary
            summary = {
                "entity_counts": entity_counts,
                "languages": languages,
                "total_files_discovered": files_discovered,
                "total_files_analyzed": files_discovered,
                "owner": owner,
                "repo_name": repo_name,
            }

            result = RepositoryIngestionResult(
                repo_id=r_id,
                snapshot_id=norm_repo.snapshot.snapshot_id,
                commit_id=resolved_commit,
                branch=resolved_branch,
                files_analyzed=files_discovered,
                nodes_created=len(nodes),
                edges_created=len(edges),
                languages=languages,
                status="completed",
                storage_mode="temporary_workspace_deleted",
                architecture_summary=summary,
            )
            # Attach NormalizedRepo for backward-compatible ingest() call
            result._norm_repo = norm_repo  # type: ignore[attr-defined]

        # -- workspace is now deleted --
        _progress("cleanup_complete", {})
        _progress("complete", {
            "repo_id": r_id,
            "snapshot_id": result.snapshot_id,
            "nodes": result.nodes_created,
            "edges": result.edges_created,
        })
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_clone_url(owner: str, repo: str, token: Optional[str]) -> str:
        if token:
            return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        return f"https://github.com/{owner}/{repo}.git"

    @staticmethod
    def _shallow_clone(url: str, dest: Path, branch: Optional[str] = None) -> None:
        cmd: List[str] = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([url, str(dest)])
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            # Sanitize: never expose the token in error messages
            safe_err = re.sub(r"x-access-token:[^@]+@", "x-access-token:***@", res.stderr)
            raise RuntimeError(f"Failed to clone repository: {safe_err.strip()}")

    @staticmethod
    def _detect_branch(repo_dir: Path) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(repo_dir), capture_output=True, text=True, check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _detect_commit(repo_dir: Path) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_dir), capture_output=True, text=True, check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None
