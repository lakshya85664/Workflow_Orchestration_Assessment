
"""
Topic 19 - Task 3
Evidence Generator

Generates a JSON evidence report for:
- Transient retry
- Timeout retry
- Malformed response handling
- Permanent failure handling
- Duplicate trigger rejection
- Idempotent replay protection
"""

import json
from pathlib import Path

from task3_failure_retry_replay import run_task3_fixtures


def generate_evidence():
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = run_task3_fixtures()

    checks = {
        "transient_retry_succeeded": (
            results["retry"]["status"] == "completed"
            and results["retry"]["attempts"] == 2
        ),
        "timeout_retry_succeeded": (
            results["timeout"]["status"] == "completed"
            and results["timeout"]["attempts"] == 2
        ),
        "malformed_response_rejected": (
            results["malformed_response"]["status"] == "needs_review"
            and results["malformed_response"]["attempts"] == 1
        ),
        "permanent_failure_not_retried": (
            results["permanent_failure"]["status"] == "needs_review"
            and results["permanent_failure"]["attempts"] == 1
            and results["permanent_failure"]["handler_calls"] == 1
        ),
        "successful_operation_replayed": (
            results["replay_safety"]["first_status"] == "completed"
            and results["replay_safety"]["replay_status"] == "replayed"
        ),
        "duplicate_trigger_rejected": (
            results["replay_safety"]["duplicate_status"] == "rejected"
        ),
        "non_idempotent_side_effect_executed_once": (
            results["replay_safety"]["side_effect_count"] == 1
        ),
        "explicit_recovery_actions_present": (
            results["malformed_response"]["next_action"]
            == "review_handler_contract"
            and results["permanent_failure"]["next_action"]
            == "operator_review"
        ),
    }

    passed = sum(checks.values())
    total = len(checks)

    evidence = {
        "assessment": "Topic 19 - Workflow Orchestration",
        "task": 3,
        "title": "Failure, Retry, and Replay Safety",
        "overall_status": "passed" if passed == total else "failed",
        "checks_passed": passed,
        "checks_total": total,
        "checks": checks,
        "scenario_results": results,
        "limitations": [
            "Timeout behavior is simulated through a declared timeout exception.",
            "The executor does not forcibly cancel an already-running operation.",
            "The idempotency store is in-memory and is not durable across process restarts.",
            "Production idempotency requires durable storage and atomic uniqueness enforcement.",
        ],
    }

    output_path = output_dir / "task3_failure_retry_replay.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(evidence, file, indent=4)

    print("=" * 65)
    print("TOPIC 19 - TASK 3 EVIDENCE GENERATION")
    print("=" * 65)

    for name, passed_check in checks.items():
        status = "PASS" if passed_check else "FAIL"
        print(f"[{status}] {name}")

    print("-" * 65)
    print(f"Checks passed: {passed}/{total}")
    print(f"Overall status: {evidence['overall_status']}")
    print(f"Evidence file: {output_path}")
    print("=" * 65)

    if passed != total:
        raise SystemExit("Task 3 evidence validation failed.")


if __name__ == "__main__":
    generate_evidence()
