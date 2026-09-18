"""End-to-end ingestion pipeline for Architecture Memory Engine.
Orchestrates Source Ingestion -> AST Parsing -> Relationship Inference -> Graph Ready.
"""

from typing import List, Optional, Tuple
from ame.ingestion.base import NormalizedRepo
from ame.models.schema import Edge, Node
from ame.parser.inferrer import RelationshipInferrer, default_inferrer
from ame.parser.registry import ParserRegistry, default_parser_registry


class IngestionPipeline:
    """Orchestrates normalization, parsing, and relationship inference for a repository."""

    def __init__(
        self,
        parser_registry: Optional[ParserRegistry] = None,
        inferrer: Optional[RelationshipInferrer] = None,
    ):
        self.parser_registry = parser_registry or default_parser_registry
        self.inferrer = inferrer or default_inferrer

    def process(self, repo: NormalizedRepo) -> Tuple[List[Node], List[Edge]]:
        all_nodes: List[Node] = []
        all_edges: List[Edge] = []

        for rel_path, norm_file in repo.files.items():
            parser = self.parser_registry.get_parser(rel_path)
            if not parser:
                continue

            try:
                nodes, edges = parser.parse(rel_path, norm_file.content)
                all_nodes.extend(nodes)
                all_edges.extend(edges)
            except Exception:
                # Resilient error boundary: keep processing remaining files
                continue

        # Run cross-component inference
        resolved_nodes, resolved_edges = self.inferrer.resolve_and_enrich(all_nodes, all_edges)
        return resolved_nodes, resolved_edges


default_pipeline = IngestionPipeline()
