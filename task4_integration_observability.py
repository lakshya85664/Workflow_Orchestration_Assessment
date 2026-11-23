
"""Topic 19 - Task 4: Integration Boundary and Observability.

This module demonstrates:
- An injectable external dependency adapter.
- A deterministic fake adapter for tests.
- Structured JSON event traces.
- Basic dependency metrics.
- Workflow status and trace inspection.
- Recursive secret redaction.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "client_secret",
}


def redact_secrets(value: Any) -> Any:
    """Return a copy of data with sensitive values redacted."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = redact_secrets(item)
        return cleaned

    if isinstance(value, list):
        return [redact_secrets(item) for item in value]

    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]

    return value


@runtime_checkable
class ExternalServiceAdapter(Protocol):
    """Contract for an injectable external service dependency."""

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class FakeExternalServiceAdapter:
    """Deterministic adapter for local development and testing."""

    def __init__(
        self,
        should_fail: bool = False,
        response: dict[str, Any] | None = None,
    ) -> None:
        self.should_fail = should_fail
        self.response = response or {
            "accepted": True,
            "external_id": "FAKE-1001",
        }
        self.call_count = 0
        self.last_payload: dict[str, Any] | None = None

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        self.last_payload = payload

        if self.should_fail:
            raise ConnectionError("Simulated external dependency failure")

        return dict(self.response)


@dataclass
class DependencyMetrics:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0

    @property
    def average_duration_ms(self) -> float:
        if self.calls == 0:
            return 0.0
        return round(self.total_duration_ms / self.calls, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "average_duration_ms": self.average_duration_ms,
        }


@dataclass
class IntegrationResult:
    status: str
    run_id: str
    response: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrationObserver:
    """Records structured events and exposes status and trace queries."""

    events: list[dict[str, Any]] = field(default_factory=list)
    metrics: DependencyMetrics = field(default_factory=DependencyMetrics)
    statuses: dict[str, str] = field(default_factory=dict)

    def record(self, event_type: str, **details: Any) -> None:
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "event_type": event_type,
            **redact_secrets(details),
        }
        self.events.append(event)

    def set_status(self, run_id: str, status: str) -> None:
        self.statuses[run_id] = status

    def get_status(self, run_id: str) -> str:
        return self.statuses.get(run_id, "unknown")

    def get_trace(self, run_id: str) -> list[dict[str, Any]]:
        return [
            event for event in self.events
            if event.get("run_id") == run_id
        ]

    def export_jsonl(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("w", encoding="utf-8") as file:
            for event in self.events:
                file.write(json.dumps(event, sort_keys=True) + "\n")

    def export_metrics(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.metrics.to_dict(), indent=2),
            encoding="utf-8",
        )


class IntegrationBoundary:
    """Wraps an external dependency and makes its behavior observable."""

    def __init__(
        self,
        adapter: ExternalServiceAdapter,
        observer: IntegrationObserver | None = None,
    ) -> None:
        self.adapter = adapter
        self.observer = observer or IntegrationObserver()

    def execute(
        self,
        run_id: str,
        payload: dict[str, Any],
    ) -> IntegrationResult:
        self.observer.set_status(run_id, "running")
        self.observer.record(
            "dependency_call_started",
            run_id=run_id,
            dependency="external_service",
            payload=payload,
        )

        self.observer.metrics.calls += 1
        started = time.perf_counter()

        try:
            response = self.adapter.send(payload)

            if not isinstance(response, dict):
                raise TypeError("Dependency response must be a dictionary")

            duration = (time.perf_counter() - started) * 1000
            self.observer.metrics.total_duration_ms += duration
            self.observer.metrics.successes += 1
            self.observer.set_status(run_id, "completed")

            self.observer.record(
                "dependency_call_succeeded",
                run_id=run_id,
                dependency="external_service",
                duration_ms=round(duration, 3),
                response=response,
            )

            return IntegrationResult(
                status="completed",
                run_id=run_id,
                response=response,
            )

        except Exception as exc:
            duration = (time.perf_counter() - started) * 1000
            self.observer.metrics.total_duration_ms += duration
            self.observer.metrics.failures += 1
            self.observer.set_status(run_id, "failed")

            self.observer.record(
                "dependency_call_failed",
                run_id=run_id,
                dependency="external_service",
                duration_ms=round(duration, 3),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            return IntegrationResult(
                status="failed",
                run_id=run_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )


def run_task4_demo(
    output_dir: str | Path = "outputs",
    trace_dir: str | Path = "traces",
) -> dict[str, Any]:
    """Run one success and one failure scenario using fake adapters."""

    output_path = Path(output_dir)
    trace_path = Path(trace_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    trace_path.mkdir(parents=True, exist_ok=True)

    observer = IntegrationObserver()

    success_boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(),
        observer,
    )
    success = success_boundary.execute(
        "TASK4-RUN-SUCCESS",
        {
            "order_id": "ORDER-1001",
            "api_key": "demo-secret-value",
            "amount": 1500,
        },
    )

    failure_boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(should_fail=True),
        observer,
    )
    failure = failure_boundary.execute(
        "TASK4-RUN-FAILURE",
        {"order_id": "ORDER-1002", "amount": 2500},
    )

    observer.export_jsonl(trace_path / "task4_integration_trace.jsonl")
    observer.export_metrics(output_path / "task4_metrics.json")

    report = {
        "task": "Topic 19 - Task 4",
        "success_scenario": success.to_dict(),
        "failure_scenario": failure.to_dict(),
        "metrics": observer.metrics.to_dict(),
        "status_checks": {
            "success_run": observer.get_status("TASK4-RUN-SUCCESS"),
            "failure_run": observer.get_status("TASK4-RUN-FAILURE"),
        },
        "trace_event_count": len(observer.events),
        "trace_files": ["traces/task4_integration_trace.jsonl"],
        "limitations": [
            "The fake adapter simulates dependency behavior; it does not call a live service.",
            "Metrics and events are held in memory until exported.",
            "This example does not implement distributed tracing or persistent metrics storage.",
            "Secret redaction is based on recognized dictionary key names; it is not a substitute for secure secret handling.",
        ],
    }

    report_file = output_path / "task4_measurement_report.json"
    report_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    return report


if __name__ == "__main__":
    result = run_task4_demo()
    print("=" * 65)
    print("TOPIC 19 - TASK 4 INTEGRATION AND OBSERVABILITY")
    print("=" * 65)
    print(json.dumps(result, indent=2))
    print("=" * 65)
    print("Trace: traces/task4_integration_trace.jsonl")
    print("Metrics: outputs/task4_metrics.json")
    print("Report: outputs/task4_measurement_report.json")
