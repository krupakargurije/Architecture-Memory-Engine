"""Embedded SQLite + NetworkX persistent graph store for Architecture Memory Engine.
Provides zero-setup, zero-daemon graph persistence with snapshot isolation and fast in-memory graph traversals.
"""

import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
import networkx as nx

from ame.config import settings
from ame.graph.base import BaseGraphStore
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.models.snapshot import Repository, RepositorySnapshot, SnapshotType, UncommittedChange


class EmbeddedGraphStore(BaseGraphStore):
    """SQLite-backed persistent graph store with in-memory NetworkX MultiDiGraph caching."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path(settings.data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / settings.db_filename
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._graph_cache: Dict[str, nx.MultiDiGraph] = {}
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS repositories (
                    repo_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_url_or_path TEXT NOT NULL,
                    default_branch TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    commit_id TEXT,
                    branch TEXT,
                    workspace_id TEXT,
                    timestamp REAL NOT NULL,
                    uncommitted_changes_json TEXT,
                    metadata_json TEXT,
                    FOREIGN KEY (repo_id) REFERENCES repositories(repo_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    snapshot_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    file_path TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    signature TEXT,
                    docstring TEXT,
                    metadata_json TEXT,
                    PRIMARY KEY (snapshot_id, node_id),
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS edges (
                    snapshot_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_type TEXT NOT NULL,
                    metadata_json TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_repo ON snapshots(repo_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(snapshot_id, entity_type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(snapshot_id, name);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(snapshot_id, source);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(snapshot_id, target);
            """)

    def save_repository(self, repository: Repository) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO repositories (repo_id, name, source_url_or_path, default_branch, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(repo_id) DO UPDATE SET
                    name = excluded.name,
                    source_url_or_path = excluded.source_url_or_path,
                    default_branch = excluded.default_branch
                """,
                (
                    repository.repo_id,
                    repository.name,
                    repository.source_url_or_path,
                    repository.default_branch,
                    repository.created_at,
                )
            )

    def get_repository(self, repo_id: str) -> Optional[Repository]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM repositories WHERE repo_id = ?", (repo_id,)).fetchone()
            if not row:
                return None
            snaps = [
                r["snapshot_id"]
                for r in conn.execute(
                    "SELECT snapshot_id FROM snapshots WHERE repo_id = ? ORDER BY timestamp DESC", (repo_id,)
                ).fetchall()
            ]
            return Repository(
                repo_id=row["repo_id"],
                name=row["name"],
                source_url_or_path=row["source_url_or_path"],
                default_branch=row["default_branch"],
                created_at=row["created_at"],
                snapshots=snaps,
            )

    def list_repositories(self) -> List[Repository]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM repositories ORDER BY created_at DESC").fetchall()
            return [
                Repository(
                    repo_id=r["repo_id"],
                    name=r["name"],
                    source_url_or_path=r["source_url_or_path"],
                    default_branch=r["default_branch"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def save_snapshot(
        self,
        snapshot: RepositorySnapshot,
        nodes: List[Node],
        edges: List[Edge],
    ) -> None:
        uncommitted_dict = {
            k: v.model_dump() for k, v in snapshot.uncommitted_changes.items()
        }

        with self._get_connection() as conn:
            # Ensure parent repo exists in DB
            conn.execute(
                """
                INSERT OR IGNORE INTO repositories (repo_id, name, source_url_or_path, default_branch, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snapshot.repo_id, snapshot.repo_id, "", snapshot.branch or "main", snapshot.timestamp)
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots (
                    snapshot_id, repo_id, snapshot_type, commit_id, branch,
                    workspace_id, timestamp, uncommitted_changes_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.repo_id,
                    snapshot.snapshot_type.value,
                    snapshot.commit_id,
                    snapshot.branch,
                    snapshot.workspace_id,
                    snapshot.timestamp,
                    json.dumps(uncommitted_dict),
                    json.dumps(snapshot.metadata),
                )
            )

            # Insert nodes
            node_params = [
                (
                    snapshot.snapshot_id,
                    n.id,
                    n.name,
                    n.entity_type.value,
                    n.file_path,
                    n.start_line,
                    n.end_line,
                    n.signature,
                    n.docstring,
                    json.dumps(n.metadata),
                )
                for n in nodes
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO nodes (
                    snapshot_id, node_id, name, entity_type, file_path,
                    start_line, end_line, signature, docstring, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                node_params
            )

            # Insert edges
            edge_params = [
                (
                    snapshot.snapshot_id,
                    e.source,
                    e.target,
                    e.relation.value,
                    e.confidence,
                    e.source_type.value,
                    json.dumps(e.metadata),
                )
                for e in edges
            ]
            conn.executemany(
                """
                INSERT INTO edges (
                    snapshot_id, source, target, relation, confidence, source_type, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                edge_params
            )

        # Invalidate/update cache
        self._build_nx_graph(snapshot.snapshot_id, nodes, edges)

    def get_snapshot(self, snapshot_id: str) -> Optional[RepositorySnapshot]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
            if not row:
                return None
            uncommitted_raw = json.loads(row["uncommitted_changes_json"] or "{}")
            uncommitted_map = {k: UncommittedChange(**v) for k, v in uncommitted_raw.items()}
            return RepositorySnapshot(
                snapshot_id=row["snapshot_id"],
                repo_id=row["repo_id"],
                snapshot_type=SnapshotType(row["snapshot_type"]),
                commit_id=row["commit_id"],
                branch=row["branch"],
                workspace_id=row["workspace_id"],
                timestamp=row["timestamp"],
                uncommitted_changes=uncommitted_map,
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def get_latest_snapshot(self, repo_id: str) -> Optional[RepositorySnapshot]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE repo_id = ? ORDER BY timestamp DESC LIMIT 1", (repo_id,)
            ).fetchone()
            if not row:
                return None
            uncommitted_raw = json.loads(row["uncommitted_changes_json"] or "{}")
            uncommitted_map = {k: UncommittedChange(**v) for k, v in uncommitted_raw.items()}
            return RepositorySnapshot(
                snapshot_id=row["snapshot_id"],
                repo_id=row["repo_id"],
                snapshot_type=SnapshotType(row["snapshot_type"]),
                commit_id=row["commit_id"],
                branch=row["branch"],
                workspace_id=row["workspace_id"],
                timestamp=row["timestamp"],
                uncommitted_changes=uncommitted_map,
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def get_nodes(self, snapshot_id: str, entity_type: Optional[EntityType] = None) -> List[Node]:
        with self._get_connection() as conn:
            if entity_type:
                query = "SELECT * FROM nodes WHERE snapshot_id = ? AND entity_type = ?"
                rows = conn.execute(query, (snapshot_id, entity_type.value)).fetchall()
            else:
                query = "SELECT * FROM nodes WHERE snapshot_id = ?"
                rows = conn.execute(query, (snapshot_id,)).fetchall()

            return [
                Node(
                    id=r["node_id"],
                    name=r["name"],
                    entity_type=EntityType(r["entity_type"]),
                    file_path=r["file_path"],
                    start_line=r["start_line"],
                    end_line=r["end_line"],
                    signature=r["signature"],
                    docstring=r["docstring"],
                    metadata=json.loads(r["metadata_json"] or "{}"),
                )
                for r in rows
            ]

    def get_node(self, snapshot_id: str, node_id: str) -> Optional[Node]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM nodes WHERE snapshot_id = ? AND node_id = ?", (snapshot_id, node_id)
            ).fetchone()
            if not row:
                return None
            return Node(
                id=row["node_id"],
                name=row["name"],
                entity_type=EntityType(row["entity_type"]),
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                signature=row["signature"],
                docstring=row["docstring"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def get_edges(self, snapshot_id: str) -> List[Edge]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM edges WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
            return [
                Edge(
                    source=r["source"],
                    target=r["target"],
                    relation=RelationType(r["relation"]),
                    confidence=r["confidence"],
                    source_type=SourceType(r["source_type"]),
                    metadata=json.loads(r["metadata_json"] or "{}"),
                )
                for r in rows
            ]

    def get_graph(self, snapshot_id: str) -> nx.MultiDiGraph:
        if snapshot_id in self._graph_cache:
            return self._graph_cache[snapshot_id]

        nodes = self.get_nodes(snapshot_id)
        edges = self.get_edges(snapshot_id)
        return self._build_nx_graph(snapshot_id, nodes, edges)

    def _build_nx_graph(
        self, snapshot_id: str, nodes: List[Node], edges: List[Edge]
    ) -> nx.MultiDiGraph:
        G = nx.MultiDiGraph()
        for n in nodes:
            G.add_node(n.id, **n.model_dump())

        for e in edges:
            G.add_edge(e.source, e.target, key=e.relation.value, **e.model_dump())

        self._graph_cache[snapshot_id] = G
        return G
