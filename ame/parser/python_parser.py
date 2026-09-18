"""Python AST parser for Architecture Memory Engine.
Parses Python modules, classes, FastAPI/Flask routes, SQLAlchemy models, and pytest cases.
"""

import ast
from typing import List, Optional, Tuple
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.parser.base import BaseParser


class PythonParser(BaseParser):
    """Parses Python source code into architectural nodes and edges using standard library ast."""

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def parse(self, file_path: str, content: str) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        import textwrap
        dedented = textwrap.dedent(content)
        try:
            tree = ast.parse(dedented, filename=file_path)
        except SyntaxError:
            return nodes, edges

        clean_path = file_path.replace("\\", "/")

        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                c_nodes, c_edges = self._parse_class(item, clean_path, content)
                nodes.extend(c_nodes)
                edges.extend(c_edges)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_nodes, f_edges = self._parse_top_level_function(item, clean_path, content)
                nodes.extend(f_nodes)
                edges.extend(f_edges)

        return nodes, edges

    def _parse_class(self, node: ast.ClassDef, file_path: str, content: str) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        class_name = node.name
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line + 20)
        docstring = ast.get_docstring(node)

        # Classify entity
        entity_type = EntityType.CLASS
        role = "Class"
        if "Controller" in class_name or "Router" in class_name:
            entity_type = EntityType.CONTROLLER
            role = "Controller"
        elif "Service" in class_name:
            entity_type = EntityType.SERVICE
            role = "Service"
        elif "Repository" in class_name or "DAO" in class_name:
            entity_type = EntityType.SERVICE
            role = "Repository"
        elif "Model" in class_name or "Table" in class_name or any(
            base.id in ["Base", "Model"] for base in node.bases if isinstance(base, ast.Name)
        ):
            entity_type = EntityType.TABLE
            role = "Model/Table"
        elif class_name.startswith("Test") or class_name.endswith("Test") or "test" in file_path.lower():
            entity_type = EntityType.TEST
            role = "Test Suite"

        class_node_id = f"{entity_type.value}:{class_name}"
        class_node = Node(
            id=class_node_id,
            name=class_name,
            entity_type=entity_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=f"class {class_name}",
            docstring=docstring,
            metadata={"role": role}
        )
        nodes.append(class_node)

        # Inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                edges.append(Edge(
                    source=class_node_id,
                    target=f"class:{base.id}",
                    relation=RelationType.EXTENDS,
                    confidence=1.0,
                    source_type=SourceType.STATIC_ANALYSIS,
                ))

        # Methods inside class
        for sub in node.body:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m_nodes, m_edges = self._parse_method(sub, class_node_id, class_name, file_path, content)
                nodes.extend(m_nodes)
                edges.extend(m_edges)

        return nodes, edges

    def _parse_method(
        self, node: ast.AST, parent_node_id: str, class_name: str, file_path: str, content: str
    ) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        fn_name = getattr(node, "name", "")
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line + 10)
        docstring = ast.get_docstring(node)

        method_id = f"method:{class_name}.{fn_name}"
        nodes.append(Node(
            id=method_id,
            name=f"{class_name}.{fn_name}",
            entity_type=EntityType.METHOD,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=f"def {fn_name}(...)",
            docstring=docstring,
        ))

        edges.append(Edge(
            source=parent_node_id,
            target=method_id,
            relation=RelationType.USES,
            confidence=1.0,
            source_type=SourceType.STATIC_ANALYSIS,
        ))

        # Check for calls in method
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                target_var, func_name = self._resolve_call(call.func)
                if target_var and target_var not in ["self", "cls", "super"]:
                    edges.append(Edge(
                        source=parent_node_id,
                        target=f"service:{target_var[0].upper() + target_var[1:]}",
                        relation=RelationType.CALLS,
                        confidence=0.88,
                        source_type=SourceType.STATIC_ANALYSIS,
                        metadata={"method": func_name}
                    ))

        return nodes, edges

    def _parse_top_level_function(
        self, node: ast.AST, file_path: str, content: str
    ) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        fn_name = getattr(node, "name", "")
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line + 10)
        docstring = ast.get_docstring(node)

        entity_type = EntityType.TEST if fn_name.startswith("test_") else EntityType.FUNCTION
        fn_id = f"{entity_type.value}:{fn_name}"

        # Check for route decorators: e.g. @app.get("/orders") or @router.post("/checkout")
        api_route = self._extract_route_decorator(getattr(node, "decorator_list", []))
        if api_route:
            verb, path = api_route
            api_id = f"api:{verb} {path}"
            nodes.append(Node(
                id=api_id,
                name=f"{verb} {path}",
                entity_type=EntityType.API,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                signature=f"{verb} {path} -> {fn_name}()",
                metadata={"http_method": verb, "path": path, "handler": fn_name}
            ))
            edges.append(Edge(
                source=fn_id,
                target=api_id,
                relation=RelationType.EXPOSES_API,
                confidence=1.0,
                source_type=SourceType.STATIC_ANALYSIS,
            ))

        nodes.append(Node(
            id=fn_id,
            name=fn_name,
            entity_type=entity_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=f"def {fn_name}(...)",
            docstring=docstring,
        ))

        return nodes, edges

    def _resolve_call(self, func_node: ast.AST) -> Tuple[Optional[str], Optional[str]]:
        if isinstance(func_node, ast.Attribute):
            val = func_node.value
            var_name = getattr(val, "id", None) or getattr(val, "attr", None)
            return var_name, func_node.attr
        return None, None

    def _extract_route_decorator(self, decorators: list) -> Optional[Tuple[str, str]]:
        for dec in decorators:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                attr = dec.func.attr.upper()
                if attr in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    path = "/"
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = str(dec.args[0].value)
                    return attr, path
        return None
