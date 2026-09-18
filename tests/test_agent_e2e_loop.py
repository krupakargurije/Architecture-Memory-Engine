"""End-to-End Agent Pair Programming Simulation Test.
Demonstrates the full loop:
Developer Task -> AI Agent -> AME MCP retrieve_context() -> Agent Code Modification -> AME MCP create_workspace_snapshot() -> Incremental Architectural Memory Update.
"""

from pathlib import Path
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.ingestion.local_git import LocalGitIngestion
from ame.ingestion.pipeline import IngestionPipeline
from ame.mcp.tools import AMEMCPTools


def test_end_to_end_agent_loop(tmp_path):
    # Setup test repository
    db_path = tmp_path / "ame_agent_loop.db"
    store = EmbeddedGraphStore(db_path)
    tools = AMEMCPTools(store)

    sample_repo_dir = Path(__file__).resolve().parent.parent / "samples" / "ecommerce_java"
    norm_repo = LocalGitIngestion().ingest(str(sample_repo_dir), repo_id="sample-ecommerce")
    nodes, edges = IngestionPipeline().process(norm_repo)
    store.save_snapshot(norm_repo.snapshot, nodes, edges)
    initial_snapshot_id = norm_repo.snapshot.snapshot_id

    # 1. Developer Task arrives
    developer_task = "Introduce a discount validation step before creating an order"

    # 2. Agent asks AME MCP for minimum context
    context_pkg = tools.retrieve_context(
        task=developer_task,
        repo_id="sample-ecommerce",
        snapshot_id=initial_snapshot_id,
        token_budget=8000,
    )

    # Verify AME supplied the exact dependency chain
    retrieved_names = {s["name"] for s in context_pkg["snippets"]}
    assert "OrderController" in retrieved_names or "OrderService" in retrieved_names
    assert "DiscountService" in retrieved_names
    assert "OrderServiceTest" in context_pkg["impact"]["affected_tests"]

    # 3. Agent modifies code in workspace (uncommitted change)
    order_service_path = "src/main/java/com/example/ecommerce/service/OrderService.java"
    original_code = (sample_repo_dir / order_service_path).read_text(encoding="utf-8")

    # Agent adds discount validation logic and a new helper method
    modified_code = original_code.replace(
        "public Order createOrder(String customerId, BigDecimal baseTotal, String couponCode) {",
        "public Order createOrder(String customerId, BigDecimal baseTotal, String couponCode) {\n        validateDiscountEligibility(couponCode, baseTotal);"
    ) + "\n\n    public void validateDiscountEligibility(String couponCode, BigDecimal baseTotal) {\n        if (couponCode != null && !couponCode.isBlank() && baseTotal.compareTo(BigDecimal.ZERO) <= 0) {\n            throw new IllegalArgumentException(\"Invalid order amount for discount application\");\n        }\n    }\n"

    # 4. Agent submits uncommitted workspace change back to AME
    update_res = tools.create_workspace_snapshot(
        repo_id="sample-ecommerce",
        uncommitted_files={order_service_path: modified_code},
        base_snapshot_id=initial_snapshot_id,
    )

    new_snapshot_id = update_res["new_snapshot_id"]
    assert new_snapshot_id != initial_snapshot_id
    assert update_res["is_dirty"] is True

    # 5. Verify AME's architectural memory updated incrementally
    new_snapshot = store.get_snapshot(new_snapshot_id)
    assert new_snapshot is not None
    assert new_snapshot.is_dirty

    updated_nodes = store.get_nodes(new_snapshot_id)
    updated_method_ids = {n.name for n in updated_nodes}
    assert "OrderService.validateDiscountEligibility" in updated_method_ids

    # Querying AME on the updated snapshot reflects the new state immediately
    impact = tools.find_impact("OrderService", repo_id="sample-ecommerce", snapshot_id=new_snapshot_id)
    assert "OrderServiceTest" in impact["affected_tests"]
