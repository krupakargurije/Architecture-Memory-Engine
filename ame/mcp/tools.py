"""Model Context Protocol (MCP) tool implementations for Architecture Memory Engine.
Agent-agnostic architectural operations exposed to AI coding agents.
"""

from typing import Any, Dict, List, Optional
from ame.graph.base import BaseGraphStore
from ame.incremental.updater import IncrementalGraphUpdater
from ame.models.schema import EntityType
from ame.models.snapshot import ChangeType, UncommittedChange
from ame.retrieval.engine import RetrievalEngine


def infer_task_intent(task: str) -> str:
    """Classifies user task into an architectural intent category."""
    t = task.lower()
    if any(k in t for k in ["what break", "what will break", "what could break", "affect", "impact", "blast radius", "break"]):
        return "CHANGE IMPACT"
    if any(k in t for k in ["test", "tests", "coverage", "cover", "tested"]):
        return "TEST DISCOVERY"
    if any(k in t for k in ["where", "locate", "find", "explore", "show architecture", "how does", "what is"]):
        return "ARCHITECTURE EXPLORATION"
    if any(k in t for k in ["depend", "caller", "calls", "upstream", "downstream", "chain", "flow"]):
        return "DEPENDENCY DISCOVERY"
    if any(k in t for k in ["fix", "bug", "error", "issue", "fail", "broken", "debug", "solve"]):
        return "DEBUGGING"
    return "IMPLEMENTATION"


class AMEMCPTools:
    """Provides high-level MCP tool handlers backed by AME graph store and retrieval engine."""

    def __init__(self, store: BaseGraphStore, retrieval_engine: Optional[RetrievalEngine] = None):
        self.store = store
        self.retrieval = retrieval_engine or RetrievalEngine(store)
        self.updater = IncrementalGraphUpdater(store)

    def _resolve_snapshot_id(self, repo_id: str, snapshot_id: Optional[str] = None) -> str:
        if snapshot_id:
            return snapshot_id
        latest = self.store.get_latest_snapshot(repo_id)
        if not latest:
            raise ValueError(f"No snapshot found for repository: {repo_id}")
        return latest.snapshot_id

    def get_repository_architecture(
        self, repo_id: str, snapshot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Returns high-level summary of controllers, services, entities, tests, and API routes."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        nodes = self.store.get_nodes(snap_id)
        edges = self.store.get_edges(snap_id)

        by_type: Dict[str, List[str]] = {}
        for n in nodes:
            by_type.setdefault(n.entity_type.value, []).append(n.name)

        return {
            "repo_id": repo_id,
            "snapshot_id": snap_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "controllers": by_type.get(EntityType.CONTROLLER.value, []),
            "services": by_type.get(EntityType.SERVICE.value, []),
            "database_tables": by_type.get(EntityType.TABLE.value, []),
            "apis": by_type.get(EntityType.API.value, []),
            "tests": by_type.get(EntityType.TEST.value, []),
        }

    def search_architecture(
        self,
        query: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Searches architectural components by keyword or symbol name."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        etype = EntityType(entity_type) if entity_type else None
        nodes = self.store.get_nodes(snap_id, entity_type=etype)

        query_lower = query.lower()
        matches = [
            {
                "id": n.id,
                "name": n.name,
                "entity_type": n.entity_type.value,
                "file_path": n.file_path,
                "lines": f"{n.start_line}-{n.end_line}",
                "signature": n.signature,
            }
            for n in nodes
            if query_lower in n.name.lower()
            or query_lower in (n.signature or "").lower()
            or query_lower in (n.docstring or "").lower()
        ]
        return matches[:20]

    def find_dependencies(
        self,
        component_name: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
        direction: str = "both",
    ) -> Dict[str, Any]:
        """Finds what calls this component (upstream) and what this component calls (downstream)."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        graph = self.store.get_graph(snap_id)

        target_id = None
        for n in graph.nodes():
            if graph.nodes[n].get("name") == component_name or n.endswith(f":{component_name}"):
                target_id = n
                break

        if not target_id:
            return {"error": f"Component '{component_name}' not found in architecture graph."}

        upstream = []
        if direction in ["upstream", "both"]:
            for u, _, k, d in graph.in_edges(target_id, data=True, keys=True):
                upstream.append({
                    "component": graph.nodes[u].get("name", u),
                    "relation": d.get("relation", k),
                    "confidence": d.get("confidence", 1.0),
                })

        downstream = []
        if direction in ["downstream", "both"]:
            for _, v, k, d in graph.out_edges(target_id, data=True, keys=True):
                downstream.append({
                    "component": graph.nodes[v].get("name", v),
                    "relation": d.get("relation", k),
                    "confidence": d.get("confidence", 1.0),
                })

        return {
            "component": component_name,
            "target_id": target_id,
            "upstream_callers": upstream,
            "downstream_dependencies": downstream,
        }

    def find_call_chain(
        self,
        source: str,
        target: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Finds the shortest architectural path between two components."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        graph = self.store.get_graph(snap_id)

        src_id = next((n for n in graph.nodes() if graph.nodes[n].get("name") == source or n.endswith(f":{source}")), None)
        tgt_id = next((n for n in graph.nodes() if graph.nodes[n].get("name") == target or n.endswith(f":{target}")), None)

        if not src_id or not tgt_id:
            return {"error": f"Could not find source '{source}' or target '{target}'."}

        path = self.retrieval.traversal.find_call_chain(graph, src_id, tgt_id)
        if not path:
            return {"path": [], "message": f"No architectural path found between {source} and {target}"}

        named_path = [graph.nodes[p].get("name", p) for p in path]
        return {
            "source": source,
            "target": target,
            "length": len(path) - 1,
            "path": named_path,
            "raw_nodes": path,
        }

    def find_impact(
        self,
        component_name: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Answers 'What could my change break?' for a component."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        graph = self.store.get_graph(snap_id)

        target_id = next((n for n in graph.nodes() if graph.nodes[n].get("name") == component_name or n.endswith(f":{component_name}")), None)
        if not target_id:
            return {"error": f"Component '{component_name}' not found."}

        summary = self.retrieval.impact_analyzer.analyze_impact(graph, [target_id])
        return summary.model_dump()

    def retrieve_context(
        self,
        task: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
        token_budget: int = 8000,
        repo_root: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main entry point: retrieves minimum sufficient context for a developer coding task."""
        snap_id = self._resolve_snapshot_id(repo_id, snapshot_id)
        pkg = self.retrieval.retrieve(
            task=task,
            snapshot_id=snap_id,
            token_budget=token_budget,
            repo_root=repo_root,
        )

        # Build why-included & relevance mapping for each node
        why_map: Dict[str, str] = {}
        relevance_map: Dict[str, float] = {}
        node_name_map = {n.id: n.name for n in pkg.nodes}

        for n in pkg.nodes:
            if n.name in pkg.impact.target_components:
                why_map[n.name] = "Direct candidate seed matching task query"
                relevance_map[n.name] = 0.95
            elif n.name in pkg.impact.downstream_dependencies:
                why_map[n.name] = "Downstream dependency called during task flow"
                relevance_map[n.name] = 0.88
            elif n.name in pkg.impact.upstream_callers:
                why_map[n.name] = "Upstream caller affected by changes to component"
                relevance_map[n.name] = 0.82
            elif n.name in pkg.impact.affected_tests:
                why_map[n.name] = "Automated test suite verifying affected components"
                relevance_map[n.name] = 0.80
            elif n.entity_type.value in ["table", "database"]:
                why_map[n.name] = "Persistent entity accessed by repository layer"
                relevance_map[n.name] = 0.78
            else:
                why_map[n.name] = "Architectural dependency within 2-hop traversal"
                relevance_map[n.name] = 0.72

        dependency_chains = []
        for e in pkg.edges:
            src_name = node_name_map.get(e.source, e.source.split(":")[-1])
            tgt_name = node_name_map.get(e.target, e.target.split(":")[-1])
            dependency_chains.append({
                "source": src_name,
                "relation": e.relation.value,
                "target": tgt_name,
                "confidence": e.confidence,
            })

        enriched_snippets = []
        for s in pkg.snippets:
            s_dict = s.model_dump()
            s_dict["why_included"] = why_map.get(s.name, "Architectural dependency")
            s_dict["task_relevance"] = relevance_map.get(s.name, 0.80)
            s_dict["token_cost"] = s.estimated_tokens
            enriched_snippets.append(s_dict)

        return {
            "task": pkg.task,
            "repo_id": pkg.repo_id,
            "snapshot_id": pkg.snapshot_id,
            "task_intent": infer_task_intent(task),
            "total_tokens": pkg.total_tokens,
            "token_budget": pkg.token_budget,
            "token_savings_percentage": pkg.token_savings_percentage,
            "impact": pkg.impact.model_dump(),
            "nodes_count": len(pkg.nodes),
            "edges_count": len(pkg.edges),
            "snippets_count": len(pkg.snippets),
            "nodes": [n.model_dump() for n in pkg.nodes],
            "edges": [e.model_dump() for e in pkg.edges],
            "dependency_chains": dependency_chains,
            "why_included": why_map,
            "formatted_context": pkg.to_formatted_prompt_context(),
            "snippets": enriched_snippets,
            "provenance_records": [p.model_dump() for p in pkg.provenance_records],
        }

    def get_related_tests(
        self,
        component_name: str,
        repo_id: str,
        snapshot_id: Optional[str] = None,
    ) -> List[str]:
        """Returns test classes or test methods that cover or exercise this component."""
        impact = self.find_impact(component_name, repo_id, snapshot_id)
        if "error" in impact:
            return []
        return impact.get("affected_tests", [])

    def create_workspace_snapshot(
        self,
        repo_id: str,
        uncommitted_files: Dict[str, str],
        base_snapshot_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Allows AI agents to index active uncommitted workspace files right now."""
        base_id = self._resolve_snapshot_id(repo_id, base_snapshot_id)
        changes = {
            f: UncommittedChange(file_path=f, change_type=ChangeType.MODIFIED, content=content)
            for f, content in uncommitted_files.items()
        }
        new_snap, stats = self.updater.apply_workspace_changes(
            base_snapshot_id=base_id,
            changed_files=changes,
            workspace_id=workspace_id,
        )
        return {
            "new_snapshot_id": new_snap.snapshot_id,
            "repo_id": repo_id,
            "is_dirty": True,
            "stats": stats,
        }
