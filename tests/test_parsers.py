from ame.models.schema import EntityType, RelationType, SourceType
from ame.parser.java_parser import JavaParser
from ame.parser.python_parser import PythonParser
from ame.parser.inferrer import RelationshipInferrer


def test_java_parser_spring_controller():
    java_code = """
    package com.example.demo;

    import org.springframework.web.bind.annotation.*;

    @RestController
    @RequestMapping("/api/v1/users")
    public class UserController {
        private final UserService userService;

        public UserController(UserService userService) {
            this.userService = userService;
        }

        @GetMapping("/{id}")
        public User getUser(@PathVariable String id) {
            return userService.findUser(id);
        }
    }
    """
    parser = JavaParser()
    nodes, edges = parser.parse("UserController.java", java_code)

    # Validate controller node
    controller_nodes = [n for n in nodes if n.entity_type == EntityType.CONTROLLER]
    assert len(controller_nodes) == 1
    assert controller_nodes[0].name == "UserController"

    # Validate API endpoint node
    api_nodes = [n for n in nodes if n.entity_type == EntityType.API]
    assert len(api_nodes) == 1
    assert "GET /api/v1/users/{id}" in api_nodes[0].name

    # Validate injected dependency edge
    injected_edges = [e for e in edges if e.relation == RelationType.USES]
    assert len(injected_edges) >= 1
    assert any(e.source_type == SourceType.FRAMEWORK_INFERENCE for e in injected_edges)


def test_java_parser_test_class():
    test_code = """
    package com.example.demo;

    import org.junit.jupiter.api.Test;

    public class UserServiceTest {
        @Test
        public void testFindUser() {
        }
    }
    """
    parser = JavaParser()
    nodes, edges = parser.parse("UserServiceTest.java", test_code)

    test_nodes = [n for n in nodes if n.entity_type == EntityType.TEST]
    assert len(test_nodes) == 1

    # Inferred tested_by edge
    test_edges = [e for e in edges if e.relation == RelationType.TESTED_BY]
    assert len(test_edges) == 1
    assert test_edges[0].target == "service:UserService"


def test_python_parser():
    py_code = """
    from fastapi import FastAPI

    app = FastAPI()

    class OrderService:
        def process(self, order_id: str):
            pass

    @app.get("/orders/{order_id}")
    def get_order(order_id: str):
        pass
    """
    parser = PythonParser()
    nodes, edges = parser.parse("main.py", py_code)

    service_nodes = [n for n in nodes if n.name == "OrderService"]
    assert len(service_nodes) == 1

    api_nodes = [n for n in nodes if n.entity_type == EntityType.API]
    assert len(api_nodes) == 1
    assert "GET /orders/{order_id}" in api_nodes[0].name
