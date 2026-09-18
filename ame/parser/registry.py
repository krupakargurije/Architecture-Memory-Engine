"""Parser registry for Architecture Memory Engine.
Routes source files to the appropriate AST parser based on file extension.
"""

from typing import Dict, List, Optional
from ame.parser.base import BaseParser
from ame.parser.java_parser import JavaParser
from ame.parser.python_parser import PythonParser


class ParserRegistry:
    def __init__(self):
        self._parsers: List[BaseParser] = [
            JavaParser(),
            PythonParser(),
        ]

    def register(self, parser: BaseParser):
        self._parsers.append(parser)

    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None


default_parser_registry = ParserRegistry()
