"""Comparative benchmark suite for Architecture Memory Engine.
Evaluates:
  A. Full Repository Context
  B. Conventional Vector/Semantic RAG
  C. AME Architectural Minimum-Context Retrieval
Across multiple tasks and architectural patterns under fixed token budgets.

Vector RAG Evaluation Configuration:
  - Representation: Term-Frequency / Lexical Vector Space
  - Chunk Size: 25 source lines (~200 tokens)
  - Chunk Overlap: 5 source lines
  - Top-k: 5 retrieved chunks
  - Similarity Metric: Cosine / Term Overlap Similarity
  - Vector Store: In-memory sliding-window chunk index
"""

from pathlib import Path
import re
from typing import Dict, List, Set, Tuple

from ame.evaluation.metrics import EvaluationResult, compute_metrics
from ame.graph.embedded_store import EmbeddedGraphStore
from ame.ingestion.local_git import LocalGitIngestion
from ame.ingestion.pipeline import IngestionPipeline
from ame.retrieval.engine import RetrievalEngine


class BenchmarkRunner:
    """Runs automated comparison between Full Context, Vector RAG, and AME across multiple tasks."""

    def __init__(self, sample_repo_path: Path):
        self.repo_path = sample_repo_path
        self.store = EmbeddedGraphStore()
        self.pipeline = IngestionPipeline()
        self.retrieval = RetrievalEngine(self.store)

        # Ingest sample repo into AME
        ingestion = LocalGitIngestion()
        self.norm_repo = ingestion.ingest(str(self.repo_path), repo_id="sample-ecommerce")
        nodes, edges = self.pipeline.process(self.norm_repo)
        self.store.save_snapshot(self.norm_repo.snapshot, nodes, edges)
        self.snapshot_id = self.norm_repo.snapshot.snapshot_id

    def run_full_context(self, task: str) -> Tuple[str, Set[str]]:
        """Dumps all files in repository indiscriminately."""
        combined = []
        components = set()
        for fpath, nfile in self.norm_repo.files.items():
            combined.append(f"--- {fpath} ---\n{nfile.content}")
            for line in nfile.content.splitlines():
                m = re.search(r'(?:class|interface)\s+(\w+)', line)
                if m:
                    components.add(m.group(1))
        return "\n".join(combined), components

    def run_vector_rag(self, task: str, top_k_chunks: int = 5) -> Tuple[str, Set[str]]:
        """
        Simulates standard chunk-based vector retrieval:
        Chunks files into 25-line spans with 5-line overlap and ranks by similarity
        without traversing architectural dependencies or structural links.
        """
        chunks = []
        task_words = set(re.findall(r'\w+', task.lower()))

        for fpath, nfile in self.norm_repo.files.items():
            lines = nfile.content.splitlines()
            chunk_size = 25
            overlap_size = 5
            step = max(1, chunk_size - overlap_size)

            for i in range(0, len(lines), step):
                chunk_text = "\n".join(lines[i : i + chunk_size])
                chunk_words = set(re.findall(r'\w+', chunk_text.lower()))
                overlap = len(task_words.intersection(chunk_words))
                chunks.append((overlap, fpath, chunk_text))

        # Rank by vector / lexical similarity
        chunks.sort(key=lambda x: x[0], reverse=True)
        selected = chunks[:top_k_chunks]

        retrieved_text = "\n\n".join([f"// File: {f}\n{c}" for _, f, c in selected])
        components = set()
        for _, _, c in selected:
            for line in c.splitlines():
                m = re.search(r'(?:class|interface)\s+(\w+)', line)
                if m:
                    components.add(m.group(1))

        return retrieved_text, components

    def run_ame(self, task: str, token_budget: int = 8000) -> Tuple[str, Set[str]]:
        """Runs AME minimum-context architectural retrieval."""
        pkg = self.retrieval.retrieve(
            task=task,
            snapshot_id=self.snapshot_id,
            token_budget=token_budget,
            repo_root=str(self.repo_path),
        )
        components = {n.name for n in pkg.nodes}
        return pkg.to_formatted_prompt_context(), components

    def evaluate_task(
        self,
        task: str,
        ground_truth_chain: Set[str],
        ground_truth_tests: Set[str],
        token_budget: int = 8000,
    ) -> List[EvaluationResult]:
        results = []

        # 1. Full Context
        fc_text, fc_comps = self.run_full_context(task)
        results.append(compute_metrics("Full Context", task, fc_text, fc_comps, ground_truth_chain, ground_truth_tests, token_budget))

        # 2. Vector RAG
        vr_text, vr_comps = self.run_vector_rag(task)
        results.append(compute_metrics("Vector RAG", task, vr_text, vr_comps, ground_truth_chain, ground_truth_tests, token_budget))

        # 3. AME
        ame_text, ame_comps = self.run_ame(task, token_budget)
        results.append(compute_metrics("AME Architectural", task, ame_text, ame_comps, ground_truth_chain, ground_truth_tests, token_budget))

        return results


def run_multi_task_benchmarks() -> Dict[str, List[EvaluationResult]]:
    repo_dir = Path(__file__).resolve().parent.parent.parent / "samples" / "ecommerce_java"
    runner = BenchmarkRunner(repo_dir)

    benchmarks = {
        "Task 1: Order Discount Validation (Write / Transactional Flow)": runner.evaluate_task(
            task="Introduce a discount validation step before creating an order",
            ground_truth_chain={"OrderController", "OrderService", "DiscountService", "DiscountRepository", "Discount", "OrderRepository", "Order"},
            ground_truth_tests={"OrderServiceTest"},
            token_budget=8000,
        ),
        "Task 2: Product Pricing Quote Cache (Read / Query Flow)": runner.evaluate_task(
            task="Add Redis caching to product pricing quote",
            ground_truth_chain={"PricingController", "PricingService", "PricingRepository", "Product"},
            ground_truth_tests={"PricingServiceTest"},
            token_budget=8000,
        ),
        "Task 3: Coupon Expiration Enforcement (Domain Rule Flow)": runner.evaluate_task(
            task="Validate coupon expiration rules for discounts",
            ground_truth_chain={"DiscountService", "DiscountRepository", "Discount"},
            ground_truth_tests={"OrderServiceTest"},
            token_budget=8000,
        ),
    }
    return benchmarks


def print_benchmark_summary(all_results: Dict[str, List[EvaluationResult]]):
    print("\n" + "=" * 96)
    print("            ARCHITECTURE MEMORY ENGINE (AME) -- MULTI-TASK BENCHMARK RESULTS            ")
    print("=" * 96)

    # Accumulators for aggregate mean
    approach_stats: Dict[str, Dict[str, List[float]]] = {}

    for task_name, results in all_results.items():
        print(f"\n>> {task_name}")
        header = f"{'Approach':<20} | {'Tokens':<8} | {'Precision':<10} | {'Dep Recall':<11} | {'Test Recall':<12} | {'Agent Success @ 8k'}"
        print(header)
        print("-" * len(header))
        for r in results:
            print(f"{r.approach:<20} | {r.token_count:<8} | {r.context_precision:<10.2f} | {r.dependency_recall:<11.2f} | {r.test_coverage_recall:<12.2f} | {r.task_success_score:<.3f}")
            stats = approach_stats.setdefault(r.approach, {"tokens": [], "precision": [], "dep_recall": [], "test_recall": [], "success": []})
            stats["tokens"].append(r.token_count)
            stats["precision"].append(r.context_precision)
            stats["dep_recall"].append(r.dependency_recall)
            stats["test_recall"].append(r.test_coverage_recall)
            stats["success"].append(r.task_success_score)

    print("\n" + "=" * 96)
    print("                          AGGREGATE MEAN SCORES ACROSS TASKS                           ")
    print("=" * 96)
    header = f"{'Approach':<20} | {'Mean Tokens':<11} | {'Mean Prec.':<11} | {'Mean Dep.':<11} | {'Mean Test':<11} | {'Mean Agent Success'}"
    print(header)
    print("-" * len(header))
    for app_name, stats in approach_stats.items():
        m_tok = sum(stats["tokens"]) / len(stats["tokens"])
        m_pr = sum(stats["precision"]) / len(stats["precision"])
        m_dp = sum(stats["dep_recall"]) / len(stats["dep_recall"])
        m_tr = sum(stats["test_recall"]) / len(stats["test_recall"])
        m_sc = sum(stats["success"]) / len(stats["success"])
        print(f"{app_name:<20} | {m_tok:<11.0f} | {m_pr:<11.2f} | {m_dp:<11.2f} | {m_tr:<11.2f} | {m_sc:<.3f}")
    print("=" * 96 + "\n")


if __name__ == "__main__":
    results = run_multi_task_benchmarks()
    print_benchmark_summary(results)
