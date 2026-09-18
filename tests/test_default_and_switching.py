"""Tests for Default Repository loading and repository switching behavior in AME.
Verifies:
1. Default repository auto-ingestion and snapshot metadata (44 nodes, 59 edges).
2. GET /api/default-repository endpoint response contract.
3. Graph retrieval for default repository snapshot.
4. Task context retrieval for default repository.
5. Ingestion failure safety: failed ingestion attempts preserve the current repository intact.
6. Switching between default repository and external candidate graphs.
"""

from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import HTTPException

from ame.api.app import (
    ensure_default_repository,
    get_default_repository,
    get_graph_data,
    retrieve_context,
    github_ingest,
    RetrieveRequest,
    GitHubIngestRequest,
    store,
)


def test_default_repository_data():
    """Verifies that ensure_default_repository yields ecommerce_java with 44 nodes and 59 edges."""
    data = ensure_default_repository()
    assert data["name"] == "ecommerce_java"
    assert data["repo_id"] == "ecommerce_java"
    assert data["source_type"] == "default"
    assert data["nodes"] == 44
    assert data["edges"] == 59
    assert data["snapshot_id"].startswith("snap-")
    assert "Java" in data["languages"]
    assert "entity_counts" in data["architecture_summary"]
    assert data["architecture_summary"]["entity_counts"]["controller"] == 2
    assert data["architecture_summary"]["entity_counts"]["service"] == 6


def test_get_default_repository_endpoint():
    """Verifies the get_default_repository endpoint contract."""
    data = get_default_repository()
    assert data["status"] == "success"
    assert data["name"] == "ecommerce_java"
    assert data["nodes"] == 44
    assert data["edges"] == 59
    assert data["source_type"] == "default"
    assert data["snapshot_id"].startswith("snap-")


def test_graph_data_for_default_repository():
    """Verifies that the graph for the default snapshot contains all 44 nodes & 59 edges."""
    default_data = get_default_repository()
    snap_id = default_data["snapshot_id"]

    graph = get_graph_data(snap_id)
    assert len(graph["nodes"]) == 44
    assert len(graph["edges"]) == 59

    node_names = {n["name"] for n in graph["nodes"]}
    assert "OrderController" in node_names
    assert "OrderService" in node_names
    assert "DiscountService" in node_names
    assert "OrderRepository" in node_names
    assert "Order" in node_names
    assert "PricingController" in node_names
    assert "PricingService" in node_names
    assert "Product" in node_names


def test_task_retrieval_on_default_repository():
    """Verifies task context retrieval against the default repository."""
    default_data = get_default_repository()
    snap_id = default_data["snapshot_id"]

    req = RetrieveRequest(
        task="Introduce a discount validation step before creating an order",
        repo_id="ecommerce_java",
        snapshot_id=snap_id,
        token_budget=8000,
    )
    pkg = retrieve_context(req)

    assert pkg["total_tokens"] > 0
    assert pkg["total_tokens"] <= 8000
    assert pkg["token_savings_percentage"] > 0
    assert len(pkg["snippets"]) > 0

    snippet_names = {s["name"] for s in pkg["snippets"]}
    assert "OrderService" in snippet_names or "DiscountService" in snippet_names


def test_ingestion_failure_safety_preserves_default_repository():
    """Verifies that if external ingestion fails, the default repository graph is NOT destroyed."""
    # Ensure default repo exists
    default_before = get_default_repository()
    snap_before = default_before["snapshot_id"]

    # Attempt ingestion with an invalid URL
    bad_req = GitHubIngestRequest(
        repo_url="https://github.com/invalid-nonexistent-user-12345/nonexistent-repo-99999"
    )
    with pytest.raises(HTTPException) as exc_info:
        github_ingest(bad_req)

    assert exc_info.value.status_code in [400, 500, 502]

    # Verify default repository is completely unaffected
    default_after = get_default_repository()
    assert default_after["snapshot_id"] == snap_before
    assert default_after["nodes"] == 44
    assert default_after["edges"] == 59

    # Graph remains fully intact
    graph = get_graph_data(snap_before)
    assert len(graph["nodes"]) == 44
    assert len(graph["edges"]) == 59


def test_repository_switching_isolation():
    """Verifies that switching between repositories maintains clean isolation without mixing nodes."""
    from ame.ingestion.github_connector import GitHubConnector
    import shutil

    default_data = get_default_repository()
    default_snap = default_data["snapshot_id"]

    # Ingest a mocked sample as external repo
    sample_dir = Path(__file__).resolve().parent.parent / "samples" / "ecommerce_java"

    def mock_shallow_clone(url, dest, branch=None):
        shutil.copytree(str(sample_dir), str(dest))

    with patch.object(GitHubConnector, '_shallow_clone', staticmethod(mock_shallow_clone)):
        req = GitHubIngestRequest(
            repo_url="https://github.com/acme/custom-service",
            branch="main",
        )
        ext_result = github_ingest(req)

    assert ext_result["status"] == "completed"
    assert ext_result["source_type"] == "github"
    ext_snap = ext_result["snapshot_id"]
    assert ext_snap != default_snap

    # Nodes of external snapshot
    ext_graph = get_graph_data(ext_snap)
    assert len(ext_graph["nodes"]) > 0

    # Default snapshot is still intact and separate
    def_graph = get_graph_data(default_snap)
    assert len(def_graph["nodes"]) == 44
    assert len(def_graph["edges"]) == 59

