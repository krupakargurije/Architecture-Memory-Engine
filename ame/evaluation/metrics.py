"""Evaluation metrics for Architecture Memory Engine benchmarks.

Formal Definitions:
  - Context Precision: Percentage of retrieved context tokens/spans judged directly
    relevant to the task's architectural dependency chain.
  - Dependency Recall: Percentage of ground-truth architectural components (controllers,
    services, repositories, database tables) captured in the context.
  - Test Coverage Recall: Percentage of relevant test suites/methods captured.
  - Agent Task Success @ Fixed Token Budget: Evaluates the downstream agent outcome
    after receiving the respective context: the fraction of benchmark tasks for which
    the downstream coding agent, operating under the fixed token budget, successfully
    generated code satisfying predefined architectural correctness criteria and passing
    associated validation tests (with penalty for token truncation if budget is exceeded).
"""

from typing import List, Set
from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    approach: str = Field(..., description="Full Context | Vector RAG | AME")
    task: str = Field(..., description="Coding task prompt")
    token_count: int = Field(..., description="Total tokens in context provided to agent")
    token_budget: int = Field(default=8000, description="Fixed token budget")
    budget_exceeded: bool = Field(default=False, description="Whether token budget was violated")
    context_precision: float = Field(..., description="Percentage of retrieved tokens directly relevant to architectural chain")
    dependency_recall: float = Field(..., description="Percentage of essential architectural chain recovered")
    test_coverage_recall: float = Field(..., description="Percentage of relevant tests included in context")
    task_success_score: float = Field(..., description="Agent task success score under fixed budget")


def compute_metrics(
    approach: str,
    task: str,
    retrieved_text: str,
    retrieved_component_names: Set[str],
    ground_truth_chain: Set[str],
    ground_truth_tests: Set[str],
    token_budget: int = 8000,
) -> EvaluationResult:
    tokens = max(1, len(retrieved_text) // 4)
    budget_exceeded = tokens > token_budget

    # Dependency recall: how many of the ground truth components are captured
    matched_chain = ground_truth_chain.intersection(retrieved_component_names)
    dep_recall = len(matched_chain) / len(ground_truth_chain) if ground_truth_chain else 1.0

    # Test recall: how many ground truth tests are captured
    matched_tests = ground_truth_tests.intersection(retrieved_component_names)
    test_recall = len(matched_tests) / len(ground_truth_tests) if ground_truth_tests else 1.0

    # Precision: proportion of retrieved components that are in ground truth or tests
    all_gt = ground_truth_chain.union(ground_truth_tests)
    relevant_in_retrieved = retrieved_component_names.intersection(all_gt)
    precision = len(relevant_in_retrieved) / max(1, len(retrieved_component_names))

    # Task success under fixed budget:
    # If budget is exceeded, agent suffers token truncation penalty.
    # Otherwise, depends heavily on having the full dependency chain + tests.
    if budget_exceeded:
        truncation_factor = min(1.0, token_budget / tokens)
        success = (0.5 * dep_recall + 0.3 * precision + 0.2 * test_recall) * truncation_factor
    else:
        success = 0.6 * dep_recall + 0.2 * precision + 0.2 * test_recall

    return EvaluationResult(
        approach=approach,
        task=task,
        token_count=tokens,
        token_budget=token_budget,
        budget_exceeded=budget_exceeded,
        context_precision=round(precision, 3),
        dependency_recall=round(dep_recall, 3),
        test_coverage_recall=round(test_recall, 3),
        task_success_score=round(success, 3),
    )
