"""Base AST parser interface for Architecture Memory Engine.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from ame.models.schema import Edge, Node


class BaseParser(ABC):
    """Abstract parser interface for extracting architectural nodes and edges from source files."""

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser handles the given file extension."""
        pass

    @abstractmethod
    def parse(self, file_path: str, content: str) -> Tuple[List[Node], List[Edge]]:
        """
        Parse source file content into a tuple of (nodes, edges).
        Edges may contain observed static calls and framework-inferred relationships.
        """
        pass
