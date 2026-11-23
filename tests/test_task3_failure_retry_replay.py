
import pytest

from workflow_orchestration_assessment import (
    WorkflowRun,
    WorkflowTask,
    WorkflowState,
    TaskState,
)

from task3_failure_retry_replay import (
    SafeTaskExecutor,
    IdempotencyStore,
    TransientWorkflowError,
    PermanentWorkflowError,
    TaskTimeoutError,
    MalformedResponseError,
    classify_error,
    run_task3_fixtures,
)


def create_run(task_id="task1", max_attempts=3):
    run = WorkflowRun(
        run_id="TEST-TASK3-001",
        business_key="TEST-ORDER-001",
        owner="test_operator",
    )

    run.register_task(
        WorkflowTask(
            task_id=task_id,
            name="Task 3 test task",
            owner="test_worker",
            max_attempts=max_attempts,
        )
    )

    return run


def test_transient_error_retries_and_succeeds():
    run = create_run()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1

        if calls["count"] == 1:
            raise TransientWorkflowError("Temporary error")

        return {"success": True}

    result = SafeTaskExecutor(run).execute(
        "task1",
        handler,
        "trigger-1",
    )

    assert result.status == "completed"
    assert result.attempts == 2
    assert calls["count"] == 2
    assert result.next_action == "none"


def test_timeout_error_is_retryable():
    run = create_run()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1

        if calls["count"] == 1:
            raise TaskTimeoutError("Timeout")

        return {"success": True}

    result = SafeTaskExecutor(run).execute(
        "task1",
        handler,
        "trigger-timeout",
    )

    assert result.status == "completed"
    assert result.attempts == 2


def test_retry_limit_is_enforced():
    run = create_run(max_attempts=2)
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        raise TransientWorkflowError("Still unavailable")

    result = SafeTaskExecutor(run).execute(
        "task1",
        handler,
        "trigger-limit",
    )

    assert result.status == "needs_review"
    assert result.attempts == 2
    assert calls["count"] == 2
    assert result.next_action == (
        "retry_limit_reached_operator_review"
    )


def test_permanent_error_is_not_retried():
    run = create_run()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        raise PermanentWorkflowError("Business rejection")

    result = SafeTaskExecutor(run).execute(
        "task1",
        handler,
        "trigger-permanent",
    )

    assert result.status == "needs_review"
    assert result.attempts == 1
    assert calls["count"] == 1
    assert result.next_action == "operator_review"


def test_malformed_response_is_rejected():
    run = create_run()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        return {"unexpected": "value"}

    result = SafeTaskExecutor(run).execute(
        "task1",
        handler,
        "trigger-malformed",
        response_validator=lambda value: (
            isinstance(value, dict) and "success" in value
        ),
    )

    assert result.status == "needs_review"
    assert result.error_type == "MalformedResponseError"
    assert result.attempts == 1
    assert calls["count"] == 1
    assert result.next_action == "review_handler_contract"


def test_duplicate_trigger_is_rejected():
    run = create_run()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        return {"success": True}

    executor = SafeTaskExecutor(run)

    first = executor.execute(
        "task1",
        handler,
        "same-trigger",
    )

    second = executor.execute(
        "task1",
        handler,
        "same-trigger",
    )

    assert first.status == "completed"
    assert second.status == "rejected"
    assert second.error_type == "DuplicateTriggerError"
    assert calls["count"] == 1


def test_new_trigger_replays_cached_result_without_side_effect():
    run = create_run()
    store = IdempotencyStore()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        return {"reference": "PAYMENT-001"}

    executor = SafeTaskExecutor(run, store)

    first = executor.execute(
        "task1",
        handler,
        "trigger-first",
    )

    replay = executor.execute(
        "task1",
        handler,
        "trigger-second",
    )

    assert first.status == "completed"
    assert replay.status == "replayed"
    assert replay.result == {"reference": "PAYMENT-001"}
    assert calls["count"] == 1


def test_duplicate_trigger_after_replay_is_rejected():
    run = create_run()
    store = IdempotencyStore()
    calls = {"count": 0}

    def handler(context):
        calls["count"] += 1
        return {"success": True}

    executor = SafeTaskExecutor(run, store)

    executor.execute("task1", handler, "trigger-first")

    replay = executor.execute(
        "task1",
        handler,
        "trigger-second",
    )

    duplicate = executor.execute(
        "task1",
        handler,
        "trigger-second",
    )

    assert replay.status == "replayed"
    assert duplicate.status == "rejected"
    assert calls["count"] == 1


def test_unknown_task_is_rejected():
    run = create_run()

    result = SafeTaskExecutor(run).execute(
        "unknown_task",
        lambda context: {"success": True},
        "trigger-unknown",
    )

    assert result.status == "rejected"
    assert result.error_type == "UnknownTask"
    assert result.attempts == 0


def test_empty_trigger_is_rejected():
    run = create_run()

    result = SafeTaskExecutor(run).execute(
        "task1",
        lambda context: {"success": True},
        "   ",
    )

    assert result.status == "rejected"
    assert result.error_type == "InvalidTrigger"
    assert result.attempts == 0


def test_error_classification():
    assert classify_error(TransientWorkflowError())["category"] == "transient"
    assert classify_error(TaskTimeoutError())["category"] == "timeout"
    assert classify_error(PermanentWorkflowError())["category"] == "permanent"
    assert classify_error(MalformedResponseError())["category"] == "malformed_response"


def test_task3_fixtures_cover_expected_scenarios():
    results = run_task3_fixtures()

    assert results["retry"]["status"] == "completed"
    assert results["retry"]["attempts"] == 2

    assert results["timeout"]["status"] == "completed"
    assert results["timeout"]["attempts"] == 2

    assert results["malformed_response"]["status"] == "needs_review"
    assert results["permanent_failure"]["attempts"] == 1

    assert results["replay_safety"]["first_status"] == "completed"
    assert results["replay_safety"]["replay_status"] == "replayed"
    assert results["replay_safety"]["duplicate_status"] == "rejected"
    assert results["replay_safety"]["side_effect_count"] == 1
