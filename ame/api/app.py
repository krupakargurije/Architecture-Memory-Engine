"""FastAPI REST API server for Architecture Memory Engine.
Exposes REST endpoints for ingestion, graph exploration, retrieval, and impact analysis.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ame.graph.embedded_store import EmbeddedGraphStore
from ame.ingestion.github_connector import GitHubConnector, parse_github_url
from ame.ingestion.local_git import LocalGitIngestion
from ame.ingestion.pipeline import IngestionPipeline
from ame.mcp.tools import AMEMCPTools
from ame.models.snapshot import RepositorySnapshot
from ame.retrieval.summarizer import ArchitectureSummarizer

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Architecture Memory Engine (AME) API",
    description="Persistent Architectural Memory Layer for AI Coding Agents",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = EmbeddedGraphStore()
tools = AMEMCPTools(store)
ingestion_pipeline = IngestionPipeline()
local_ingestion = LocalGitIngestion()
github_connector = GitHubConnector(store=store, pipeline=ingestion_pipeline)
summarizer = ArchitectureSummarizer(store)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    path: str
    repo_id: Optional[str] = None
    workspace_id: Optional[str] = None


class GitHubIngestRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = None
    access_token: Optional[str] = None


class RetrieveRequest(BaseModel):
    task: str
    repo_id: str
    snapshot_id: Optional[str] = None
    token_budget: Optional[int] = 8000


class WorkspaceUpdateRequest(BaseModel):
    repo_id: str
    uncommitted_files: Dict[str, str]
    base_snapshot_id: Optional[str] = None
    workspace_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "AME Architecture Memory Engine"}


# ---------------------------------------------------------------------------
# Default repository (ecommerce_java)
# ---------------------------------------------------------------------------

def ensure_default_repository() -> Dict[str, Any]:
    """Ensures the default/sample repository (ecommerce_java) is ingested and available."""
    repo_id = "ecommerce_java"
    latest = store.get_latest_snapshot(repo_id)
    sample_dir = Path(__file__).resolve().parent.parent.parent / "samples" / "ecommerce_java"

    if not latest or len(store.get_nodes(latest.snapshot_id)) == 0:
        if sample_dir.exists():
            norm_repo = local_ingestion.ingest(str(sample_dir), repo_id=repo_id)
            nodes, edges = ingestion_pipeline.process(norm_repo)
            store.save_snapshot(norm_repo.snapshot, nodes, edges)
            latest = norm_repo.snapshot
            logger.info("Default repository ecommerce_java ingested: %d nodes, %d edges", len(nodes), len(edges))

    if not latest:
        raise HTTPException(status_code=404, detail="Default repository not found")

    nodes = store.get_nodes(latest.snapshot_id)
    edges = store.get_edges(latest.snapshot_id)
    arch_summary = summarizer.summarize(latest.snapshot_id)

    return {
        "status": "success",
        "repo_id": repo_id,
        "name": "ecommerce_java",
        "owner": "samples",
        "repo_name": "ecommerce_java",
        "snapshot_id": latest.snapshot_id,
        "commit_id": latest.commit_id or "c0ffee1",
        "branch": latest.branch or "main",
        "language": "Java",
        "languages": ["Java"],
        "nodes": len(nodes),
        "edges": len(edges),
        "nodes_created": len(nodes),
        "edges_created": len(edges),
        "source_type": "default",
        "architecture_summary": arch_summary,
    }


@app.get("/api/default-repository")
def get_default_repository():
    """Returns the default repository metadata, snapshot, and architecture summary."""
    try:
        return ensure_default_repository()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

@app.get("/api/repositories")
def list_repositories():
    return store.list_repositories()


# ---------------------------------------------------------------------------
# Local ingestion
# ---------------------------------------------------------------------------

@app.post("/api/ingest")
def ingest_repository(req: IngestRequest):
    try:
        norm_repo = local_ingestion.ingest(
            target=req.path,
            repo_id=req.repo_id,
            workspace_id=req.workspace_id,
        )
        nodes, edges = ingestion_pipeline.process(norm_repo)
        store.save_snapshot(norm_repo.snapshot, nodes, edges)

        return {
            "status": "success",
            "repo_id": norm_repo.repo_id,
            "snapshot_id": norm_repo.snapshot.snapshot_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "is_dirty": norm_repo.snapshot.is_dirty,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# GitHub remote ingestion (temporary workspace)
# ---------------------------------------------------------------------------

@app.post("/api/github/ingest")
@app.post("/github/ingest")
def github_ingest(req: GitHubIngestRequest):
    """Temporarily clone a GitHub repository, analyze its architecture,
    persist graph metadata, then delete the temporary workspace.
    """
    try:
        # Validate URL up-front to give a fast, clear error
        owner, repo_name = parse_github_url(req.repo_url)

        result = github_connector.ingest_github_repository(
            repo_url=req.repo_url,
            branch=req.branch,
            access_token=req.access_token,
        )

        # Build architecture summary
        arch_summary = summarizer.summarize(result.snapshot_id)

        return {
            "status": result.status,
            "repo_id": result.repo_id,
            "snapshot_id": result.snapshot_id,
            "commit_id": result.commit_id,
            "branch": result.branch,
            "files_analyzed": result.files_analyzed,
            "nodes_created": result.nodes_created,
            "edges_created": result.edges_created,
            "languages": result.languages,
            "storage_mode": result.storage_mode,
            "architecture_summary": arch_summary,
            "owner": owner,
            "repo_name": repo_name,
            "source_type": "github",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("GitHub ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Architecture summary
# ---------------------------------------------------------------------------

@app.get("/api/architecture-summary/{snapshot_id}")
def get_architecture_summary(snapshot_id: str):
    try:
        return summarizer.summarize(snapshot_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Graph data
# ---------------------------------------------------------------------------

@app.get("/api/graph/{snapshot_id}")
def get_graph_data(snapshot_id: str):
    nodes = store.get_nodes(snapshot_id)
    edges = store.get_edges(snapshot_id)
    if not nodes:
        raise HTTPException(status_code=404, detail="Snapshot not found or empty")

    return {
        "snapshot_id": snapshot_id,
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


# ---------------------------------------------------------------------------
# Context retrieval
# ---------------------------------------------------------------------------

@app.post("/api/retrieve")
def retrieve_context(req: RetrieveRequest):
    try:
        sample_dir = Path(__file__).resolve().parent.parent.parent / "samples" / "ecommerce_java"
        repo_root = str(sample_dir) if req.repo_id == "ecommerce_java" and sample_dir.exists() else None
        return tools.retrieve_context(
            task=req.task,
            repo_id=req.repo_id,
            snapshot_id=req.snapshot_id,
            token_budget=req.token_budget or 8000,
            repo_root=repo_root,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Impact analysis
# ---------------------------------------------------------------------------

@app.get("/api/impact/{repo_id}/{component_name}")
def analyze_impact(repo_id: str, component_name: str, snapshot_id: Optional[str] = None):
    try:
        return tools.find_impact(component_name, repo_id, snapshot_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Call chain
# ---------------------------------------------------------------------------

@app.get("/api/call-chain/{repo_id}")
def find_call_chain(repo_id: str, source: str, target: str, snapshot_id: Optional[str] = None):
    return tools.find_call_chain(source, target, repo_id, snapshot_id)


# ---------------------------------------------------------------------------
# Workspace snapshot
# ---------------------------------------------------------------------------

@app.post("/api/workspace-snapshot")
def update_workspace_snapshot(req: WorkspaceUpdateRequest):
    try:
        return tools.create_workspace_snapshot(
            repo_id=req.repo_id,
            uncommitted_files=req.uncommitted_files,
            base_snapshot_id=req.base_snapshot_id,
            workspace_id=req.workspace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


def main():
    import uvicorn
    uvicorn.run("ame.api.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
