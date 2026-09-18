"""Java AST and framework syntax parser for Architecture Memory Engine.
Parses Spring Boot, Jakarta EE, JPA, and JUnit constructs into architectural nodes and edges.
"""

import re
from typing import List, Optional, Set, Tuple
from ame.models.schema import Edge, EntityType, Node, RelationType, SourceType
from ame.parser.base import BaseParser


class JavaParser(BaseParser):
    """
    Parses Java source files, extracting Spring Boot controllers, services,
    repositories, JPA entities, REST APIs, test cases, and dependency edges.
    """

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".java")

    def parse(self, file_path: str, content: str) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        # Extract package
        package_match = re.search(r"^\s*package\s+([\w\.]+);", content, re.MULTILINE)
        package_name = package_match.group(1) if package_match else ""

        # Extract imports
        imports = re.findall(r"^\s*import\s+([\w\.]+);", content, re.MULTILINE)

        # Detect class/interface declarations
        # Matches annotations right before class/interface declaration
        class_regex = re.compile(
            r"((?:@[\w\(\)\"\'\=\,\s\.\*\-\/]+\s*)*)"
            r"(?:public\s+|protected\s+|private\s+|abstract\s+|static\s+|final\s+)*"
            r"(class|interface|enum|record)\s+(\w+)"
            r"(?:\s+extends\s+([\w\<\>\,\s]+))?"
            r"(?:\s+implements\s+([\w\<\>\,\s]+))?"
            r"\s*\{",
            re.MULTILINE
        )

        lines = content.splitlines()

        for match in class_regex.finditer(content):
            annotations_raw = match.group(1) or ""
            decl_kind = match.group(2)  # class, interface, enum, record
            class_name = match.group(3)
            extends_raw = match.group(4) or ""
            implements_raw = match.group(5) or ""

            # Determine line numbers
            start_pos = match.start()
            start_line = content[:start_pos].count("\n") + 1
            # Simple brace matcher for end line estimation
            end_line = self._find_matching_brace_line(content, match.end() - 1, start_line)

            # Determine architectural role
            entity_type, role_metadata = self._classify_entity(
                class_name, decl_kind, annotations_raw, file_path
            )

            class_id = f"{package_name}.{class_name}" if package_name else class_name
            node_id = f"{entity_type.value}:{class_id}"

            class_node = Node(
                id=node_id,
                name=class_name,
                entity_type=entity_type,
                file_path=file_path.replace("\\", "/"),
                start_line=start_line,
                end_line=end_line,
                signature=f"{decl_kind} {class_name}",
                docstring=self._extract_preceding_javadoc(content, start_pos),
                metadata={
                    "package": package_name,
                    "kind": decl_kind,
                    "annotations": [a.strip() for a in annotations_raw.split("@") if a.strip()],
                    **role_metadata,
                }
            )
            nodes.append(class_node)

            # Class inheritance edges
            if extends_raw:
                super_class = extends_raw.split("<")[0].strip()
                if super_class and super_class != "Object":
                    edges.append(Edge(
                        source=node_id,
                        target=f"class:{super_class}",
                        relation=RelationType.EXTENDS,
                        confidence=1.0,
                        source_type=SourceType.STATIC_ANALYSIS,
                        metadata={"type": "inheritance"}
                    ))

            if implements_raw:
                for iface in implements_raw.split(","):
                    clean_iface = iface.split("<")[0].strip()
                    if clean_iface:
                        edges.append(Edge(
                            source=node_id,
                            target=f"interface:{clean_iface}",
                            relation=RelationType.IMPLEMENTS,
                            confidence=1.0,
                            source_type=SourceType.STATIC_ANALYSIS,
                            metadata={"type": "interface_implementation"}
                        ))

            # Extract fields / injected dependencies
            self._extract_dependencies(content, node_id, class_name, edges)

            # Extract methods and endpoints
            method_nodes, method_edges = self._extract_methods(
                content, node_id, class_name, package_name, file_path, annotations_raw
            )
            nodes.extend(method_nodes)
            edges.extend(method_edges)

            # Check if this class is a Test
            if entity_type == EntityType.TEST:
                # Infer which service/controller it tests
                target_name = re.sub(r"(Test|Tests|TestCase|IT)$", "", class_name)
                if target_name and target_name != class_name:
                    edges.append(Edge(
                        source=node_id,
                        target=f"service:{target_name}",
                        relation=RelationType.TESTED_BY,
                        confidence=0.92,
                        source_type=SourceType.FRAMEWORK_INFERENCE,
                        metadata={"inferred_target": target_name}
                    ))

        return nodes, edges

    def _classify_entity(
        self, class_name: str, kind: str, annotations: str, file_path: str
    ) -> Tuple[EntityType, dict]:
        """Classify class into Controller, Service, Repository, Table, Test, or standard Class."""
        meta = {}
        ann_upper = annotations.upper()

        if "RESTCONTROLLER" in ann_upper or "CONTROLLER" in ann_upper or class_name.endswith("Controller"):
            meta["role"] = "REST Controller"
            return EntityType.CONTROLLER, meta

        if "SERVICE" in ann_upper or class_name.endswith("Service"):
            meta["role"] = "Service Layer"
            return EntityType.SERVICE, meta

        if "REPOSITORY" in ann_upper or class_name.endswith("Repository") or class_name.endswith("Dao"):
            meta["role"] = "Repository Layer"
            return EntityType.SERVICE, meta

        if "ENTITY" in ann_upper or "TABLE" in ann_upper or "/model/" in file_path or "/entity/" in file_path:
            # Extract table name if present: @Table(name = "users")
            table_match = re.search(r'@Table\s*\(\s*name\s*=\s*["\'](\w+)["\']', annotations, re.I)
            if table_match:
                meta["table_name"] = table_match.group(1)
            meta["role"] = "Database Entity / Table"
            return EntityType.TABLE, meta

        if "TEST" in ann_upper or class_name.endswith("Test") or class_name.endswith("Tests") or "/test/" in file_path:
            meta["role"] = "Automated Test Suite"
            return EntityType.TEST, meta

        if kind == "interface":
            return EntityType.INTERFACE, meta

        return EntityType.CLASS, meta

    def _extract_dependencies(
        self, content: str, class_node_id: str, class_name: str, edges: List[Edge]
    ):
        """Extract injected fields (e.g. private final UserService userService;)."""
        field_regex = re.compile(
            r"^\s*(?:@Autowired\s+)?(?:private|protected|public)?\s*(?:final\s+)?([A-Z]\w+)\s+(\w+)\s*;",
            re.MULTILINE
        )
        for fmatch in field_regex.finditer(content):
            dep_type = fmatch.group(1)
            dep_var = fmatch.group(2)
            if dep_type in ["String", "Integer", "Long", "Double", "Boolean", "List", "Set", "Map", "Optional", class_name]:
                continue

            edges.append(Edge(
                source=class_node_id,
                target=f"service:{dep_type}",
                relation=RelationType.USES,
                confidence=0.95,
                source_type=SourceType.FRAMEWORK_INFERENCE,
                metadata={"injected_field": dep_var, "field_type": dep_type}
            ))

    def _extract_methods(
        self, content: str, parent_node_id: str, class_name: str, package_name: str, file_path: str, class_annotations: str
    ) -> Tuple[List[Node], List[Edge]]:
        nodes: List[Node] = []
        edges: List[Edge] = []

        # Find base route from @RequestMapping("/api/orders")
        base_route = ""
        route_match = re.search(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']', class_annotations)
        if route_match:
            base_route = route_match.group(1).rstrip("/")

        # Regex for methods
        method_regex = re.compile(
            r"((?:@[\w\(\)\"\'\=\,\s\.\*\-\/\{\}]+\s*)*)"
            r"(?:public|protected|private|static|final|\s)+([\w\<\>\[\]\,\s]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w\s\,]+)?\s*\{",
            re.MULTILINE
        )

        for match in method_regex.finditer(content):
            annotations_raw = match.group(1) or ""
            return_type = match.group(2).strip()
            method_name = match.group(3)
            params = match.group(4).strip()

            if method_name in ["if", "while", "for", "switch", "catch", class_name]:
                continue

            start_pos = match.start()
            start_line = content[:start_pos].count("\n") + 1
            end_line = self._find_matching_brace_line(content, match.end() - 1, start_line)

            method_id = f"method:{class_name}.{method_name}"

            # Check if this method is an API endpoint
            http_method, path = self._extract_http_endpoint(annotations_raw)
            if http_method:
                full_path = f"{base_route}/{path.lstrip('/')}" if path else base_route
                if not full_path:
                    full_path = "/"
                api_id = f"api:{http_method.upper()} {full_path}"
                api_node = Node(
                    id=api_id,
                    name=f"{http_method.upper()} {full_path}",
                    entity_type=EntityType.API,
                    file_path=file_path.replace("\\", "/"),
                    start_line=start_line,
                    end_line=end_line,
                    signature=f"{http_method.upper()} {full_path} -> {class_name}.{method_name}()",
                    metadata={"http_method": http_method.upper(), "path": full_path, "handler": method_name}
                )
                nodes.append(api_node)

                # Link Controller -> EXPOSES_API -> API
                edges.append(Edge(
                    source=parent_node_id,
                    target=api_id,
                    relation=RelationType.EXPOSES_API,
                    confidence=1.0,
                    source_type=SourceType.STATIC_ANALYSIS,
                    metadata={"handler_method": method_name}
                ))

            # Method node
            m_node = Node(
                id=method_id,
                name=f"{class_name}.{method_name}",
                entity_type=EntityType.METHOD,
                file_path=file_path.replace("\\", "/"),
                start_line=start_line,
                end_line=end_line,
                signature=f"{return_type} {method_name}({params})",
                docstring=self._extract_preceding_javadoc(content, start_pos),
                metadata={"return_type": return_type, "params": params}
            )
            nodes.append(m_node)

            # Class contains method
            edges.append(Edge(
                source=parent_node_id,
                target=method_id,
                relation=RelationType.USES,
                confidence=1.0,
                source_type=SourceType.STATIC_ANALYSIS,
                metadata={"type": "contains_method"}
            ))

            # Scan method body for calls: e.g. orderRepository.save(...)
            body_start = match.end()
            # approximate body
            body_slice = content[body_start : min(body_start + 4000, len(content))]
            call_matches = re.findall(r"(\w+)\.([a-z]\w+)\s*\(", body_slice)
            for target_var, called_method in call_matches:
                if target_var not in ["this", "super", "log", "logger", "System", "Arrays", "Collections", "Objects"]:
                    # Create call edge
                    edges.append(Edge(
                        source=parent_node_id,
                        target=f"service:{target_var[0].upper() + target_var[1:]}",
                        relation=RelationType.CALLS,
                        confidence=0.90,
                        source_type=SourceType.STATIC_ANALYSIS,
                        metadata={"called_method": called_method, "variable": target_var}
                    ))

        return nodes, edges

    def _extract_http_endpoint(self, annotations: str) -> Tuple[Optional[str], Optional[str]]:
        for verb in ["Get", "Post", "Put", "Delete", "Patch"]:
            pattern = rf'@{verb}Mapping\s*(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?["\']([^"\']*)["\'])?'
            match = re.search(pattern, annotations, re.I)
            if match:
                path = match.group(1) or ""
                return verb.upper(), path
        return None, None

    def _extract_preceding_javadoc(self, content: str, pos: int) -> Optional[str]:
        preceding = content[max(0, pos - 500) : pos].strip()
        if "*/" in preceding:
            start_idx = preceding.rfind("/**")
            if start_idx != -1:
                return preceding[start_idx:].strip()
        return None

    def _find_matching_brace_line(self, content: str, start_brace_idx: int, start_line: int) -> int:
        open_braces = 0
        current_line = start_line
        in_string = False

        for i in range(start_brace_idx, len(content)):
            char = content[i]
            if char == "\n":
                current_line += 1
            elif char == '"' and (i == 0 or content[i - 1] != "\\"):
                in_string = not in_string
            elif not in_string:
                if char == "{":
                    open_braces += 1
                elif char == "}":
                    open_braces -= 1
                    if open_braces == 0:
                        return current_line

        return min(start_line + 50, content.count("\n") + 1)
