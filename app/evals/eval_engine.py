import os
import time
import json
import logging
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EvalEngine:
    """Движок для оценки производительности агентов и LLM."""

    def __init__(self):
        self.results_dir = Path(__file__).parent.parent.parent / "eval_results"
        self.results_dir.mkdir(exist_ok=True)
        self.runs: List[Dict[str, Any]] = []

    def run_agent_benchmark(self, agent_name: str, test_cases: List[Dict]) -> Dict[str, Any]:
        """Запуск бенчмарка для агента."""
        logger.info(f"Starting benchmark for {agent_name} with {len(test_cases)} test cases")

        results = {
            "agent": agent_name,
            "total_cases": len(test_cases),
            "successful": 0,
            "failed": 0,
            "latencies": [],
            "details": []
        }

        for i, case in enumerate(test_cases):
            start = time.time()

            try:
                result = self._call_agent(agent_name, case["input"])
                latency = time.time() - start

                if self._validate_result(agent_name, result):
                    results["successful"] += 1
                    results["latencies"].append(latency)
                    results["details"].append({
                        "case": i + 1,
                        "status": "success",
                        "latency": latency,
                        "input": case["input"][:100]
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "case": i + 1,
                        "status": "invalid_output",
                        "input": case["input"][:100]
                    })

            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "case": i + 1,
                    "status": "error",
                    "error": str(e),
                    "input": case["input"][:100]
                })

        # Вычисление метрик
        results["success_rate"] = results["successful"] / results["total_cases"]
        results["avg_latency"] = sum(results["latencies"]) / len(results["latencies"]) if results["latencies"] else 0
        results["max_latency"] = max(results["latencies"]) if results["latencies"] else 0
        results["min_latency"] = min(results["latencies"]) if results["latencies"] else 0

        self.runs.append(results)
        return results

    def _call_agent(self, agent_name: str, input_data: str) -> Any:
        """Вызов агента (заглушка - заменить на реальный вызов)."""
        if agent_name == "ideation":
            return {
                "problem": input_data,
                "solution": "AI-powered solution",
                "target_audience": "users"
            }
        elif agent_name == "critic":
            return {"final_score": 7, "verdict": "accept", "problems": []}
        elif agent_name == "planner":
            return {"roadmap": [{"phase": "Phase 1", "tasks": ["task1"], "duration": "1 month"}]}
        return {}

    def _validate_result(self, agent_name: str, result: Any) -> bool:
        """Валидация результата агента."""
        if not result:
            return False

        if isinstance(result, dict):
            if agent_name == "ideation":
                return all(k in result for k in ["problem", "solution"])
            elif agent_name == "critic":
                return "final_score" in result
            elif agent_name == "planner":
                return "roadmap" in result
        return True

    def save_results(self, filename: str = None):
        """Сохранение результатов в файл."""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"eval_results_{timestamp}.json"

        filepath = self.results_dir / filename

        with open(filepath, "w") as f:
            json.dump(self.runs, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to {filepath}")
        return filepath

    def generate_report(self) -> str:
        """Генерация отчёта в текстовом формате."""
        lines = ["=" * 60, "EVALUATION REPORT", "=" * 60, ""]

        for run in self.runs:
            lines.append(f"Agent: {run['agent']}")  # Исправлено: строковый ключ
            lines.append(f"  Total cases: {run['total_cases']}")  # Исправлено: строковый ключ
            lines.append(f"  Successful: {run['successful']}")  # Исправлено: строковый ключ
            lines.append(f"  Failed: {run['failed']}")  # Исправлено: строковый ключ
            lines.append(f"  Success rate: {run['success_rate']:.2%}")  # Исправлено: строковый ключ
            lines.append(f"  Avg latency: {run['avg_latency']:.2f}s")  # Исправлено: строковый ключ
            lines.append(f"  Max latency: {run['max_latency']:.2f}s")  # Исправлено: строковый ключ
            lines.append("")

        return "\n".join(lines)


# Тестовые кейсы
IDEATION_TEST_CASES = [
    {"input": "startup idea for education"},
    {"input": "startup idea for healthcare"},
    {"input": "startup idea for finance"},
    {"input": "startup idea for environment"},
    {"input": "startup idea for food delivery"},
]

CRITIC_TEST_CASES = [
    {"input": {"problem": "test problem", "solution": "test solution", "target_audience": "test users"}},
    {"input": {"problem": "another problem", "solution": "another solution", "target_audience": "users"}},
]

PLANNER_TEST_CASES = [
    {"input": {"problem": "test problem", "solution": "test solution"}},
    {"input": {"problem": "complex problem", "solution": "complex solution"}},
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    engine = EvalEngine()

    # Запуск бенчмарков
    print("Running Ideation benchmark...")
    ideation_results = engine.run_agent_benchmark("ideation", IDEATION_TEST_CASES)

    print("Running Critic benchmark...")
    critic_results = engine.run_agent_benchmark("critic", CRITIC_TEST_CASES)

    print("Running Planner benchmark...")
    planner_results = engine.run_agent_benchmark("planner", PLANNER_TEST_CASES)

    # Сохранение результатов
    engine.save_results()

    # Отчёт
    print("\n" + engine.generate_report())
