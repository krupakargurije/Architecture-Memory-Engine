"""Targeted code span and interface signature extractor for Architecture Memory Engine.
Avoids dumping entire files, extracting only the relevant code sections and architectural signatures.
"""

from pathlib import Path
from typing import Dict, Optional
from ame.models.context import ContextSnippet
from ame.models.schema import Node


class SnippetExtractor:
    """Extracts targeted code spans from source files or cached contents."""

    def __init__(self, file_content_cache: Optional[Dict[str, str]] = None):
        self._cache = file_content_cache or {}

    def extract_snippet(
        self, node: Node, repo_root: Optional[str] = None
    ) -> ContextSnippet:
        code = ""
        start_line = node.start_line or 1
        end_line = node.end_line or 1

        if node.file_path:
            content = self._get_content(node.file_path, repo_root)
            if content:
                lines = content.splitlines()
                # 1-indexed lines
                s_idx = max(0, start_line - 1)
                e_idx = min(len(lines), end_line)
                extracted_lines = lines[s_idx:e_idx]

                # Cap huge files (e.g. max 150 lines per snippet for focused context)
                if len(extracted_lines) > 150:
                    code = "\n".join(extracted_lines[:150]) + "\n// ... [truncated for minimum context]"
                else:
                    code = "\n".join(extracted_lines)

        if not code:
            # Fallback to signature and docstring if content is unavailable
            doc = f"/** {node.docstring} */\n" if node.docstring else ""
            code = f"{doc}{node.signature or node.name}"

        # Rough token approximation: 4 chars per token
        tokens = max(1, len(code) // 4)

        return ContextSnippet(
            node_id=node.id,
            name=node.name,
            entity_type=node.entity_type,
            file_path=node.file_path or "unknown",
            start_line=start_line,
            end_line=end_line,
            code=code,
            estimated_tokens=tokens,
        )

    def _get_content(self, file_path: str, repo_root: Optional[str]) -> Optional[str]:
        clean_path = file_path.replace("\\", "/")
        if clean_path in self._cache:
            return self._cache[clean_path]

        if repo_root:
            full_path = Path(repo_root) / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    self._cache[clean_path] = content
                    return content
                except Exception:
                    pass
        return None
