"""Schema definitions for Architecture Memory Engine graph entities and relations.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    REPOSITORY = "repository"
    MODULE = "module"
    FILE = "file"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    SERVICE = "service"
    CONTROLLER = "controller"
    API = "api"
    DATABASE = "database"
    TABLE = "table"
    EVENT = "event"
    TEST = "test"


class RelationType(str, Enum):
    CALLS = "CALLS"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    IMPORTS = "IMPORTS"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    EXPOSES_API = "EXPOSES_API"
    ACCESSES = "ACCESSES"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    TESTED_BY = "TESTED_BY"
    PUBLISHES = "PUBLISHES"
    CONSUMES = "CONSUMES"


class SourceType(str, Enum):
    STATIC_ANALYSIS = "static_analysis"
    FRAMEWORK_INFERENCE = "framework_inference"
    EVENT_BINDING = "event_binding"
    RUNTIME_HEURISTIC = "runtime_heuristic"


class Node(BaseModel):
    id: str = Field(..., description="Unique node identifier, e.g. class:com.example.OrderService")
    name: str = Field(..., description="Short name, e.g. OrderService or getOrder")
    entity_type: EntityType = Field(..., description="Architectural entity type")
    file_path: Optional[str] = Field(default=None, description="Path relative to repository root")
    start_line: Optional[int] = Field(default=None, description="1-indexed starting line")
    end_line: Optional[int] = Field(default=None, description="1-indexed ending line")
    signature: Optional[str] = Field(default=None, description="Method/class signature or route definition")
    docstring: Optional[str] = Field(default=None, description="Documentation or Javadoc/docstring")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class Edge(BaseModel):
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    relation: RelationType = Field(..., description="Relationship type")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0.0 - 1.0")
    source_type: SourceType = Field(
        default=SourceType.STATIC_ANALYSIS,
        description="Whether relationship was observed statically or inferred via framework rules"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata")
