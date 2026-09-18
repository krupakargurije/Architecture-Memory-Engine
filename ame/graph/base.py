"""Abstract graph store interface for Architecture Memory Engine.
Supports persistent storage of versioned architectural graphs with snapshot isolation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import networkx as nx

from ame.models.schema import Edge, EntityType, Node
from ame.models.snapshot import Repository, RepositorySnapshot


class BaseGraphStore(ABC):
    """Abstract interface for storing and querying architectural knowledge graphs."""

    @abstractmethod
    def save_repository(self, repository: Repository) -> None:
        """Register or update a repository record."""
        pass

    @abstractmethod
    def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Fetch repository record by ID."""
        pass

    @abstractmethod
    def list_repositories(self) -> List[Repository]:
        """List all tracked repositories."""
        pass

    @abstractmethod
    def save_snapshot(
        self,
        snapshot: RepositorySnapshot,
        nodes: List[Node],
        edges: List[Edge],
    ) -> None:
        """Persist a repository snapshot along with its full architectural graph."""
        pass

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> Optional[RepositorySnapshot]:
        """Fetch snapshot metadata by snapshot ID."""
        pass

    @abstractmethod
    def get_latest_snapshot(self, repo_id: str) -> Optional[RepositorySnapshot]:
        """Get the most recent snapshot for a given repository."""
        pass

    @abstractmethod
    def get_graph(self, snapshot_id: str) -> nx.MultiDiGraph:
        """Retrieve the NetworkX MultiDiGraph for a specific snapshot."""
        pass

    @abstractmethod
    def get_nodes(
        self, snapshot_id: str, entity_type: Optional[EntityType] = None
    ) -> List[Node]:
        """Query nodes in a snapshot, optionally filtered by EntityType."""
        pass

    @abstractmethod
    def get_node(self, snapshot_id: str, node_id: str) -> Optional[Node]:
        """Fetch single node by ID within a snapshot."""
        pass

    @abstractmethod
    def get_edges(self, snapshot_id: str) -> List[Edge]:
        """Fetch all edges for a snapshot."""
        pass
