"""Graph traversal and call-chain tracer for Architecture Memory Engine.
Traverses architectural relationships bidirectionally to extract connected subgraphs.
"""

from typing import Dict, List, Optional, Set, Tuple
import networkx as nx

from ame.models.schema import Edge, RelationType, SourceType


class GraphTraversal:
    """Performs graph expansions, dependency tracing, and pathfinding on knowledge graphs."""

    def expand_subgraph(
        self,
        graph: nx.MultiDiGraph,
        seed_node_ids: List[str],
        max_depth: int = 2,
    ) -> Tuple[Set[str], List[Edge]]:
        """
        Expands outward from seed nodes up to max_depth hops along both incoming and outgoing edges.
        Returns (set of connected node IDs, list of connecting Edge objects).
        """
        visited_nodes: Set[str] = set()
        subgraph_edges: List[Edge] = []
        edge_keys_seen: Set[Tuple[str, str, str]] = set()

        current_frontier = set(seed_node_ids).intersection(graph.nodes())
        visited_nodes.update(current_frontier)

        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for node in current_frontier:
                # Outgoing edges (downstream dependencies, callees)
                for _, neighbor, key, data in graph.out_edges(node, data=True, keys=True):
                    visited_nodes.add(neighbor)
                    next_frontier.add(neighbor)
                    k = (node, neighbor, key)
                    if k not in edge_keys_seen:
                        edge_keys_seen.add(k)
                        subgraph_edges.append(self._edge_from_data(node, neighbor, data))

                # Incoming edges (upstream callers, tests targeting component)
                for neighbor, _, key, data in graph.in_edges(node, data=True, keys=True):
                    visited_nodes.add(neighbor)
                    next_frontier.add(neighbor)
                    k = (neighbor, node, key)
                    if k not in edge_keys_seen:
                        edge_keys_seen.add(k)
                        subgraph_edges.append(self._edge_from_data(neighbor, node, data))

            current_frontier = next_frontier - visited_nodes
            if not current_frontier:
                break

        return visited_nodes, subgraph_edges

    def find_call_chain(
        self, graph: nx.MultiDiGraph, source_id: str, target_id: str
    ) -> Optional[List[str]]:
        """
        Finds the shortest architectural path from source to target.
        """
        if source_id not in graph or target_id not in graph:
            return None

        try:
            # First try directed path
            path = nx.shortest_path(graph, source=source_id, target=target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        try:
            # Fall back to undirected path
            undirected = graph.to_undirected(as_view=True)
            path = nx.shortest_path(undirected, source=source_id, target=target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def _edge_from_data(self, source: str, target: str, data: dict) -> Edge:
        return Edge(
            source=source,
            target=target,
            relation=RelationType(data.get("relation", "DEPENDS_ON")),
            confidence=float(data.get("confidence", 1.0)),
            source_type=SourceType(data.get("source_type", "static_analysis")),
            metadata=data.get("metadata", {}),
        )
