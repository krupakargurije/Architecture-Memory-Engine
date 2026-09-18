"""Configuration settings for Architecture Memory Engine (AME).
"""

from pathlib import Path
from pydantic import BaseModel, Field


class AMESettings(BaseModel):
    # Storage settings
    data_dir: Path = Field(default=Path(".ame"), description="Directory for persistent data")
    db_filename: str = Field(default="ame_graph.db", description="SQLite database filename")

    # Retrieval & Token Budget defaults
    default_token_budget: int = Field(default=8000, description="Default max tokens for context package")
    max_k_hop_depth: int = Field(default=3, description="Default graph traversal search depth")

    # Security & Exclusion settings
    secret_patterns: list[str] = Field(
        default=[
            r"^\.env.*",
            r".*\.pem$",
            r".*\.key$",
            r".*id_rsa.*",
            r".*\.p12$",
            r".*credentials.*",
            r".*secret.*",
            r".*\.pfx$",
            r".*\.token$",
        ],
        description="Regex patterns for files that should never be read or indexed"
    )

    ignored_dirs: list[str] = Field(
        default=[
            ".git",
            ".ame",
            "node_modules",
            "target",
            "build",
            "dist",
            ".idea",
            ".vscode",
            "__pycache__",
            ".pytest_cache",
            ".venv",
            "venv",
        ],
        description="Directory names to ignore during scanning"
    )

    supported_extensions: list[str] = Field(
        default=[".java", ".py"],
        description="File extensions parsed in MVP"
    )


settings = AMESettings()
