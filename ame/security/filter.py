"""Security and sensitive file filtering for Architecture Memory Engine.
Prevents indexing of secrets, private keys, environment files, credentials, and binary artifacts.
"""

import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from ame.config import settings


class SecurityFilter:
    """Filters out sensitive files, credentials, binaries, and ignored directories."""

    def __init__(self, extra_secret_patterns: Optional[List[str]] = None, extra_ignored_dirs: Optional[List[str]] = None):
        patterns = list(settings.secret_patterns)
        if extra_secret_patterns:
            patterns.extend(extra_secret_patterns)
        self.compiled_secret_regexes = [re.compile(p, re.IGNORECASE) for p in patterns]

        ignored = set(settings.ignored_dirs)
        if extra_ignored_dirs:
            ignored.update(extra_ignored_dirs)
        self.ignored_dirs = ignored

    def is_safe_to_index(self, rel_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if a file path is safe to ingest.
        Returns (is_safe, rejection_reason).
        """
        # Check ignored directory parts
        parts = rel_path.parts
        for part in parts[:-1]:
            if part in self.ignored_dirs or part.startswith("."):
                return False, f"Inside ignored/hidden directory: '{part}'"

        filename = rel_path.name

        # Check secret patterns first
        str_path = str(rel_path).replace("\\", "/")
        for regex in self.compiled_secret_regexes:
            if regex.search(str_path) or regex.search(filename):
                return False, f"Matches sensitive/secret pattern: '{regex.pattern}'"

        if filename.startswith(".") and filename not in [".gitignore"]:
            return False, f"Hidden file: '{filename}'"

        # Check extensions
        if rel_path.suffix.lower() not in settings.supported_extensions:
            return False, f"Unsupported file extension: '{rel_path.suffix}'"

        return True, None

    def filter_paths(self, root_dir: Path, relative_paths: Iterable[Path]) -> List[Path]:
        """Filter a list of relative paths to only safe, indexable files."""
        safe_paths: List[Path] = []
        for rel_path in relative_paths:
            is_safe, _ = self.is_safe_to_index(rel_path)
            if is_safe:
                # Also check binary content if file exists
                abs_path = root_dir / rel_path
                if abs_path.is_file() and not self._is_binary(abs_path):
                    safe_paths.append(rel_path)
        return safe_paths

    def _is_binary(self, file_path: Path) -> bool:
        """Check if file appears to be binary by testing first 1024 bytes for null bytes."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True


default_security_filter = SecurityFilter()
