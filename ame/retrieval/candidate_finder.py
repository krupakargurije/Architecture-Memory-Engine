"""Candidate node discovery for Architecture Memory Engine.
Pluggable lexical token matching and BM25-style relevance scoring to discover seed nodes from task descriptions.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from ame.models.schema import Node


class CandidateFinder:
    """
    Finds seed architectural nodes matching a natural-language task prompt.
    Splits camelCase, snake_case, and extracts keywords.
    """

    STOP_WORDS = {
        "a", "an", "the", "and", "or", "to", "in", "on", "of", "for", "with",
        "by", "at", "from", "up", "about", "into", "over", "after", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "should", "could", "can", "add", "introduce",
        "implement", "create", "fix", "update", "modify", "change", "refactor",
        "make", "before", "after", "where", "still", "being"
    }

    def tokenize(self, text: str) -> List[str]:
        # Split camelCase and snake_case and whitespace
        s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        words = re.findall(r"[A-Za-z0-9]+", s1.lower())
        return [w for w in words if len(w) > 1 and w not in self.STOP_WORDS]

    def find_candidates(
        self, task: str, nodes: List[Node], top_k: int = 10
    ) -> List[Tuple[Node, float]]:
        """
        Computes lexical/BM25-style similarity between task tokens and node properties.
        Returns list of (Node, score) sorted in descending order.
        """
        task_tokens = self.tokenize(task)
        if not task_tokens:
            return [(n, 1.0) for n in nodes[:top_k]]

        scored: List[Tuple[Node, float]] = []

        for node in nodes:
            score = 0.0
            node_name_tokens = set(self.tokenize(node.name))
            sig_tokens = set(self.tokenize(node.signature or ""))
            doc_tokens = set(self.tokenize(node.docstring or ""))

            # Exact phrase or name match boost
            clean_task = task.lower()
            if node.name.lower() in clean_task:
                score += 5.0

            for t in task_tokens:
                if t in node_name_tokens:
                    score += 3.0
                elif any(t in nt for nt in node_name_tokens):
                    score += 1.5

                if t in sig_tokens:
                    score += 1.0
                if t in doc_tokens:
                    score += 0.5

            if score > 0:
                # Entity type weighting: Controllers and Services often form primary entry points
                if node.entity_type.value in ["controller", "service", "api"]:
                    score *= 1.2
                scored.append((node, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
