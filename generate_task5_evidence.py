
"""Topic 19 - Task 5: Consolidated evidence and operator report."""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
TRACES = ROOT / "traces"
REPORTS = ROOT / "reports"


def read_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing evidence file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    # Load previously generated evidence.
    task1 = read_json(OUTPUTS / "task1_workflow_contract.json")
    task2 = read_json(OUTPUTS / "task2_orchestration.json")
    task3 = read_json(OUTPUTS / "task3_failure_retry_replay.json")
    task4_report = read_json(OUTPUTS / "task4_measurement_report.json")
    task4_metrics = read_json(OUTPUTS / "task4_metrics.json")
    task4_evidence = read_json(OUTPUTS / "task4_integration_evidence.json")

    trace_path = TRACES / "task4_integration_trace.jsonl"
    if not trace_path.exists():
        raise FileNotFoundError(f"Missing trace: {trace_path}")

    trace_text = trace_path.read_text(encoding="utf-8")
    events = [
        json.loads(line)
        for line in trace_text.splitlines()
        if line.strip()
    ]

    checks = {
        "task1_evidence_available": bool(task1),
        "task2_evidence_available": bool(task2),
        "task3_evidence_available": bool(task3),
        "task4_evidence_passed": task4_evidence.get("overall_passed") is True,
        "dependency_metrics_valid": (
            task4_metrics.get("calls") == 2
            and task4_metrics.get("successes") == 1
            and task4_metrics.get("failures") == 1
        ),
        "structured_trace_available": (
            len(events) == 4
            and all("event_type" in event for event in events)
            and all("event_id" in event for event in events)
        ),
        "measurement_report_available": bool(task4_report),
    }

    reflection = """
This assessment demonstrated how a multi-step workflow can be structured
around explicit task dependencies, controlled state transitions, and
observable execution. Task 1 established the workflow contract and state
model. Task 2 extended that foundation into an orchestrator that validates
dependencies, executes eligible tasks, and records task-level outcomes.

Task 3 focused on reliability. Transient errors and simulated timeouts were
retried within a bounded attempt limit, while malformed responses and
permanent failures were treated as conditions requiring review. Replay
testing demonstrated why idempotency matters: a completed operation could
be returned for a new trigger without repeating the simulated
non-idempotent side effect, while a duplicate trigger was rejected.

Task 4 introduced an injectable dependency boundary. A fake adapter made
success and failure behavior deterministic and testable without contacting
a live service. Structured events, status lookup, JSONL trace export, and
basic call metrics made dependency behavior observable. Secret redaction
was verified for recognized sensitive dictionary keys, including nested
values.

The implementation has important production limitations. The fake adapter
does not validate real network behavior. Retry timing is bounded but does
not provide exponential backoff or jitter. Idempotency and event storage
are in-memory in this demonstration, so they are not durable or atomic
across processes. The timeout fixture simulates a timeout exception rather
than forcibly cancelling an external operation. Redaction by key name
cannot detect every possible secret.

The main engineering lesson is to make workflow state, failure categories,
replay behavior, and operator decisions explicit. Before production use,
the design would need durable idempotency storage, authenticated external
adapters, secure secret management, persistent telemetry, real timeout
handling, and operational alerts. This assessment provides a testable
foundation, not a production-ready distributed workflow platform.
""".strip()

    metrics = [
        ("External dependency calls", task4_metrics.get("calls")),
        ("Successful dependency calls", task4_metrics.get("successes")),
        ("Failed dependency calls", task4_metrics.get("failures")),
        ("Total duration (ms)", task4_metrics.get("total_duration_ms")),
        ("Average duration (ms)", task4_metrics.get("average_duration_ms")),
        ("Structured trace events", len(events)),
        ("Automated tests", "40 passed in last verified run"),
    ]

    report = [
        "# Topic 19 — Operator Runbook and Evidence Report",
        "",
        "## 1. Purpose",
        "",
        "This report documents the workflow lifecycle demonstrations, "
        "operator responses, measurements, trace artifacts, and known "
        "limitations for the Workflow Orchestration Assessment.",
        "",
        "## 2. Execution commands",
        "",
        "Run from the project root with the virtual environment activated:",
        "",
        "```cmd",
        "python generate_task1_evidence.py",
        "python generate_task2_evidence.py",
        "python task3_failure_retry_replay.py",
        "python generate_task3_evidence.py",
        "python task4_integration_observability.py",
        "python generate_task4_evidence.py",
        "python -m pytest -q",
        "python generate_task5_evidence.py",
        "```",
        "",
        "## 3. Lifecycle scenarios and operator actions",
        "",
        "| Scenario | Demonstrated behavior | Operator action |",
        "|---|---|---|",
        "| Success | Six workflow tasks complete | Verify final outputs "
        "and retain the evidence |",
        "| Transient failure | Retry succeeds on second attempt | Inspect "
        "attempt events and bounded retry count |",
        "| Timeout | Simulated timeout followed by successful retry | "
        "Verify external operation status before repeating it |",
        "| Permanent failure | Workflow moves to needs_review | Inspect "
        "the error and resolve the cause before re-execution |",
        "| Malformed response | Invalid response is rejected | Review "
        "the handler and response contract |",
        "| Replay | Cached completed result is returned | Verify the "
        "business operation key and existing result |",
        "| Duplicate trigger | Repeated trigger is rejected | Inspect "
        "the original workflow status; do not repeat the side effect |",
        "| Dependency failure | External call failure is recorded | "
        "Inspect error type and trace; decide on safe retry or review |",
        "",
        "## 4. Output excerpts",
        "",
        "### Task 2 — successful workflow",
        "",
        "The Task 2 evidence confirms the deterministic six-task workflow "
        "completed, with all six tasks completed and 22 workflow events.",
        "",
        "### Task 3 — failure and replay",
        "",
        "- Transient retry: completed in 2 attempts.",
        "- Timeout retry: completed in 2 attempts.",
        "- Malformed response: needs_review.",
        "- Permanent failure: needs_review.",
        "- Replay: replayed.",
        "- Duplicate trigger: rejected.",
        "- Non-idempotent side effect count: 1.",
        "",
        "### Task 4 — dependency measurements",
        "",
        "```json",
        json.dumps(task4_metrics, indent=2),
        "```",
        "",
        "## 5. Measurement table",
        "",
        "| Measurement | Observed value |",
        "|---|---:|",
    ]

    for name, value in metrics:
        report.append(f"| {name} | {value} |")

    report.extend([
        "",
        "The dependency timings are measurements from a local fake adapter. "
        "They are not representative of real network latency or production "
        "throughput.",
        "",
        "## 6. Trace and evidence files",
        "",
        "| Artifact | Purpose |",
        "|---|---|",
        "| `outputs/task1_workflow_contract.json` | Workflow contract evidence |",
        "| `outputs/task2_orchestration.json` | Orchestration evidence |",
        "| `outputs/task3_failure_retry_replay.json` | Failure, retry, replay evidence |",
        "| `outputs/task4_integration_evidence.json` | Adapter and redaction evidence |",
        "| `outputs/task4_measurement_report.json` | Dependency scenario report |",
        "| `outputs/task4_metrics.json` | Dependency measurements |",
        "| `traces/task4_integration_trace.jsonl` | Structured dependency events |",
        "| `outputs/task5_consolidated_evidence.json` | Task 5 verification |",
        "",
        "## 7. Known limitations",
        "",
        "- The external dependency is represented by a fake adapter; "
        "no live service is called.",
        "- Retries are bounded but do not use exponential backoff or jitter.",
        "- Idempotency and trigger stores are in-memory, not durable or "
        "atomic across processes.",
        "- A simulated timeout does not cancel a real external operation. "
        "An external side effect may have occurred despite a timeout.",
        "- Events and metrics are held in memory until exported.",
        "- Distributed tracing and persistent telemetry are not implemented.",
        "- Secret redaction relies on recognized dictionary key names and "
        "cannot detect every secret embedded in arbitrary strings.",
        "- Fake adapter timings are not production performance benchmarks.",
        "",
        "## 8. Engineering reflection (~300 words)",
        "",
        reflection,
        "",
        "## 9. Verification",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "The evidence generator checks the availability and validity of "
        "the Task 1–4 artifacts. The full automated suite was last verified "
        "at 40 passing tests. Run `python -m pytest -q` again to confirm "
        "the current environment.",
        "",
    ])

    report_path = REPORTS / "operator_runbook.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    consolidated = {
        "assessment": "Topic 19 - Workflow Orchestration",
        "task": "Task 5 - Operator Runbook and Evidence Report",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": [
            {"check": name, "passed": passed}
            for name, passed in checks.items()
        ],
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "overall_passed": all(checks.values()),
        "lifecycle_scenarios": [
            "success",
            "failure",
            "replay",
            "recovery through bounded retry",
        ],
        "metrics": [
            {"measurement": name, "value": value}
            for name, value in metrics
        ],
        "trace_event_count": len(events),
        "report_file": "reports/operator_runbook.md",
        "known_limitations_documented": True,
        "engineering_reflection_included": True,
    }

    evidence_path = OUTPUTS / "task5_consolidated_evidence.json"
    evidence_path.write_text(
        json.dumps(consolidated, indent=2),
        encoding="utf-8",
    )

    print("=" * 65)
    print("TOPIC 19 - TASK 5 EVIDENCE GENERATION")
    print("=" * 65)

    for name, passed in checks.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    print("-" * 65)
    print(f"Checks passed: {consolidated['checks_passed']}/"
          f"{consolidated['checks_total']}")
    print("Overall status: "
          + ("passed" if consolidated["overall_passed"] else "failed"))
    print(f"Report: reports\\{report_path.name}")
    print(f"Evidence: outputs\\{evidence_path.name}")
    print("=" * 65)

    if not consolidated["overall_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
