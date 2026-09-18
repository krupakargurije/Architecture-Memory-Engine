from ame.models.context import ContextSnippet
from ame.models.schema import EntityType, Node
from ame.retrieval.candidate_finder import CandidateFinder
from ame.retrieval.optimizer import GreedyTokenOptimizer


def test_candidate_finder_tokenization_and_scoring():
    nodes = [
        Node(id="c1", name="OrderController", entity_type=EntityType.CONTROLLER),
        Node(id="s1", name="OrderService", entity_type=EntityType.SERVICE),
        Node(id="s2", name="DiscountService", entity_type=EntityType.SERVICE),
        Node(id="t1", name="ProductTable", entity_type=EntityType.TABLE),
    ]

    finder = CandidateFinder()
    task = "Introduce a discount validation step before creating an order"
    scored = finder.find_candidates(task, nodes)

    names = [n.name for n, _ in scored]
    assert "OrderService" in names or "OrderController" in names
    assert "DiscountService" in names


def test_greedy_token_optimizer_respects_budget():
    optimizer = GreedyTokenOptimizer()

    node1 = Node(id="n1", name="OrderService", entity_type=EntityType.SERVICE)
    snippet1 = ContextSnippet(
        node_id="n1", name="OrderService", entity_type=EntityType.SERVICE,
        file_path="OrderService.java", start_line=1, end_line=50,
        code="public class OrderService {}", estimated_tokens=100
    )

    node2 = Node(id="n2", name="MassiveLegacyFile", entity_type=EntityType.CLASS)
    snippet2 = ContextSnippet(
        node_id="n2", name="MassiveLegacyFile", entity_type=EntityType.CLASS,
        file_path="MassiveLegacyFile.java", start_line=1, end_line=5000,
        code="// huge file", estimated_tokens=7000
    )

    candidates = [
        (node1, 5.0, snippet1),
        (node2, 1.0, snippet2),
    ]

    # With a small budget of 500 tokens, MassiveLegacyFile should be omitted
    selected_snippets, selected_nodes, total = optimizer.optimize(candidates, token_budget=500, subgraph_overhead_tokens=50)

    assert len(selected_snippets) == 1
    assert selected_snippets[0].name == "OrderService"
    assert total <= 500
