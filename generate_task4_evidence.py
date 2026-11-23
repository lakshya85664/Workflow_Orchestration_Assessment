
"""Topic 19 - Task 4 evidence generation."""

import json
from pathlib import Path

from task4_integration_observability import run_task4_demo


def main():
    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    trace_dir = root / "traces"

    print("=" * 65)
    print("TOPIC 19 - TASK 4 EVIDENCE GENERATION")
    print("=" * 65)

    # Regenerate the report, metrics, and trace from deterministic fixtures.
    report = run_task4_demo(output_dir, trace_dir)

    metrics_path = output_dir / "task4_metrics.json"
    report_path = output_dir / "task4_measurement_report.json"
    trace_path = trace_dir / "task4_integration_trace.jsonl"

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))

    trace_lines = trace_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in trace_lines]
    trace_text = trace_path.read_text(encoding="utf-8")

    checks = {
        "success_scenario_completed": (
            report["success_scenario"]["status"] == "completed"
        ),
        "failure_scenario_observed": (
            report["failure_scenario"]["status"] == "failed"
            and report["failure_scenario"]["error_type"] == "ConnectionError"
        ),
        "metrics_counted_correctly": (
            metrics["calls"] == 2
            and metrics["successes"] == 1
            and metrics["failures"] == 1
        ),
        "structured_trace_events_exported": (
            len(events) == 4
            and all("event_id" in event for event in events)
            and all("timestamp" in event for event in events)
            and all("event_type" in event for event in events)
        ),
        "success_and_failure_events_present": (
            any(
                event["event_type"] == "dependency_call_succeeded"
                for event in events
            )
            and any(
                event["event_type"] == "dependency_call_failed"
                for event in events
            )
        ),
        "secret_redacted_in_trace": (
            "demo-secret-value" not in trace_text
            and "[REDACTED]" in trace_text
        ),
        "status_results_recorded": (
            saved_report["status_checks"]["success_run"] == "completed"
            and saved_report["status_checks"]["failure_run"] == "failed"
        ),
        "all_deliverable_files_exist": (
            metrics_path.exists()
            and report_path.exists()
            and trace_path.exists()
        ),
    }

    evidence = {
        "assessment": "Topic 19 - Task 4",
        "task": "Integration Boundary and Observability",
        "checks": [
            {"check": name, "passed": passed}
            for name, passed in checks.items()
        ],
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "overall_passed": all(checks.values()),
        "metrics": metrics,
        "trace_event_count": len(events),
        "deliverables": [
            "outputs/task4_metrics.json",
            "outputs/task4_measurement_report.json",
            "traces/task4_integration_trace.jsonl",
        ],
    }

    evidence_path = output_dir / "task4_integration_evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )

    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    print("-" * 65)
    print(f"Checks passed: {evidence['checks_passed']}/{len(checks)}")
    print(
        "Overall status: "
        + ("passed" if evidence["overall_passed"] else "failed")
    )
    print(f"Evidence file: outputs\\{evidence_path.name}")
    print("=" * 65)

    if not evidence["overall_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
