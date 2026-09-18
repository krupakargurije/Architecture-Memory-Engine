"""Model Context Protocol (MCP) server implementation for Architecture Memory Engine.
Provides standard JSON-RPC 2.0 stdio communication for AI coding agents (Antigravity, Codex, Cursor, etc.).
"""

import json
import sys
from typing import Any, Dict, List, Optional
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.mcp.tools import AMEMCPTools


class MCPServer:
    """Standard Model Context Protocol stdio server."""

    def __init__(self, store: Optional[EmbeddedGraphStore] = None):
        self.store = store or EmbeddedGraphStore()
        self.tools = AMEMCPTools(self.store)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "retrieve_context",
                "description": "Retrieves the minimum sufficient architectural context, dependency graph, and code snippets for a coding task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Natural language developer task or question."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID (defaults to latest)."},
                        "token_budget": {"type": "integer", "description": "Maximum token budget constraint (default 8000)."},
                    },
                    "required": ["task", "repo_id"]
                }
            },
            {
                "name": "find_impact",
                "description": "Answers 'What could my change break?' by analyzing upstream callers, exposed APIs, database tables, and tests.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {"type": "string", "description": "Target component (e.g. OrderService, PaymentController)."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."}
                    },
                    "required": ["component_name", "repo_id"]
                }
            },
            {
                "name": "get_repository_architecture",
                "description": "Returns high-level summary of controllers, services, database tables, APIs, and tests.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."}
                    },
                    "required": ["repo_id"]
                }
            },
            {
                "name": "find_dependencies",
                "description": "Finds upstream callers and downstream dependencies of an architectural component.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {"type": "string", "description": "Component name."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."},
                        "direction": {"type": "string", "enum": ["upstream", "downstream", "both"], "default": "both"}
                    },
                    "required": ["component_name", "repo_id"]
                }
            },
            {
                "name": "find_call_chain",
                "description": "Finds the shortest architectural path/call chain connecting two components.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source component name."},
                        "target": {"type": "string", "description": "Target component name."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."}
                    },
                    "required": ["source", "target", "repo_id"]
                }
            },
            {
                "name": "get_related_tests",
                "description": "Finds test suites and methods that test or cover a specific component.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "component_name": {"type": "string", "description": "Component name."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."}
                    },
                    "required": ["component_name", "repo_id"]
                }
            },
            {
                "name": "create_workspace_snapshot",
                "description": "Submits active uncommitted workspace changes to produce a real-time updated architectural graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "uncommitted_files": {"type": "object", "description": "Map of relative file paths to current buffer contents."},
                        "base_snapshot_id": {"type": "string", "description": "Base snapshot ID to apply changes onto."}
                    },
                    "required": ["repo_id", "uncommitted_files"]
                }
            },
            {
                "name": "search_architecture",
                "description": "Search architectural components by name, signature, or keyword.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term."},
                        "repo_id": {"type": "string", "description": "Repository identifier."},
                        "snapshot_id": {"type": "string", "description": "Optional snapshot ID."},
                        "entity_type": {"type": "string", "description": "Optional filter (controller, service, table, test, api)."}
                    },
                    "required": ["query", "repo_id"]
                }
            }
        ]

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "Architecture Memory Engine",
                        "version": "0.1.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions()
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            try:
                res = self.execute_tool(tool_name, args)
                formatted_text = json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": formatted_text}
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found."
                }
            }

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "retrieve_context":
            return self.tools.retrieve_context(**args)
        elif tool_name == "find_impact":
            return self.tools.find_impact(**args)
        elif tool_name == "get_repository_architecture":
            return self.tools.get_repository_architecture(**args)
        elif tool_name == "find_dependencies":
            return self.tools.find_dependencies(**args)
        elif tool_name == "find_call_chain":
            return self.tools.find_call_chain(**args)
        elif tool_name == "get_related_tests":
            return self.tools.get_related_tests(**args)
        elif tool_name == "create_workspace_snapshot":
            return self.tools.create_workspace_snapshot(**args)
        elif tool_name == "search_architecture":
            return self.tools.search_architecture(**args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def run_stdio(self):
        """Runs the MCP server loop reading JSON-RPC messages from stdin."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()


def main():
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
