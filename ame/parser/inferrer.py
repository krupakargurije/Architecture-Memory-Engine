"""Framework and cross-component relationship inferrer for Architecture Memory Engine.
Reconciles loose references into concrete graph connections with calibrated confidence scores.
"""

from typing import Dict, List, Set, Tuple
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType


class RelationshipInferrer:
    """
    Refines and resolves architectural relationships across files, classes, and framework layers.
    """

    def resolve_and_enrich(
        self, nodes: List[Node], edges: List[Edge]
    ) -> Tuple[List[Node], List[Edge]]:
        # Index nodes by id and by base name
        node_by_id: Dict[str, Node] = {n.id: n for n in nodes}
        nodes_by_name: Dict[str, List[Node]] = {}
        for n in nodes:
            nodes_by_name.setdefault(n.name, []).append(n)

        resolved_edges: List[Edge] = []
        seen_edges: Set[Tuple[str, str, str]] = set()

        for edge in edges:
            source_id = edge.source
            target_id = edge.target

            # If target_id already exists directly
            if target_id in node_by_id:
                key = (source_id, target_id, edge.relation.value)
                if key not in seen_edges:
                    seen_edges.add(key)
                    resolved_edges.append(edge)
                continue

            # Attempt to resolve target by clean name
            # E.g. target_id was "service:OrderService" or "class:Order"
            target_name = target_id.split(":")[-1].split(".")[-1]
            candidates = nodes_by_name.get(target_name, [])

            if candidates:
                best_match = candidates[0]
                new_edge = Edge(
                    source=source_id,
                    target=best_match.id,
                    relation=edge.relation,
                    confidence=min(edge.confidence, 0.95),
                    source_type=edge.source_type,
                    metadata=dict(edge.metadata),
                )
                key = (source_id, best_match.id, edge.relation.value)
                if key not in seen_edges:
                    seen_edges.add(key)
                    resolved_edges.append(new_edge)
            else:
                # Keep original edge as external/unresolved
                key = (source_id, target_id, edge.relation.value)
                if key not in seen_edges:
                    seen_edges.add(key)
                    resolved_edges.append(edge)

        # Infer Service -> Repository -> Table connections if not already explicit
        for node in nodes:
            if "Repository" in node.name:
                entity_name = node.name.replace("Repository", "")
                if entity_name in nodes_by_name:
                    for target_table in nodes_by_name[entity_name]:
                        if target_table.entity_type in [EntityType.TABLE, EntityType.CLASS]:
                            key = (node.id, target_table.id, RelationType.ACCESSES.value)
                            if key not in seen_edges:
                                seen_edges.add(key)
                                resolved_edges.append(Edge(
                                    source=node.id,
                                    target=target_table.id,
                                    relation=RelationType.ACCESSES,
                                    confidence=0.95,
                                    source_type=SourceType.FRAMEWORK_INFERENCE,
                                    metadata={"inferred": "Spring Data Repository Entity"}
                                ))

        return nodes, resolved_edges


default_inferrer = RelationshipInferrer()
