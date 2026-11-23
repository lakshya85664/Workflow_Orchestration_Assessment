
"""
Topic 19 - Task 3
Failure, Retry, and Replay Safety

Features:
- Error classification
- Bounded retries
- Timeout handling
- Malformed response handling
- Permanent failure handling
- Duplicate trigger protection
- Idempotent side-effect protection
- Explicit next-action decisions

All fixtures use local synthetic data.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from workflow_orchestration_assessment import (
    WorkflowRun,
    WorkflowTask,
    WorkflowState,
    TaskState,
    EventType,
    transition,
)


# ============================================================
# ERROR TYPES
# ============================================================

class TransientWorkflowError(Exception):
    """An error that may succeed when retried."""


class PermanentWorkflowError(Exception):
    """An error that should not be retried."""


class TaskTimeoutError(TransientWorkflowError):
    """A task exceeded its declared execution time."""


class MalformedResponseError(PermanentWorkflowError):
    """A handler returned a response outside its contract."""


class DuplicateTriggerError(Exception):
    """A workflow trigger was already processed."""


# ============================================================
# RESULT CONTRACT
# ============================================================

@dataclass
class Task3Result:
    status: str
    error_type: str | None
    attempts: int
    next_action: str
    result: Any = None
    retry_trace: list[dict[str, Any]] = field(default_factory=list)


# ============================================================
# IDEMPOTENCY STORE
# ============================================================

class IdempotencyStore:
    """
    In-memory idempotency store for this assessment.

    Successful operations are stored against business_key
    and task_id. Replays return the stored result rather than
    repeating the side effect.

    Production systems should use durable storage with an
    atomic uniqueness constraint.
    """

    def __init__(self):
        self.completed_operations: dict[tuple[str, str], Any] = {}
        self.processed_triggers: set[str] = set()

    def get(self, business_key: str, task_id: str):
        return self.completed_operations.get((business_key, task_id))

    def contains(self, business_key: str, task_id: str) -> bool:
        return (business_key, task_id) in self.completed_operations

    def save(self, business_key: str, task_id: str, result: Any):
        self.completed_operations[(business_key, task_id)] = result

    def claim_trigger(self, trigger_id: str) -> bool:
        """
        Return False when a trigger has already been processed.
        """
        if trigger_id in self.processed_triggers:
            return False

        self.processed_triggers.add(trigger_id)
        return True


# ============================================================
# ERROR CLASSIFICATION
# ============================================================

def classify_error(error: Exception) -> dict[str, str]:
    """Classify an error and return an explicit recovery action."""

    if isinstance(error, TaskTimeoutError):
        return {
            "category": "timeout",
            "retryable": "true",
            "next_action": "retry_with_idempotency_check",
        }

    if isinstance(error, TransientWorkflowError):
        return {
            "category": "transient",
            "retryable": "true",
            "next_action": "retry_with_idempotency_check",
        }

    if isinstance(error, MalformedResponseError):
        return {
            "category": "malformed_response",
            "retryable": "false",
            "next_action": "review_handler_contract",
        }

    if isinstance(error, PermanentWorkflowError):
        return {
            "category": "permanent",
            "retryable": "false",
            "next_action": "operator_review",
        }

    return {
        "category": "unknown",
        "retryable": "false",
        "next_action": "operator_review",
    }


# ============================================================
# TASK 3 EXECUTOR
# ============================================================

class SafeTaskExecutor:
    """
    Execute one workflow task with bounded retries and replay safety.

    A handler must raise TaskTimeoutError when its timeout
    contract is exceeded.

    This executor does not forcibly cancel an already-running
    thread, process, or external network operation.
    """

    def __init__(
        self,
        run: WorkflowRun,
        idempotency_store: IdempotencyStore | None = None,
    ):
        self.run = run
        self.idempotency_store = (
            idempotency_store or IdempotencyStore()
        )

    def execute(
        self,
        task_id: str,
        handler: Callable[[WorkflowRun], Any],
        trigger_id: str,
        response_validator: Callable[[Any], bool] | None = None,
    ) -> Task3Result:

        # ----------------------------------------------------
        # Boundary validation
        # ----------------------------------------------------

        if task_id not in self.run.tasks:
            return Task3Result(
                status="rejected",
                error_type="UnknownTask",
                attempts=0,
                next_action="register_or_correct_task_id",
            )

        if not isinstance(trigger_id, str) or not trigger_id.strip():
            return Task3Result(
                status="rejected",
                error_type="InvalidTrigger",
                attempts=0,
                next_action="provide_valid_trigger_id",
            )

        task = self.run.tasks[task_id]
        business_key = self.run.business_key

        # ----------------------------------------------------
        # 1. Duplicate trigger check
        # ----------------------------------------------------
        # This check must happen BEFORE the cached-result check.
        # Reusing the same trigger ID is rejected.

        if not self.idempotency_store.claim_trigger(trigger_id):
            self.run.record(
                "duplicate_trigger_rejected",
                task_id=task_id,
                trigger_id=trigger_id,
            )

            return Task3Result(
                status="rejected",
                error_type="DuplicateTriggerError",
                attempts=task.attempts,
                next_action="return_existing_workflow_status",
            )

        # ----------------------------------------------------
        # 2. Idempotent replay check
        # ----------------------------------------------------
        # A different trigger may safely retrieve an already
        # completed result without executing the handler again.

        if self.idempotency_store.contains(business_key, task_id):
            cached = self.idempotency_store.get(
                business_key,
                task_id,
            )

            self.run.record(
                "duplicate_operation_replayed",
                task_id=task_id,
                trigger_id=trigger_id,
            )

            return Task3Result(
                status="replayed",
                error_type=None,
                attempts=task.attempts,
                next_action="none",
                result=cached,
            )

        # ----------------------------------------------------
        # 3. Existing task-state boundaries
        # ----------------------------------------------------

        if task.state == TaskState.COMPLETED:
            return Task3Result(
                status="replayed",
                error_type=None,
                attempts=task.attempts,
                next_action="none",
                result=task.result,
            )

        if task.state == TaskState.FAILED:
            return Task3Result(
                status="rejected",
                error_type=task.error_type or "PreviousFailure",
                attempts=task.attempts,
                next_action="operator_review",
            )

        if task.max_attempts < 1:
            return Task3Result(
                status="rejected",
                error_type="InvalidRetryLimit",
                attempts=0,
                next_action="correct_task_retry_configuration",
            )

        # ----------------------------------------------------
        # 4. Start workflow if necessary
        # ----------------------------------------------------

        if self.run.state == WorkflowState.CREATED:
            transition(self.run, "start")

        trace = []

        # ----------------------------------------------------
        # 5. Bounded retry loop
        # ----------------------------------------------------

        for attempt in range(1, task.max_attempts + 1):

            task.attempts = attempt
            task.state = TaskState.RUNNING
            self.run.steps_executed += 1

            self.run.record(
                EventType.TASK_STARTED.value,
                task_id=task_id,
                attempt=attempt,
                trigger_id=trigger_id,
            )

            try:
                response = handler(self.run)

                # Validate response before accepting success.
                if response_validator is not None:
                    if not response_validator(response):
                        raise MalformedResponseError(
                            "Handler response failed validation"
                        )

                if response is None:
                    raise MalformedResponseError(
                        "Handler returned no response"
                    )

                # Persist success before returning to caller.
                self.idempotency_store.save(
                    business_key,
                    task_id,
                    response,
                )

                task.result = response
                task.state = TaskState.COMPLETED
                task.error_type = None

                self.run.record(
                    EventType.TASK_COMPLETED.value,
                    task_id=task_id,
                    attempt=attempt,
                )

                trace.append({
                    "attempt": attempt,
                    "outcome": "completed",
                })

                return Task3Result(
                    status="completed",
                    error_type=None,
                    attempts=attempt,
                    next_action="none",
                    result=response,
                    retry_trace=trace,
                )

            except Exception as error:

                classification = classify_error(error)

                trace.append({
                    "attempt": attempt,
                    "outcome": "failed",
                    "error_type": type(error).__name__,
                    "category": classification["category"],
                })

                task.error_type = type(error).__name__
                task.state = TaskState.FAILED

                self.run.record(
                    EventType.TASK_FAILED.value,
                    task_id=task_id,
                    attempt=attempt,
                    error_type=type(error).__name__,
                    error_category=classification["category"],
                )

                can_retry = (
                    classification["retryable"] == "true"
                    and attempt < task.max_attempts
                )

                if can_retry:
                    self.run.record(
                        EventType.RETRY_SCHEDULED.value,
                        task_id=task_id,
                        attempt=attempt,
                        next_attempt=attempt + 1,
                    )
                    continue

                if self.run.state == WorkflowState.RUNNING:
                    transition(self.run, "review")

                task.state = TaskState.FAILED

                if classification["retryable"] == "false":
                    next_action = classification["next_action"]
                else:
                    next_action = (
                        "retry_limit_reached_operator_review"
                    )

                return Task3Result(
                    status="needs_review",
                    error_type=type(error).__name__,
                    attempts=attempt,
                    next_action=next_action,
                    retry_trace=trace,
                )

        # Defensive boundary.
        return Task3Result(
            status="needs_review",
            error_type="RetryLimitReached",
            attempts=task.attempts,
            next_action="operator_review",
            retry_trace=trace,
        )


# ============================================================
# TASK 3 FAILURE FIXTURES
# ============================================================

def run_task3_fixtures() -> dict[str, Any]:
    """
    Run deterministic local fixtures for:
    - Transient failure followed by success
    - Timeout followed by success
    - Malformed response
    - Permanent failure
    - Duplicate trigger
    - Duplicate replay without repeating a side effect
    """

    results = {}

    # --------------------------------------------------------
    # Fixture 1: Transient failure followed by success
    # --------------------------------------------------------

    run = WorkflowRun(
        run_id="TASK3-RETRY-001",
        business_key="ORDER-RETRY-001",
        owner="task3_operator",
    )

    run.register_task(
        WorkflowTask(
            task_id="retry_task",
            name="Retry demonstration",
            owner="retry_worker",
            max_attempts=3,
        )
    )

    calls = {"count": 0}

    def transient_then_success(context):
        calls["count"] += 1

        if calls["count"] == 1:
            raise TransientWorkflowError(
                "Temporary service issue"
            )

        return {
            "success": True,
            "reference": "RETRY-001",
        }

    retry_result = SafeTaskExecutor(run).execute(
        "retry_task",
        transient_then_success,
        trigger_id="TRIGGER-RETRY-001",
        response_validator=lambda value: (
            isinstance(value, dict)
            and value.get("success") is True
        ),
    )

    results["retry"] = {
        "status": retry_result.status,
        "attempts": retry_result.attempts,
        "next_action": retry_result.next_action,
        "trace": retry_result.retry_trace,
    }

    # --------------------------------------------------------
    # Fixture 2: Timeout followed by success
    # --------------------------------------------------------

    timeout_run = WorkflowRun(
        run_id="TASK3-TIMEOUT-001",
        business_key="ORDER-TIMEOUT-001",
        owner="task3_operator",
    )

    timeout_run.register_task(
        WorkflowTask(
            task_id="timeout_task",
            name="Timeout demonstration",
            owner="timeout_worker",
            max_attempts=2,
        )
    )

    timeout_calls = {"count": 0}

    def timeout_then_success(context):
        timeout_calls["count"] += 1

        if timeout_calls["count"] == 1:
            raise TaskTimeoutError(
                "Declared timeout exceeded"
            )

        return {
            "success": True,
            "reference": "TIMEOUT-001",
        }

    timeout_result = SafeTaskExecutor(timeout_run).execute(
        "timeout_task",
        timeout_then_success,
        trigger_id="TRIGGER-TIMEOUT-001",
        response_validator=lambda value: (
            isinstance(value, dict)
            and value.get("success") is True
        ),
    )

    results["timeout"] = {
        "status": timeout_result.status,
        "attempts": timeout_result.attempts,
        "next_action": timeout_result.next_action,
        "trace": timeout_result.retry_trace,
    }

    # --------------------------------------------------------
    # Fixture 3: Malformed response
    # --------------------------------------------------------

    malformed_run = WorkflowRun(
        run_id="TASK3-MALFORMED-001",
        business_key="ORDER-MALFORMED-001",
        owner="task3_operator",
    )

    malformed_run.register_task(
        WorkflowTask(
            task_id="malformed_task",
            name="Malformed response demonstration",
            owner="response_worker",
            max_attempts=3,
        )
    )

    malformed_result = SafeTaskExecutor(malformed_run).execute(
        "malformed_task",
        lambda context: {"unexpected": "shape"},
        trigger_id="TRIGGER-MALFORMED-001",
        response_validator=lambda value: (
            isinstance(value, dict)
            and "success" in value
        ),
    )

    results["malformed_response"] = {
        "status": malformed_result.status,
        "error_type": malformed_result.error_type,
        "attempts": malformed_result.attempts,
        "next_action": malformed_result.next_action,
    }

    # --------------------------------------------------------
    # Fixture 4: Permanent failure
    # --------------------------------------------------------

    permanent_run = WorkflowRun(
        run_id="TASK3-PERMANENT-001",
        business_key="ORDER-PERMANENT-001",
        owner="task3_operator",
    )

    permanent_run.register_task(
        WorkflowTask(
            task_id="permanent_task",
            name="Permanent failure demonstration",
            owner="permanent_worker",
            max_attempts=3,
        )
    )

    permanent_calls = {"count": 0}

    def permanent_failure(context):
        permanent_calls["count"] += 1

        raise PermanentWorkflowError(
            "Business rule rejected request"
        )

    permanent_result = SafeTaskExecutor(permanent_run).execute(
        "permanent_task",
        permanent_failure,
        trigger_id="TRIGGER-PERMANENT-001",
    )

    results["permanent_failure"] = {
        "status": permanent_result.status,
        "error_type": permanent_result.error_type,
        "attempts": permanent_result.attempts,
        "handler_calls": permanent_calls["count"],
        "next_action": permanent_result.next_action,
    }

    # --------------------------------------------------------
    # Fixture 5: Replay and duplicate-trigger safety
    # --------------------------------------------------------

    replay_run = WorkflowRun(
        run_id="TASK3-REPLAY-001",
        business_key="ORDER-REPLAY-001",
        owner="task3_operator",
    )

    replay_run.register_task(
        WorkflowTask(
            task_id="charge_task",
            name="Synthetic non-idempotent charge",
            owner="payment_worker",
            max_attempts=2,
        )
    )

    store = IdempotencyStore()

    side_effects = {
        "charge_count": 0,
    }

    def synthetic_charge(context):
        side_effects["charge_count"] += 1

        return {
            "charged": True,
            "charge_reference": "CHARGE-001",
        }

    executor = SafeTaskExecutor(
        replay_run,
        store,
    )

    # First trigger executes the operation.
    first = executor.execute(
        "charge_task",
        synthetic_charge,
        trigger_id="TRIGGER-CHARGE-001",
    )

    # A different trigger retrieves the cached result.
    replay = executor.execute(
        "charge_task",
        synthetic_charge,
        trigger_id="TRIGGER-CHARGE-REPLAY-001",
    )

    # Reusing the same trigger must be rejected.
    duplicate = executor.execute(
        "charge_task",
        synthetic_charge,
        trigger_id="TRIGGER-CHARGE-REPLAY-001",
    )

    results["replay_safety"] = {
        "first_status": first.status,
        "replay_status": replay.status,
        "duplicate_status": duplicate.status,
        "side_effect_count": side_effects["charge_count"],
        "next_action": duplicate.next_action,
    }

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import json

    print("TASK 3 - FAILURE, RETRY, AND REPLAY SAFETY")
    print("=" * 60)

    output = run_task3_fixtures()

    print(json.dumps(output, indent=2))
