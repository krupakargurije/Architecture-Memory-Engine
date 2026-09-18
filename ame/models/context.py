"""Context package definitions returned by AME retrieval to AI coding agents.
Formalizes Minimum Context = Required Nodes + Required Edges + Relevant Code Spans + Interfaces/Signatures + Affected Tests.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ame.models.schema import Edge, EntityType, Node
from ame.models.provenance import ProvenanceRecord


class ContextSnippet(BaseModel):
    node_id: str = Field(..., description="Node ID for this code snippet")
    name: str = Field(..., description="Component name")
    entity_type: EntityType = Field(..., description="Type of component")
    file_path: str = Field(..., description="Relative file path")
    start_line: int = Field(..., description="Start line number")
    end_line: int = Field(..., description="End line number")
    code: str = Field(..., description="Extracted relevant code span or signature")
    estimated_tokens: int = Field(default=0, description="Estimated token count")
    provenance: Optional[ProvenanceRecord] = Field(default=None, description="Provenance tracking record")


class ImpactSummary(BaseModel):
    target_components: List[str] = Field(default_factory=list, description="Seed components being analyzed or modified")
    upstream_callers: List[str] = Field(default_factory=list, description="Components that call or depend on targets")
    downstream_dependencies: List[str] = Field(default_factory=list, description="Components called or accessed by targets")
    exposed_apis: List[str] = Field(default_factory=list, description="External APIs or endpoints directly affected")
    database_tables: List[str] = Field(default_factory=list, description="Database models or tables touched")
    affected_tests: List[str] = Field(default_factory=list, description="Test suites or methods covering these components")
    risk_level: str = Field(default="LOW", description="LOW | MEDIUM | HIGH | CRITICAL")


class ArchitecturalContext(BaseModel):
    nodes: List[Node] = Field(default_factory=list, description="Architectural nodes in the minimum subgraph")
    edges: List[Edge] = Field(default_factory=list, description="Dependency relationships connecting the subgraph")
    dependency_chains: List[str] = Field(default_factory=list, description="Extracted dependency chains")
    impact_summary: ImpactSummary = Field(default_factory=ImpactSummary, description="Impact and blast radius analysis")
    signatures: List[str] = Field(default_factory=list, description="Method and class signatures")


class SourceContext(BaseModel):
    snippets: List[ContextSnippet] = Field(default_factory=list, description="Targeted code spans, interfaces, and test bodies")
    file_spans: Dict[str, str] = Field(default_factory=dict, description="File paths mapped to active line spans")


class ContextPackage(BaseModel):
    task: str = Field(..., description="The coding task or question")
    repo_id: str = Field(..., description="Repository identifier")
    snapshot_id: str = Field(..., description="Snapshot identifier used for retrieval")
    commit_id: Optional[str] = Field(default=None, description="Associated Git commit if committed")

    # Explicit modeling of the two context types
    architectural_context: Optional[ArchitecturalContext] = Field(default=None, description="Architectural knowledge context")
    source_context: Optional[SourceContext] = Field(default=None, description="Source code spans context")

    # Direct accessors for backward-compatibility & serialization
    nodes: List[Node] = Field(default_factory=list, description="Architectural nodes in the minimum subgraph")
    edges: List[Edge] = Field(default_factory=list, description="Dependency relationships connecting the subgraph")
    snippets: List[ContextSnippet] = Field(default_factory=list, description="Targeted code spans and signatures")
    impact: ImpactSummary = Field(default_factory=ImpactSummary, description="Impact and ripple-effect analysis")

    # Provenance and token metrics
    provenance_records: List[ProvenanceRecord] = Field(default_factory=list, description="Provenance for each item")
    total_tokens: int = Field(default=0, description="Total tokens used by context package")
    token_budget: int = Field(default=8000, description="Max token budget constraint")
    token_savings_percentage: float = Field(default=0.0, description="Tokens saved compared to full repository context")

    def to_formatted_prompt_context(self) -> str:
        """Format the context package into a clean, markdown context block ready for an LLM agent."""
        lines = [
            f"# AME Architectural Context for Task: '{self.task}'",
            f"**Repository:** `{self.repo_id}` | **Snapshot:** `{self.snapshot_id}`"
            + (f" | **Commit:** `{self.commit_id}`" if self.commit_id else " (Workspace Snapshot)"),
            f"**Token Cost:** {self.total_tokens} / {self.token_budget} budget ({self.token_savings_percentage:.1f}% reduction vs full repo)\n",
            "## 1. Architectural Subgraph",
            "```text",
        ]

        if not self.edges:
            for node in self.nodes[:5]:
                lines.append(f"[{node.entity_type.value.upper()}] {node.name}")
        else:
            for edge in self.edges:
                lines.append(f"{edge.source} --[{edge.relation} (conf: {edge.confidence:.2f})]--> {edge.target}")

        lines.extend([
            "```\n",
            "## 2. Impact Analysis (\"What could this change affect?\")",
            f"- **Upstream Callers:** {', '.join(self.impact.upstream_callers) or 'None detected'}",
            f"- **Downstream Dependencies:** {', '.join(self.impact.downstream_dependencies) or 'None detected'}",
            f"- **Exposed APIs:** {', '.join(self.impact.exposed_apis) or 'None detected'}",
            f"- **Database Tables:** {', '.join(self.impact.database_tables) or 'None detected'}",
            f"- **Affected Tests to Run/Update:** {', '.join(self.impact.affected_tests) or 'None detected'}",
            f"- **Assessed Risk Level:** `{self.impact.risk_level}`\n",
            "## 3. Minimum Sufficient Code Context",
        ])

        for snippet in self.snippets:
            prov_str = f" (Provenance: {snippet.provenance.formatted_summary()})" if snippet.provenance else ""
            lines.extend([
                f"### {snippet.name} (`{snippet.file_path}:L{snippet.start_line}-L{snippet.end_line}`){prov_str}",
                "```java" if snippet.file_path.endswith(".java") else "```python",
                snippet.code,
                "```\n",
            ])

        return "\n".join(lines)
