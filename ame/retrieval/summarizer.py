"""Deterministic architecture summarizer for Architecture Memory Engine.
Computes structural statistics and primary dependency chains directly from
the graph — no LLM required.
"""

from typing import Any, Dict, List, Set, Tuple

import networkx as nx

from ame.graph.base import BaseGraphStore
from ame.models.schema import EntityType


# Entity types that represent high-level architecture
_LAYER_ORDER = [
    EntityType.CONTROLLER,
    EntityType.API,
    EntityType.SERVICE,
    EntityType.TABLE,
    EntityType.TEST,
    EntityType.INTERFACE,
    EntityType.CLASS,
    EntityType.METHOD,
]


class ArchitectureSummarizer:
    """Builds a deterministic, human-readable summary from graph metadata."""

    def __init__(self, store: BaseGraphStore):
        self.store = store

    def summarize(self, snapshot_id: str) -> Dict[str, Any]:
        nodes = self.store.get_nodes(snapshot_id)
        edges = self.store.get_edges(snapshot_id)
        graph = self.store.get_graph(snapshot_id)

        # --- Entity counts ---
        entity_counts: Dict[str, int] = {}
        for n in nodes:
            et = n.entity_type.value
            entity_counts[et] = entity_counts.get(et, 0) + 1

        # --- Language detection from file paths ---
        extensions: Dict[str, int] = {}
        for n in nodes:
            if n.file_path:
                ext = n.file_path.rsplit(".", 1)[-1].lower() if "." in n.file_path else ""
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1

        lang_map = {
            "java": "Java", "py": "Python", "js": "JavaScript",
            "ts": "TypeScript", "go": "Go", "rs": "Rust",
            "kt": "Kotlin", "scala": "Scala", "rb": "Ruby",
        }
        languages = sorted({lang_map.get(ext, ext.upper()) for ext in extensions if ext in lang_map})

        # --- Primary dependency chains ---
        chains = self._find_primary_chains(graph, nodes)

        # --- Structural health facts ---
        health = self._compute_health(graph, nodes)

        return {
            "entity_counts": entity_counts,
            "languages": languages or ["Unknown"],
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "primary_chains": chains,
            "health": health,
        }

    # ------------------------------------------------------------------
    def _find_primary_chains(
        self, graph: nx.MultiDiGraph, nodes: list, max_chains: int = 8,
    ) -> List[List[str]]:
        """Trace entry-point → service → repository → entity chains."""
        node_map = {n.id: n for n in nodes}
        entry_points = [
            n for n in nodes
            if n.entity_type in (EntityType.CONTROLLER, EntityType.API)
        ]

        chains: List[List[str]] = []
        seen_starts: Set[str] = set()

        for entry in entry_points:
            if entry.id in seen_starts or entry.id not in graph:
                continue
            seen_starts.add(entry.id)

            chain = self._dfs_chain(graph, entry.id, node_map, max_depth=6)
            if len(chain) >= 2:
                chains.append(chain)
            if len(chains) >= max_chains:
                break

        # Also trace from services if we don't have enough entry-point chains
        if len(chains) < 3:
            for n in nodes:
                if n.entity_type == EntityType.SERVICE and n.id not in seen_starts:
                    if n.id in graph:
                        chain = self._dfs_chain(graph, n.id, node_map, max_depth=4)
                        if len(chain) >= 2:
                            chains.append(chain)
                        if len(chains) >= max_chains:
                            break

        return chains

    def _dfs_chain(
        self, graph: nx.MultiDiGraph, start: str, node_map: dict, max_depth: int,
    ) -> List[str]:
        """Simple DFS following outgoing edges, preferring high-level nodes."""
        visited: Set[str] = set()
        chain: List[str] = []

        current = start
        for _ in range(max_depth):
            if current in visited or current not in graph:
                break
            visited.add(current)

            node = node_map.get(current)
            if node and node.entity_type != EntityType.METHOD:
                chain.append(node.name)

            # Pick the "most architectural" successor
            successors = list(graph.successors(current))
            best = None
            best_priority = 999
            for s in successors:
                if s in visited:
                    continue
                s_node = node_map.get(s)
                if not s_node:
                    continue
                try:
                    prio = _LAYER_ORDER.index(s_node.entity_type)
                except ValueError:
                    prio = 50
                if s_node.entity_type == EntityType.METHOD:
                    prio = 100  # deprioritize methods
                if prio < best_priority:
                    best_priority = prio
                    best = s

            if best is None:
                break
            current = best

        return chain

    # ------------------------------------------------------------------
    def _compute_health(self, graph: nx.MultiDiGraph, nodes: list) -> Dict[str, Any]:
        """Factual structural statistics — no subjective judgments."""
        node_map = {n.id: n for n in nodes}

        # Most connected (by total degree)
        degree_list: List[Tuple[str, int]] = []
        for nid in graph.nodes():
            n = node_map.get(nid)
            if n and n.entity_type != EntityType.METHOD:
                deg = graph.in_degree(nid) + graph.out_degree(nid)
                degree_list.append((n.name, deg))
        degree_list.sort(key=lambda x: x[1], reverse=True)

        # Most depended-on (highest in-degree, excluding methods)
        in_deg: List[Tuple[str, int]] = []
        for nid in graph.nodes():
            n = node_map.get(nid)
            if n and n.entity_type != EntityType.METHOD:
                d = graph.in_degree(nid)
                if d > 0:
                    in_deg.append((n.name, d))
        in_deg.sort(key=lambda x: x[1], reverse=True)

        # Highest outgoing (most dependencies)
        out_deg: List[Tuple[str, int]] = []
        for nid in graph.nodes():
            n = node_map.get(nid)
            if n and n.entity_type != EntityType.METHOD:
                d = graph.out_degree(nid)
                if d > 0:
                    out_deg.append((n.name, d))
        out_deg.sort(key=lambda x: x[1], reverse=True)

        # Unreferenced nodes (0 in-degree, not entry points)
        unreferenced = []
        for nid in graph.nodes():
            n = node_map.get(nid)
            if n and n.entity_type not in (EntityType.CONTROLLER, EntityType.API, EntityType.METHOD):
                if graph.in_degree(nid) == 0:
                    unreferenced.append(n.name)

        return {
            "most_connected": [{"name": name, "connections": deg} for name, deg in degree_list[:10]],
            "most_depended_on": [{"name": name, "incoming": d} for name, d in in_deg[:10]],
            "highest_outgoing": [{"name": name, "outgoing": d} for name, d in out_deg[:10]],
            "unreferenced": unreferenced[:15],
        }
