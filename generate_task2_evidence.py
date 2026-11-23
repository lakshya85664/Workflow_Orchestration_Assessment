
"""
Topic 19 - Task 2 Evidence Generator
"""

import json
from pathlib import Path

from workflow_orchestration_assessment import (
    WorkflowRun,
    WorkflowTask,
    WorkflowState,
    WorkflowOrchestrator,
    WorkflowValidationError,
    run_topic2_fixture,
)


def main():
    print("=" * 60)
    print("TASK 2 - ORCHESTRATION IMPLEMENTATION EVIDENCE")
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

    # Run the deterministic happy path.
    result = run_topic2_fixture()

    record_check(
        "deterministic_workflow_completed",
        result["status"] == "completed",
        f"Workflow status: {result['status']}",
    )

    record_check(
        "all_six_tasks_completed",
        result["task_count"] == 6
        and result["completed_tasks"] == 6,
        (
            f"Completed {result['completed_tasks']} "
            f"of {result['task_count']} tasks"
        ),
    )

    record_check(
        "workflow_step_count_valid",
        result["steps_executed"] == 6,
        f"Steps executed: {result['steps_executed']}",
    )

    # Verify dependency relationships.
    tasks = result["tasks"]

    dependencies_valid = (
        tasks["check_inventory"]["dependencies"]
        == ["validate_order"]
        and tasks["reserve_inventory"]["dependencies"]
        == ["check_inventory"]
        and tasks["process_payment"]["dependencies"]
        == ["validate_order"]
        and set(tasks["create_shipment"]["dependencies"])
        == {"reserve_inventory", "process_payment"}
        and tasks["notify_customer"]["dependencies"]
        == ["create_shipment"]
    )

    record_check(
        "workflow_dependencies_valid",
        dependencies_valid,
        "All declared task dependencies match the workflow DAG",
    )

    # Verify the expected business outputs.
    outputs_valid = (
        tasks["validate_order"]["result"]["valid"] is True
        and tasks["check_inventory"]["result"]["available"] is True
        and tasks["reserve_inventory"]["result"]["reserved"] is True
        and tasks["process_payment"]["result"]["payment_status"]
        == "approved"
        and tasks["create_shipment"]["result"]["shipment_status"]
        == "created"
        and tasks["notify_customer"]["result"]["notification_status"]
        == "sent"
    )

    record_check(
        "business_task_outputs_valid",
        outputs_valid,
        "Validation, inventory, payment, shipment, and notification outputs verified",
    )

    # Verify structured workflow events.
    event_names = [
        event["event"] for event in result["events"]
    ]

    events_valid = (
        "workflow_started" in event_names
        and "task_started" in event_names
        and "task_completed" in event_names
        and "workflow_completed" in event_names
    )

    record_check(
        "workflow_events_recorded",
        events_valid,
        f"Recorded {len(event_names)} workflow events",
    )

    # Verify validation failure occurs before side effects.
    invalid_run = WorkflowRun(
        run_id="TASK2-INVALID-001",
        business_key="INVALID-BUSINESS-001",
        owner="evidence_operator",
    )

    invalid_run.register_task(
        WorkflowTask(
            task_id="task_a",
            name="Task A",
            owner="validation_service",
            dependencies=["missing_task"],
        )
    )

    side_effects = []

    invalid_orchestrator = WorkflowOrchestrator(
        run=invalid_run,
        task_handlers={
            "task_a": lambda context: side_effects.append(
                "side_effect_executed"
            )
        },
    )

    validation_rejected = False

    try:
        invalid_orchestrator.execute()
    except WorkflowValidationError:
        validation_rejected = True

    record_check(
        "invalid_workflow_rejected_before_execution",
        validation_rejected
        and not side_effects
        and invalid_run.state == WorkflowState.CREATED,
        "Invalid dependency rejected; no handler executed",
    )

    passed = sum(item["passed"] for item in checks)
    total = len(checks)

    evidence = {
        "topic": "Topic 19 - Workflow Orchestration Assessment",
        "task": "Task 2 - Workflow Orchestration Implementation",
        "workflow_result": result,
        "checks": checks,
        "passed_checks": passed,
        "total_checks": total,
        "overall_passed": passed == total,
    }

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "task2_orchestration.json"

    output_file.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )

    print("-" * 60)
    print(f"Passed checks: {passed}/{total}")
    print(f"Evidence file: {output_file}")
    print(
        f"Overall result: "
        f"{'PASS' if passed == total else 'FAIL'}"
    )

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
