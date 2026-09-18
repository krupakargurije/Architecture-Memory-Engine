"""Core Impact Analysis engine for Architecture Memory Engine.
Computes the architectural blast radius answering: "What could my change break?"
"""

from typing import Dict, List, Optional, Set
import networkx as nx

from ame.models.context import ImpactSummary
from ame.models.schema import EntityType, Node


class ImpactAnalyzer:
    """
    Analyzes upstream callers, downstream dependencies, exposed API endpoints,
    database models, and tests that could be affected by modifying target components.
    """

    def analyze_impact(
        self,
        graph: nx.MultiDiGraph,
        target_node_ids: List[str],
        max_hops: int = 3,
    ) -> ImpactSummary:
        """
        Computes upstream callers, downstream dependencies, exposed APIs, database tables,
        and affected tests for the given target node IDs.
        
        Args:
            graph: The architectural knowledge graph.
            target_node_ids: List of node IDs to analyze.
            max_hops: Maximum number of hops to traverse for impact analysis.
            
        Returns:
            ImpactSummary containing detailed impact analysis.
        """
        valid_targets = [tid for tid in target_node_ids if tid in graph]
        if not valid_targets:
            return ImpactSummary(target_components=target_node_ids, risk_level="LOW")

        upstream_callers: Set[str] = set()
        downstream_deps: Set[str] = set()
        exposed_apis: Set[str] = set()
        database_tables: Set[str] = set()
        affected_tests: Set[str] = set()

        for target in valid_targets:
            # 1. Traverse upstream (incoming edges: callers, tests)
            for caller, _, key, data in graph.in_edges(target, data=True, keys=True):
                node_data = graph.nodes.get(caller, {})
                entity_type = node_data.get("entity_type", "")
                name = node_data.get("name", caller)

                if entity_type == EntityType.TEST.value or "TEST" in key:
                    affected_tests.add(name)
                elif entity_type in [EntityType.CONTROLLER.value, EntityType.SERVICE.value]:
                    upstream_callers.add(name)
                elif entity_type == EntityType.API.value:
                    exposed_apis.add(name)
                else:
                    upstream_callers.add(name)

            # 2. Traverse downstream (outgoing edges: callees, exposed apis, tables)
            for _, callee, key, data in graph.out_edges(target, data=True, keys=True):
                node_data = graph.nodes.get(callee, {})
                entity_type = node_data.get("entity_type", "")
                name = node_data.get("name", callee)

                if entity_type == EntityType.API.value or key == "EXPOSES_API":
                    exposed_apis.add(name)
                elif entity_type == EntityType.TABLE.value or key in ["ACCESSES", "READS_FROM", "WRITES_TO"]:
                    database_tables.add(name)
                elif entity_type == EntityType.TEST.value:
                    affected_tests.add(name)
                else:
                    downstream_deps.add(name)

            # 3. Upstream callers exposing APIs (1-hop and 2-hop controllers)
            for caller, _ in list(graph.in_edges(target)):
                # Check if caller exposes APIs directly
                for _, api_node, k, _ in graph.out_edges(caller, keys=True, data=True):
                    if k == "EXPOSES_API" or graph.nodes.get(api_node, {}).get("entity_type") == EntityType.API.value:
                        exposed_apis.add(graph.nodes.get(api_node, {}).get("name", api_node))

                # Check grand callers
                for grand_caller, _ in list(graph.in_edges(caller)):
                    gc_data = graph.nodes.get(grand_caller, {})
                    if gc_data.get("entity_type") == EntityType.CONTROLLER.value:
                        upstream_callers.add(gc_data.get("name", grand_caller))
                    for _, api_node, k, _ in graph.out_edges(grand_caller, keys=True, data=True):
                        if k == "EXPOSES_API" or graph.nodes.get(api_node, {}).get("entity_type") == EntityType.API.value:
                            exposed_apis.add(graph.nodes.get(api_node, {}).get("name", api_node))

        # Risk level determination based on blast radius
        total_impacted = len(upstream_callers) + len(exposed_apis) + len(database_tables)
        if len(exposed_apis) > 0 and len(database_tables) > 0:
            risk = "HIGH" if total_impacted < 8 else "CRITICAL"
        elif total_impacted > 4:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return ImpactSummary(
            target_components=[graph.nodes.get(t, {}).get("name", t) for t in valid_targets],
            upstream_callers=sorted(list(upstream_callers)),
            downstream_dependencies=sorted(list(downstream_deps)),
            exposed_apis=sorted(list(exposed_apis)),
            database_tables=sorted(list(database_tables)),
            affected_tests=sorted(list(affected_tests)),
            risk_level=risk,
        )
