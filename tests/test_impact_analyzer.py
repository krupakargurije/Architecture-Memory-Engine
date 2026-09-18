import networkx as nx
from ame.models.schema import EntityType
from ame.retrieval.impact_analyzer import ImpactAnalyzer


def test_impact_analysis_blast_radius():
    G = nx.MultiDiGraph()

    # Build architectural flow:
    # UserController -> UserService -> UserRepository -> UserTable
    # UserServiceTest -> UserService
    # UserController exposes /api/users
    G.add_node("controller:UserController", name="UserController", entity_type=EntityType.CONTROLLER.value)
    G.add_node("service:UserService", name="UserService", entity_type=EntityType.SERVICE.value)
    G.add_node("repository:UserRepository", name="UserRepository", entity_type=EntityType.SERVICE.value)
    G.add_node("table:UserTable", name="UserTable", entity_type=EntityType.TABLE.value)
    G.add_node("test:UserServiceTest", name="UserServiceTest", entity_type=EntityType.TEST.value)
    G.add_node("api:GET /api/users", name="GET /api/users", entity_type=EntityType.API.value)

    G.add_edge("controller:UserController", "service:UserService", key="CALLS", relation="CALLS")
    G.add_edge("service:UserService", "repository:UserRepository", key="USES", relation="USES")
    G.add_edge("repository:UserRepository", "table:UserTable", key="ACCESSES", relation="ACCESSES")
    G.add_edge("test:UserServiceTest", "service:UserService", key="TESTED_BY", relation="TESTED_BY")
    G.add_edge("controller:UserController", "api:GET /api/users", key="EXPOSES_API", relation="EXPOSES_API")

    analyzer = ImpactAnalyzer()
    summary = analyzer.analyze_impact(G, ["service:UserService"])

    # Changing UserService should detect UserController as upstream
    assert "UserController" in summary.upstream_callers

    # Downstream dependencies should include UserRepository
    assert "UserRepository" in summary.downstream_dependencies

    # Affected tests should include UserServiceTest
    assert "UserServiceTest" in summary.affected_tests

    # Exposed APIs should be traced
    assert "GET /api/users" in summary.exposed_apis
