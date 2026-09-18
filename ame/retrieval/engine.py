"""Core Minimum-Context Retrieval Engine for Architecture Memory Engine.
Orchestrates Candidate Discovery -> Graph Traversal -> Impact Analysis -> Greedy Optimization -> Context Packaging.
"""

from typing import Dict, List, Optional, Set, Tuple
from ame.config import settings
from ame.graph.base import BaseGraphStore
from ame.models.context import ContextPackage, ContextSnippet, ImpactSummary
from ame.models.provenance import ProvenanceRecord, RelationshipBreadcrumb
from ame.models.schema import Edge, EntityType, Node
from ame.retrieval.candidate_finder import CandidateFinder
from ame.retrieval.graph_traversal import GraphTraversal
from ame.retrieval.impact_analyzer import ImpactAnalyzer
from ame.retrieval.optimizer import GreedyTokenOptimizer
from ame.retrieval.provenance_tracker import ProvenanceTracker
from ame.retrieval.snippet_extractor import SnippetExtractor


class RetrievalEngine:
    """Computes the minimum sufficient architectural context for an AI coding task."""

    def __init__(
        self,
        store: BaseGraphStore,
        candidate_finder: Optional[CandidateFinder] = None,
        traversal: Optional[GraphTraversal] = None,
        impact_analyzer: Optional[ImpactAnalyzer] = None,
        optimizer: Optional[GreedyTokenOptimizer] = None,
        provenance_tracker: Optional[ProvenanceTracker] = None,
    ):
        self.store = store
        self.candidate_finder = candidate_finder or CandidateFinder()
        self.traversal = traversal or GraphTraversal()
        self.impact_analyzer = impact_analyzer or ImpactAnalyzer()
        self.optimizer = optimizer or GreedyTokenOptimizer()
        self.provenance_tracker = provenance_tracker or ProvenanceTracker()

    def retrieve(
        self,
        task: str,
        snapshot_id: str,
        token_budget: Optional[int] = None,
        repo_root: Optional[str] = None,
        file_cache: Optional[Dict[str, str]] = None,
    ) -> ContextPackage:
        budget = token_budget or settings.default_token_budget

        snapshot = self.store.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        graph = self.store.get_graph(snapshot_id)
        all_nodes = self.store.get_nodes(snapshot_id)
        node_map: Dict[str, Node] = {n.id: n for n in all_nodes}

        # Step 1: Candidate Discovery (Seed Nodes)
        scored_seeds = self.candidate_finder.find_candidates(task, all_nodes, top_k=6)
        if not scored_seeds and all_nodes:
            # Fallback to top-level controllers or services if no lexical match
            entry_points = [n for n in all_nodes if n.entity_type in [EntityType.CONTROLLER, EntityType.SERVICE]]
            scored_seeds = [(n, 1.0) for n in entry_points[:3]]

        seed_ids = [n.id for n, _ in scored_seeds]
        seed_score_map = {n.id: score for n, score in scored_seeds}

        # Step 2: Graph Expansion (Traverse Dependencies & Callers)
        expanded_node_ids, connecting_edges = self.traversal.expand_subgraph(
            graph=graph,
            seed_node_ids=seed_ids,
            max_depth=settings.max_k_hop_depth,
        )

        # Step 3: First-Class Impact Analysis
        impact_summary = self.impact_analyzer.analyze_impact(graph, seed_ids)

        # Include affected tests in the expanded node set
        for node in all_nodes:
            if node.entity_type == EntityType.TEST:
                if any(t_name in node.name for t_name in impact_summary.target_components):
                    expanded_node_ids.add(node.id)

        # Step 4: Snippet Extraction
        snippet_extractor = SnippetExtractor(file_content_cache=file_cache)
        candidate_items: List[Tuple[Node, float, ContextSnippet]] = []

        # Breadcrumbs map
        edge_breadcrumbs: Dict[str, List[RelationshipBreadcrumb]] = {}
        for edge in connecting_edges:
            bc = self.provenance_tracker.edge_to_breadcrumb(edge)
            edge_breadcrumbs.setdefault(edge.target, []).append(bc)

        # Filter: if class container is present, avoid duplicating the full method snippet
        class_names_present = {
            node_map[nid].name for nid in expanded_node_ids
            if nid in node_map and node_map[nid].entity_type in [
                EntityType.CLASS, EntityType.CONTROLLER, EntityType.SERVICE,
                EntityType.TABLE, EntityType.TEST, EntityType.INTERFACE
            ]
        }

        for nid in expanded_node_ids:
            node = node_map.get(nid)
            if not node:
                continue

            if node.entity_type == EntityType.METHOD and any(c_name in node.id for c_name in class_names_present):
                # Skip duplicating full method snippet if its parent class is already included
                continue

            # Compute relevance score: seeds get original score, neighbors get discounted propagation
            base_score = seed_score_map.get(nid, 1.0)
            if nid not in seed_score_map:
                # 1-hop / 2-hop neighbor score
                base_score = 0.7

            snippet = snippet_extractor.extract_snippet(node, repo_root=repo_root)

            # Build provenance record
            prov = self.provenance_tracker.build_record(
                node=node,
                snapshot_id=snapshot_id,
                commit_id=snapshot.commit_id,
                breadcrumbs=edge_breadcrumbs.get(nid, []),
                confidence=0.95 if nid in seed_score_map else 0.85,
            )
            snippet.provenance = prov
            candidate_items.append((node, base_score, snippet))

        # Step 5: Greedy Optimization under Token Budget
        selected_snippets, selected_nodes, total_tokens = self.optimizer.optimize(
            candidate_items=candidate_items,
            token_budget=budget,
            subgraph_overhead_tokens=150 + len(connecting_edges) * 10,
        )

        # Keep only edges between selected nodes
        selected_node_ids = {n.id for n in selected_nodes}
        filtered_edges = [
            e for e in connecting_edges
            if e.source in selected_node_ids and e.target in selected_node_ids
        ]

        # Estimate full repository token size for savings metric
        full_repo_tokens = sum(max(1, (n.end_line or 10) - (n.start_line or 1)) * 10 for n in all_nodes)
        full_repo_tokens = max(full_repo_tokens, total_tokens)
        savings = ((full_repo_tokens - total_tokens) / full_repo_tokens) * 100.0 if full_repo_tokens > 0 else 0.0

        provenance_records = [s.provenance for s in selected_snippets if s.provenance]

        return ContextPackage(
            task=task,
            repo_id=snapshot.repo_id,
            snapshot_id=snapshot.snapshot_id,
            commit_id=snapshot.commit_id,
            nodes=selected_nodes,
            edges=filtered_edges,
            snippets=selected_snippets,
            impact=impact_summary,
            provenance_records=provenance_records,
            total_tokens=total_tokens,
            token_budget=budget,
            token_savings_percentage=savings,
        )
