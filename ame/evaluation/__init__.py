from ame.evaluation.metrics import EvaluationResult, compute_metrics
from ame.evaluation.benchmark import BenchmarkRunner, run_multi_task_benchmarks

run_benchmarks = run_multi_task_benchmarks

__all__ = ["EvaluationResult", "compute_metrics", "BenchmarkRunner", "run_multi_task_benchmarks", "run_benchmarks"]
