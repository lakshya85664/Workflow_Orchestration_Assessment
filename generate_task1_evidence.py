
"""
Topic 19 - Task 1 Evidence Generator
"""

import json
from pathlib import Path

from workflow_orchestration_assessment import (
    WorkflowRun,
    WorkflowState,
    run_task1_fixture,
    transition,
)


def main():
    print("=" * 60)
    print("TASK 1 - WORKFLOW CONTRACT EVIDENCE")
    print("=" * 60)

    checks = []

    def record_check(name, passed, details):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "details": details,
        })
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}")
        print(f"       {details}")

    # Check 1: Runnable fixture
    fixture = run_task1_fixture()
    record_check(
        "fixture_created_and_started",
        fixture["status"] == "running",
        f"Workflow status: {fixture['status']}",
    )

    # Check 2: Task registry
    tasks = fixture["tasks"]
    record_check(
        "two_tasks_registered",
        len(tasks) == 2,
        f"Registered tasks: {len(tasks)}",
    )

    # Check 3: Dependency declaration
    dependency_valid = (
        tasks.get("task_2", {}).get("dependencies") == ["task_1"]
    )
    record_check(
        "task_dependency_declared",
        dependency_valid,
        "task_2 depends on task_1",
    )

    # Check 4: Legal transition
    legal_run = WorkflowRun(
        run_id="EVIDENCE-LEGAL-001",
        business_key="BUSINESS-EVIDENCE-001",
        owner="evidence_operator",
    )
    transition(legal_run, "start")

    record_check(
        "legal_transition_passed",
        legal_run.state == WorkflowState.RUNNING,
        f"State after start: {legal_run.state.value}",
    )

    # Check 5: Illegal transition
    illegal_run = WorkflowRun(
        run_id="EVIDENCE-ILLEGAL-001",
        business_key="BUSINESS-EVIDENCE-002",
        owner="evidence_operator",
    )

    illegal_rejected = False

    try:
        transition(illegal_run, "complete")
    except ValueError:
        illegal_rejected = True

    record_check(
        "illegal_transition_rejected",
        illegal_rejected and illegal_run.state == WorkflowState.CREATED,
        "Illegal transition rejected without changing workflow state",
    )

    # Check 6: Ownership information
    ownership_valid = (
        fixture["owner"] == "workflow_operator"
        and all(task["owner"] for task in tasks.values())
    )
    record_check(
        "workflow_and_task_ownership_present",
        ownership_valid,
        "Workflow and registered tasks have owners",
    )

    # Check 7: Structured event trace
    events_valid = (
        len(fixture["events"]) >= 4
        and all(
            event.get("event")
            and event.get("state")
            and event.get("timestamp")
            for event in fixture["events"]
        )
    )
    record_check(
        "structured_events_recorded",
        events_valid,
        f"Structured events: {len(fixture['events'])}",
    )

    passed = sum(item["passed"] for item in checks)
    total = len(checks)

    evidence = {
        "topic": "Topic 19 - Workflow Orchestration Assessment",
        "task": "Task 1 - Workflow Contract and State Model",
        "fixture": fixture,
        "checks": checks,
        "passed_checks": passed,
        "total_checks": total,
        "overall_passed": passed == total,
    }

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "task1_workflow_contract.json"
    output_file.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )

    print("-" * 60)
    print(f"Passed checks: {passed}/{total}")
    print(f"Evidence file: {output_file}")
    print(f"Overall result: {'PASS' if passed == total else 'FAIL'}")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
