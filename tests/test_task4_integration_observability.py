
import json

import pytest

from task4_integration_observability import (
    DependencyMetrics,
    ExternalServiceAdapter,
    FakeExternalServiceAdapter,
    IntegrationBoundary,
    IntegrationObserver,
    redact_secrets,
    run_task4_demo,
)


def test_fake_adapter_can_be_injected():
    adapter = FakeExternalServiceAdapter()
    boundary = IntegrationBoundary(adapter)

    result = boundary.execute("RUN-INJECT-1", {"order_id": "ORD-1"})

    assert result.status == "completed"
    assert result.response["accepted"] is True
    assert adapter.call_count == 1


def test_adapter_satisfies_integration_contract():
    adapter = FakeExternalServiceAdapter()

    assert isinstance(adapter, ExternalServiceAdapter)


def test_dependency_failure_is_returned_and_observable():
    observer = IntegrationObserver()
    adapter = FakeExternalServiceAdapter(should_fail=True)
    boundary = IntegrationBoundary(adapter, observer)

    result = boundary.execute("RUN-FAIL-1", {"order_id": "ORD-2"})

    assert result.status == "failed"
    assert result.error_type == "ConnectionError"
    assert observer.get_status("RUN-FAIL-1") == "failed"


def test_successful_dependency_call_updates_metrics():
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(),
        observer,
    )

    result = boundary.execute("RUN-METRIC-1", {"amount": 100})

    assert result.status == "completed"
    assert observer.metrics.calls == 1
    assert observer.metrics.successes == 1
    assert observer.metrics.failures == 0
    assert observer.metrics.total_duration_ms >= 0


def test_failed_dependency_call_updates_metrics():
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(should_fail=True),
        observer,
    )

    boundary.execute("RUN-METRIC-2", {"amount": 100})

    assert observer.metrics.calls == 1
    assert observer.metrics.successes == 0
    assert observer.metrics.failures == 1


def test_trace_contains_structured_start_and_success_events():
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(),
        observer,
    )

    boundary.execute("RUN-TRACE-1", {"order_id": "ORD-3"})

    trace = observer.get_trace("RUN-TRACE-1")
    event_types = [event["event_type"] for event in trace]

    assert event_types == [
        "dependency_call_started",
        "dependency_call_succeeded",
    ]
    assert all("event_id" in event for event in trace)
    assert all("timestamp" in event for event in trace)


def test_trace_contains_failure_event():
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(should_fail=True),
        observer,
    )

    boundary.execute("RUN-TRACE-2", {"order_id": "ORD-4"})

    trace = observer.get_trace("RUN-TRACE-2")
    event_types = [event["event_type"] for event in trace]

    assert "dependency_call_started" in event_types
    assert "dependency_call_failed" in event_types
    failure_event = trace[-1]
    assert failure_event["error_type"] == "ConnectionError"


def test_secret_redaction_handles_nested_dictionaries_and_lists():
    original = {
        "username": "operator",
        "api_key": "secret-key",
        "metadata": {
            "access_token": "secret-token",
            "items": [
                {"password": "secret-password"},
                {"value": "visible"},
            ],
        },
    }

    cleaned = redact_secrets(original)

    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["metadata"]["access_token"] == "[REDACTED]"
    assert cleaned["metadata"]["items"][0]["password"] == "[REDACTED]"
    assert cleaned["metadata"]["items"][1]["value"] == "visible"

    # Redaction must not mutate the original input.
    assert original["api_key"] == "secret-key"


def test_secrets_are_redacted_in_recorded_trace():
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(),
        observer,
    )

    boundary.execute(
        "RUN-SECRET-1",
        {
            "api_key": "do-not-log-this",
            "nested": {"password": "also-secret"},
        },
    )

    trace_text = json.dumps(observer.get_trace("RUN-SECRET-1"))

    assert "do-not-log-this" not in trace_text
    assert "also-secret" not in trace_text
    assert "[REDACTED]" in trace_text


def test_trace_export_is_valid_jsonl_and_contains_redaction(tmp_path):
    observer = IntegrationObserver()
    boundary = IntegrationBoundary(
        FakeExternalServiceAdapter(),
        observer,
    )

    boundary.execute(
        "RUN-EXPORT-1",
        {"authorization": "Bearer private-value"},
    )

    trace_file = tmp_path / "trace.jsonl"
    observer.export_jsonl(trace_file)

    lines = trace_file.read_text(encoding="utf-8").splitlines()
    exported_events = [json.loads(line) for line in lines]

    assert len(exported_events) == 2
    assert all("event_type" in event for event in exported_events)

    exported_text = trace_file.read_text(encoding="utf-8")
    assert "Bearer private-value" not in exported_text
    assert "[REDACTED]" in exported_text


def test_status_function_returns_unknown_for_missing_run():
    observer = IntegrationObserver()

    assert observer.get_status("UNKNOWN-RUN") == "unknown"


def test_metrics_average_is_zero_without_calls():
    metrics = DependencyMetrics()

    assert metrics.average_duration_ms == 0.0
    assert metrics.to_dict()["calls"] == 0


def test_task4_demo_creates_report_metrics_and_trace(tmp_path):
    output_dir = tmp_path / "outputs"
    trace_dir = tmp_path / "traces"

    report = run_task4_demo(output_dir, trace_dir)

    assert report["success_scenario"]["status"] == "completed"
    assert report["failure_scenario"]["status"] == "failed"
    assert report["metrics"]["calls"] == 2
    assert report["metrics"]["successes"] == 1
    assert report["metrics"]["failures"] == 1

    assert (output_dir / "task4_metrics.json").exists()
    assert (output_dir / "task4_measurement_report.json").exists()
    assert (trace_dir / "task4_integration_trace.jsonl").exists()
