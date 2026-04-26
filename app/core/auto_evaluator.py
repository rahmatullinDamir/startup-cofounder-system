import os
import time
import logging
import threading
from typing import Dict, Any, Optional
from app.observability.langfuse_client import LangfuseClient

logger = logging.getLogger(__name__)


class AutoEvaluator:
    """Автоматическая оценка каждого запроса в реальном времени."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.langfuse = LangfuseClient()
        self._lock = threading.Lock()

        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_latency = 0.0
        self._request_latencies = []

    def evaluate_request(self, request_id: str, input_data: str, output_data: Dict[str, Any],
                         latency: float, status: str = "success", error: Optional[str] = None):
        if not self.enabled:
            return

        trace = None
        try:
            trace = self.langfuse.create_trace(
                name="auto_evaluator.request",
                input=input_data,
                output=output_data,
                metadata={"status": status, "latency": latency, "has_error": error is not None}
            )

            self.langfuse.create_span(
                name="auto_evaluator.evaluation",
                input={"request_id": request_id, "latency": latency},
                output={"status": status, "error": error},
                metadata={"request_id": request_id, "status": status, "latency": latency}
            )

            score_value = 1.0 if status == "success" else 0.0
            self.langfuse.create_score(
                trace_id=trace.trace_id,
                name="request_success",
                value=score_value,
                metadata={"request_id": request_id}
            )

            self.langfuse.create_score(
                trace_id=trace.trace_id,
                name="latency",
                value=latency,
                metadata={"request_id": request_id, "unit": "seconds"}
            )

            with self._lock:
                self._total_requests += 1
                if status == "success":
                    self._successful_requests += 1
                else:
                    self._failed_requests += 1
                self._total_latency += latency
                self._request_latencies.append(latency)
                # Keep only last 100 latencies to prevent memory leak
                if len(self._request_latencies) > 100:
                    self._request_latencies = self._request_latencies[-100:]

            logger.info(f"Auto-evaluation: request_id={request_id}, status={status}, latency={latency:.2f}s")

        except Exception as e:
            logger.error(f"Auto-evaluation failed for request {request_id}: {e}")
            if trace:
                trace.update(metadata={"eval_error": str(e)})

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            if self._total_requests == 0:
                return {"total_requests": 0, "success_rate": 0.0, "avg_latency": 0.0, "p50_latency": 0.0,
                        "p95_latency": 0.0, "p99_latency": 0.0}

            success_rate = self._successful_requests / self._total_requests
            avg_latency = self._total_latency / self._total_requests
            sorted_latencies = sorted(self._request_latencies)
            n = len(sorted_latencies)

            p50 = sorted_latencies[int(n * 0.50)] if n > 0 else 0
            p95 = sorted_latencies[int(n * 0.95)] if n > 0 else 0
            p99 = sorted_latencies[min(int(n * 0.99), n - 1)] if n > 0 else 0

            return {
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "success_rate": success_rate,
                "avg_latency": avg_latency,
                "p50_latency": p50,
                "p95_latency": p95,
                "p99_latency": p99
            }


_evaluator = None
_evaluator_lock = threading.Lock()


def get_auto_evaluator() -> AutoEvaluator:
    global _evaluator
    if _evaluator is None:
        with _evaluator_lock:
            if _evaluator is None:
                enabled = os.getenv("AUTO_EVALUATOR_ENABLED", "true").lower() == "true"
                _evaluator = AutoEvaluator(enabled=enabled)
    return _evaluator


def evaluate_request(request_id: str, input_data: str, output_data: Dict[str, Any],
                     latency: float, status: str = "success", error: Optional[str] = None):
    evaluator = get_auto_evaluator()
    evaluator.evaluate_request(request_id, input_data, output_data, latency, status, error)


def get_metrics() -> Dict[str, Any]:
    evaluator = get_auto_evaluator()
    return evaluator.get_metrics()
