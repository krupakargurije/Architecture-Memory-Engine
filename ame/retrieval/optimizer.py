"""Token budget optimizer for Architecture Memory Engine.
Implements greedy relevance-per-token selection to maximize architectural context under a strict token budget.
"""

from typing import List, Tuple
from ame.models.context import ContextSnippet
from ame.models.schema import EntityType, Node


class GreedyTokenOptimizer:
    """
    Greedy selection algorithm maximizing architectural relevance within a strict token budget:
    Unit Value = Relevance / max(1, Token Cost)
    """

    def optimize(
        self,
        candidate_items: List[Tuple[Node, float, ContextSnippet]],
        token_budget: int = 8000,
        subgraph_overhead_tokens: int = 250,
    ) -> Tuple[List[ContextSnippet], List[Node], int]:
        """
        candidate_items: list of (Node, relevance_score, ContextSnippet)
        returns: (selected_snippets, selected_nodes, total_tokens_used)
        """
        available_tokens = max(100, token_budget - subgraph_overhead_tokens)

        # Calculate unit efficiency for each candidate
        # Boost direct services, controllers, and tests
        scored_candidates = []
        for node, relevance, snippet in candidate_items:
            token_cost = max(1, snippet.estimated_tokens)
            boost = 1.0
            if node.entity_type in [EntityType.CONTROLLER, EntityType.SERVICE]:
                boost = 1.3
            elif node.entity_type == EntityType.TEST:
                boost = 1.2
            elif node.entity_type == EntityType.API:
                boost = 1.1

            effective_score = relevance * boost
            efficiency = effective_score / token_cost
            scored_candidates.append((efficiency, effective_score, token_cost, node, snippet))

        # Sort descending by unit efficiency
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        selected_snippets: List[ContextSnippet] = []
        selected_nodes: List[Node] = []
        accumulated_tokens = subgraph_overhead_tokens

        for _, _, cost, node, snippet in scored_candidates:
            if accumulated_tokens + cost <= token_budget:
                selected_snippets.append(snippet)
                selected_nodes.append(node)
                accumulated_tokens += cost

        return selected_snippets, selected_nodes, accumulated_tokens
