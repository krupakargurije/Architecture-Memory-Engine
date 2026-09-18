"""Tests for GitHub remote ingestion with temporary workspace lifecycle.
Verifies URL parsing, temporary workspace creation/deletion, graph persistence,
and failure cleanup.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ame.ingestion.github_connector import (
    GitHubConnector,
    parse_github_url,
    temporary_repository_workspace,
)
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.ingestion.pipeline import IngestionPipeline


# ═══════════════════════════════════════════════════════════════════════════
# URL Parsing
# ═══════════════════════════════════════════════════════════════════════════

class TestParseGitHubUrl:
    def test_https_standard(self):
        assert parse_github_url("https://github.com/spring-projects/spring-boot") == ("spring-projects", "spring-boot")

    def test_https_with_git_suffix(self):
        assert parse_github_url("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_https_trailing_slash(self):
        assert parse_github_url("https://github.com/owner/repo/") == ("owner", "repo")

    def test_ssh_format(self):
        assert parse_github_url("git@github.com:owner/repo.git") == ("owner", "repo")

    def test_shorthand(self):
        assert parse_github_url("owner/repo") == ("owner", "repo")

    def test_shorthand_with_git(self):
        assert parse_github_url("owner/repo.git") == ("owner", "repo")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("not-a-valid-url")

    def test_whitespace_stripped(self):
        assert parse_github_url("  https://github.com/a/b  ") == ("a", "b")


# ═══════════════════════════════════════════════════════════════════════════
# Temporary Workspace Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestTemporaryWorkspace:
    def test_workspace_created_and_deleted(self):
        workspace_path = None
        with temporary_repository_workspace(label="test") as ws:
            workspace_path = ws
            assert ws.exists(), "Workspace must exist during the with block"
            assert str(ws).startswith(tempfile.gettempdir().rstrip("\\").rstrip("/")), \
                "Workspace must be inside OS temp directory"
        assert not workspace_path.exists(), "Workspace must be deleted after exiting with block"

    def test_workspace_deleted_on_exception(self):
        workspace_path = None
        with pytest.raises(RuntimeError):
            with temporary_repository_workspace(label="test-fail") as ws:
                workspace_path = ws
                assert ws.exists()
                raise RuntimeError("simulated analysis failure")
        assert not workspace_path.exists(), "Workspace must be deleted even when exception occurs"

    def test_workspace_has_unique_id(self):
        paths = []
        for _ in range(3):
            with temporary_repository_workspace(label="test") as ws:
                paths.append(str(ws))
        assert len(set(paths)) == 3, "Each workspace must have a unique path"


# ═══════════════════════════════════════════════════════════════════════════
# GitHubConnector — Integration with local sample repo
# ═══════════════════════════════════════════════════════════════════════════

class TestGitHubConnectorLocalMode:
    """Tests GitHubConnector using the local ecommerce_java sample
    by mocking the shallow clone to copy files locally instead of
    hitting GitHub over the network.
    """

    @pytest.fixture
    def sample_repo_dir(self):
        return Path(__file__).resolve().parent.parent / "samples" / "ecommerce_java"

    @pytest.fixture
    def store(self, tmp_path):
        return EmbeddedGraphStore(tmp_path / "test_github.db")

    def test_full_ingestion_with_mocked_clone(self, sample_repo_dir, store, tmp_path):
        """Simulate the full pipeline: clone → analyze → persist → cleanup."""
        import shutil

        connector = GitHubConnector(store=store, pipeline=IngestionPipeline())

        # Mock _shallow_clone to copy from local sample instead of git clone
        def mock_shallow_clone(url, dest, branch=None):
            shutil.copytree(str(sample_repo_dir), str(dest))

        with patch.object(GitHubConnector, '_shallow_clone', staticmethod(mock_shallow_clone)):
            result = connector.ingest_github_repository(
                repo_url="https://github.com/example/ecommerce-java",
                branch="main",
            )

        # Verify result
        assert result.status == "completed"
        assert result.repo_id == "github-example-ecommerce-java"
        assert result.storage_mode == "temporary_workspace_deleted"
        assert result.files_analyzed > 0
        assert result.nodes_created > 0
        assert result.edges_created > 0
        assert "Java" in result.languages

        # Verify graph was persisted
        nodes = store.get_nodes(result.snapshot_id)
        edges = store.get_edges(result.snapshot_id)
        assert len(nodes) > 0
        assert len(edges) > 0

        # Verify architectural structure: Controller -> Service -> Repository -> Entity
        node_names = {n.name for n in nodes}
        assert "OrderController" in node_names
        assert "OrderService" in node_names
        assert "DiscountService" in node_names

        # Verify entity types
        node_types = {n.name: n.entity_type.value for n in nodes}
        assert node_types["OrderController"] == "controller"
        assert node_types["OrderService"] == "service"

    def test_temporary_workspace_not_left_behind(self, sample_repo_dir, store):
        """Verify that no temporary workspace directory remains after ingestion."""
        import shutil, os

        connector = GitHubConnector(store=store, pipeline=IngestionPipeline())
        temp_dir_before = set(os.listdir(tempfile.gettempdir()))

        def mock_shallow_clone(url, dest, branch=None):
            shutil.copytree(str(sample_repo_dir), str(dest))

        with patch.object(GitHubConnector, '_shallow_clone', staticmethod(mock_shallow_clone)):
            result = connector.ingest_github_repository(
                repo_url="https://github.com/test/repo",
            )

        temp_dir_after = set(os.listdir(tempfile.gettempdir()))
        # Any new ame-* directories should have been cleaned up
        new_dirs = temp_dir_after - temp_dir_before
        ame_dirs = [d for d in new_dirs if d.startswith("ame-")]
        assert len(ame_dirs) == 0, f"Temporary workspace directories not cleaned up: {ame_dirs}"

    def test_cleanup_on_failure(self, store):
        """Verify temporary workspace is deleted even when clone fails."""
        connector = GitHubConnector(store=store, pipeline=IngestionPipeline())

        def mock_clone_fail(url, dest, branch=None):
            raise RuntimeError("Clone failed: network error")

        with patch.object(GitHubConnector, '_shallow_clone', staticmethod(mock_clone_fail)):
            with pytest.raises(RuntimeError, match="Clone failed"):
                connector.ingest_github_repository(
                    repo_url="https://github.com/fail/repo",
                )

    def test_snapshot_metadata_correct(self, sample_repo_dir, store):
        """Verify snapshot contains github metadata and storage mode."""
        import shutil

        connector = GitHubConnector(store=store, pipeline=IngestionPipeline())

        def mock_clone(url, dest, branch=None):
            shutil.copytree(str(sample_repo_dir), str(dest))

        with patch.object(GitHubConnector, '_shallow_clone', staticmethod(mock_clone)):
            result = connector.ingest_github_repository(
                repo_url="https://github.com/test/myproject",
                branch="develop",
            )

        snapshot = store.get_snapshot(result.snapshot_id)
        assert snapshot is not None
        assert snapshot.metadata.get("github_owner") == "test"
        assert snapshot.metadata.get("github_repo") == "myproject"
        assert snapshot.metadata.get("storage_mode") == "temporary_workspace_deleted"
        assert snapshot.metadata.get("source_url") == "https://github.com/test/myproject"
