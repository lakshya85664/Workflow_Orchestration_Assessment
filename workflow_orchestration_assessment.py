
"""
Topic 19 - Workflow Orchestration Assessment
Task 1: Workflow Contract and State Model
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================
# ENUMERATIONS
# ============================================================

class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    CANCELLED = "cancelled"


class TaskState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(str, Enum):
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    TASK_REGISTERED = "task_registered"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    RETRY_SCHEDULED = "retry_scheduled"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class WorkflowTask:
    task_id: str
    name: str
    owner: str
    dependencies: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    attempts: int = 0
    max_attempts: int = 3
    result: Any = None
    error_type: str | None = None

    def __post_init__(self):
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")

        if not self.name.strip():
            raise ValueError("task name cannot be empty")

        if not self.owner.strip():
            raise ValueError("task owner cannot be empty")

        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("Duplicate task dependencies are not allowed")


@dataclass
class WorkflowEvent:
    run_id: str
    event: str
    state: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class WorkflowResult:
    run_id: str
    business_key: str
    status: str
    task_results: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    next_action: str = "none"


@dataclass
class WorkflowTrace:
    run_id: str
    business_key: str
    state: str
    events: list[WorkflowEvent] = field(default_factory=list)
    task_states: dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowRun:
    run_id: str
    business_key: str
    owner: str
    state: WorkflowState = WorkflowState.CREATED
    attempts: int = 0
    max_attempts: int = 3
    max_steps: int = 20
    steps_executed: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    tasks: dict[str, WorkflowTask] = field(default_factory=dict)
    events: list[WorkflowEvent] = field(default_factory=list)

    def __post_init__(self):
        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty")

        if not self.business_key.strip():
            raise ValueError("business_key cannot be empty")

        if not self.owner.strip():
            raise ValueError("workflow owner cannot be empty")

        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")

    def record(self, event: str, **details: Any) -> WorkflowEvent:
        """Append a structured event to this workflow run."""
        workflow_event = WorkflowEvent(
            run_id=self.run_id,
            event=event,
            state=self.state.value,
            details=details,
        )
        self.events.append(workflow_event)
        return workflow_event

    def register_task(self, task: WorkflowTask) -> None:
        """Register a task without allowing duplicate task IDs."""
        if task.task_id in self.tasks:
            raise ValueError(
                f"Task already registered: {task.task_id}"
            )

        self.tasks[task.task_id] = task
        self.record(
            EventType.TASK_REGISTERED.value,
            task_id=task.task_id,
            task_name=task.name,
            owner=task.owner,
        )


# ============================================================
# LEGAL WORKFLOW TRANSITIONS
# ============================================================

LEGAL_TRANSITIONS = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,

    (WorkflowState.RUNNING, "pause"): WorkflowState.WAITING,
    (WorkflowState.RUNNING, "complete"): WorkflowState.COMPLETED,
    (WorkflowState.RUNNING, "fail"): WorkflowState.FAILED,
    (WorkflowState.RUNNING, "review"): WorkflowState.NEEDS_REVIEW,

    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,
    (WorkflowState.WAITING, "cancel"): WorkflowState.CANCELLED,

    (WorkflowState.NEEDS_REVIEW, "retry"): WorkflowState.RUNNING,
    (WorkflowState.NEEDS_REVIEW, "cancel"): WorkflowState.CANCELLED,

    (WorkflowState.FAILED, "review"): WorkflowState.NEEDS_REVIEW,

    (WorkflowState.CREATED, "cancel"): WorkflowState.CANCELLED,
}


def transition(run: WorkflowRun, event: str) -> WorkflowRun:
    """
    Validate and apply a legal workflow state transition.

    Invalid transitions raise ValueError without changing state.
    """
    next_state = LEGAL_TRANSITIONS.get((run.state, event))

    if next_state is None:
        raise ValueError(
            f"Illegal transition: {run.state.value} + {event}"
        )

    previous_state = run.state
    run.state = next_state

    run.record(
        event,
        previous_state=previous_state.value,
        new_state=next_state.value,
    )

    return run


# ============================================================
# TASK 1 FIXTURE
# ============================================================

def run_task1_fixture() -> dict[str, Any]:
    """Create a sample workflow contract and validate its start."""
    run = WorkflowRun(
        run_id=str(uuid4()),
        business_key="BUSINESS-001",
        owner="workflow_operator",
        max_attempts=3,
        max_steps=10,
    )

    run.record(EventType.WORKFLOW_CREATED.value)

    run.register_task(
        WorkflowTask(
            task_id="task_1",
            name="validate_request",
            owner="validation_service",
        )
    )

    run.register_task(
        WorkflowTask(
            task_id="task_2",
            name="process_request",
            owner="processing_service",
            dependencies=["task_1"],
        )
    )

    transition(run, "start")

    return {
        "run_id": run.run_id,
        "business_key": run.business_key,
        "status": run.state.value,
        "owner": run.owner,
        "max_steps": run.max_steps,
        "task_count": len(run.tasks),
        "tasks": {
            task_id: {
                "name": task.name,
                "owner": task.owner,
                "state": task.state.value,
                "dependencies": task.dependencies,
            }
            for task_id, task in run.tasks.items()
        },
        "events": [
            {
                "event": event.event,
                "state": event.state,
                "timestamp": event.timestamp,
            }
            for event in run.events
        ],
    }


if __name__ == "__main__":
    print("TASK 1 - WORKFLOW CONTRACT")
    print("=" * 55)

    result = run_task1_fixture()

    import json
    print(json.dumps(result, indent=2))


# ============================================================
# TASK 2 - WORKFLOW ORCHESTRATION ENGINE
# ============================================================

from collections.abc import Callable


class WorkflowValidationError(Exception):
    """Raised when a workflow definition is invalid."""


class WorkflowTaskError(Exception):
    """Raised when a workflow task cannot be completed."""


class WorkflowOrchestrator:
    """
    Dependency-aware workflow orchestrator.

    Responsibilities:
    - Validate task dependencies.
    - Detect dependency cycles.
    - Execute tasks only after dependencies complete.
    - Enforce a workflow step limit.
    - Record task and workflow events.
    - Return an explicit next action.
    """

    def __init__(
        self,
        run: WorkflowRun,
        task_handlers: dict[str, Callable],
    ):
        self.run = run
        self.task_handlers = task_handlers

    def validate_workflow(self) -> None:
        """Validate task registry, dependencies, and DAG structure."""

        if not self.run.tasks:
            raise WorkflowValidationError(
                "Workflow must contain at least one task"
            )

        task_ids = set(self.run.tasks)

        for task_id, task in self.run.tasks.items():

            if task_id not in self.task_handlers:
                raise WorkflowValidationError(
                    f"Missing handler for task: {task_id}"
                )

            if task.task_id != task_id:
                raise WorkflowValidationError(
                    f"Task registry key mismatch: {task_id}"
                )

            for dependency in task.dependencies:
                if dependency not in task_ids:
                    raise WorkflowValidationError(
                        f"Unknown dependency {dependency} "
                        f"for task {task_id}"
                    )

                if dependency == task_id:
                    raise WorkflowValidationError(
                        f"Task cannot depend on itself: {task_id}"
                    )

        # Detect dependency cycles using depth-first search.
        visited = set()
        active = set()

        def visit(task_id: str) -> None:
            if task_id in active:
                raise WorkflowValidationError(
                    f"Dependency cycle detected at: {task_id}"
                )

            if task_id in visited:
                return

            active.add(task_id)

            for dependency in self.run.tasks[
                task_id
            ].dependencies:
                visit(dependency)

            active.remove(task_id)
            visited.add(task_id)

        for task_id in self.run.tasks:
            visit(task_id)

    def execute(self) -> WorkflowResult:
        """Execute the workflow in dependency order."""

        # Validate the complete graph before any task handler runs.
        self.validate_workflow()

        if self.run.state != WorkflowState.CREATED:
            raise WorkflowValidationError(
                "Workflow must be in created state before execution"
            )

        transition(self.run, "start")

        self.run.record(
            EventType.WORKFLOW_STARTED.value,
            task_count=len(self.run.tasks),
        )

        while True:

            pending_tasks = [
                task
                for task in self.run.tasks.values()
                if task.state in (
                    TaskState.PENDING,
                    TaskState.READY,
                )
            ]

            if not pending_tasks:
                break

            ready_tasks = [
                task
                for task in pending_tasks
                if all(
                    self.run.tasks[dependency].state
                    == TaskState.COMPLETED
                    for dependency in task.dependencies
                )
            ]

            if not ready_tasks:
                raise WorkflowValidationError(
                    "No executable tasks remain; "
                    "dependency graph cannot progress"
                )

            for task in ready_tasks:

                # Hard workflow-level task execution limit.
                if self.run.steps_executed >= self.run.max_steps:
                    self.run.record(
                        "workflow_step_limit_reached",
                        max_steps=self.run.max_steps,
                        steps_executed=self.run.steps_executed,
                    )

                    transition(self.run, "review")

                    return WorkflowResult(
                        run_id=self.run.run_id,
                        business_key=self.run.business_key,
                        status=self.run.state.value,
                        task_results={
                            task_id: item.result
                            for task_id, item in self.run.tasks.items()
                            if item.state == TaskState.COMPLETED
                        },
                        error_type="StepLimitExceeded",
                        next_action="review_workflow_step_limit",
                    )

                task.state = TaskState.READY
                task.state = TaskState.RUNNING
                task.attempts += 1
                self.run.steps_executed += 1

                self.run.record(
                    EventType.TASK_STARTED.value,
                    task_id=task.task_id,
                    task_name=task.name,
                    owner=task.owner,
                    attempt=task.attempts,
                    step=self.run.steps_executed,
                )

                try:
                    handler = self.task_handlers[task.task_id]
                    task_result = handler(self.run)

                    # Store the result only after successful execution.
                    task.result = task_result
                    task.state = TaskState.COMPLETED

                    self.run.context[task.task_id] = task_result

                    self.run.record(
                        EventType.TASK_COMPLETED.value,
                        task_id=task.task_id,
                        outcome="success",
                    )

                except Exception as error:
                    task.state = TaskState.FAILED
                    task.error_type = type(error).__name__

                    self.run.record(
                        EventType.TASK_FAILED.value,
                        task_id=task.task_id,
                        error_type=task.error_type,
                        next_action="review_failed_task",
                    )

                    transition(self.run, "review")

                    return WorkflowResult(
                        run_id=self.run.run_id,
                        business_key=self.run.business_key,
                        status=self.run.state.value,
                        task_results={
                            task_id: item.result
                            for task_id, item in self.run.tasks.items()
                            if item.state == TaskState.COMPLETED
                        },
                        error_type=task.error_type,
                        next_action="review_failed_task",
                    )

        transition(self.run, "complete")

        self.run.record(
            EventType.WORKFLOW_COMPLETED.value,
            completed_tasks=len(self.run.tasks),
            steps_executed=self.run.steps_executed,
        )

        return WorkflowResult(
            run_id=self.run.run_id,
            business_key=self.run.business_key,
            status=self.run.state.value,
            task_results={
                task_id: task.result
                for task_id, task in self.run.tasks.items()
            },
            next_action="none",
        )


# ============================================================
# TASK 2 - DETERMINISTIC WORKFLOW FIXTURE
# ============================================================

def run_topic2_fixture() -> dict[str, Any]:
    """
    Execute a deterministic order operations workflow.

    The handlers use local synthetic data only.
    No production service is contacted.
    """

    run = WorkflowRun(
        run_id=str(uuid4()),
        business_key="ORDER-2001",
        owner="order_operations",
        max_attempts=3,
        max_steps=10,
    )

    # Register the workflow tasks and their dependencies.
    tasks = [
        WorkflowTask(
            task_id="validate_order",
            name="Validate order",
            owner="validation_service",
        ),
        WorkflowTask(
            task_id="check_inventory",
            name="Check inventory",
            owner="inventory_service",
            dependencies=["validate_order"],
        ),
        WorkflowTask(
            task_id="reserve_inventory",
            name="Reserve inventory",
            owner="inventory_service",
            dependencies=["check_inventory"],
        ),
        WorkflowTask(
            task_id="process_payment",
            name="Process payment",
            owner="payment_service",
            dependencies=["validate_order"],
        ),
        WorkflowTask(
            task_id="create_shipment",
            name="Create shipment",
            owner="fulfilment_service",
            dependencies=[
                "reserve_inventory",
                "process_payment",
            ],
        ),
        WorkflowTask(
            task_id="notify_customer",
            name="Notify customer",
            owner="notification_service",
            dependencies=["create_shipment"],
        ),
    ]

    for task in tasks:
        run.register_task(task)

    # Local deterministic task handlers.
    def validate_order(context: WorkflowRun):
        return {
            "valid": True,
            "order_id": context.business_key,
        }

    def check_inventory(context: WorkflowRun):
        return {
            "available": True,
            "quantity_available": 10,
        }

    def reserve_inventory(context: WorkflowRun):
        return {
            "reserved": True,
            "reservation_id": "RES-2001",
        }

    def process_payment(context: WorkflowRun):
        return {
            "payment_status": "approved",
            "payment_id": "PAY-2001",
        }

    def create_shipment(context: WorkflowRun):
        return {
            "shipment_status": "created",
            "shipment_id": "SHIP-2001",
        }

    def notify_customer(context: WorkflowRun):
        return {
            "notification_status": "sent",
            "notification_id": "NOTIFY-2001",
        }

    handlers = {
        "validate_order": validate_order,
        "check_inventory": check_inventory,
        "reserve_inventory": reserve_inventory,
        "process_payment": process_payment,
        "create_shipment": create_shipment,
        "notify_customer": notify_customer,
    }

    orchestrator = WorkflowOrchestrator(
        run=run,
        task_handlers=handlers,
    )

    result = orchestrator.execute()

    return {
        "run_id": result.run_id,
        "business_key": result.business_key,
        "status": result.status,
        "next_action": result.next_action,
        "steps_executed": run.steps_executed,
        "task_count": len(run.tasks),
        "completed_tasks": sum(
            task.state == TaskState.COMPLETED
            for task in run.tasks.values()
        ),
        "tasks": {
            task_id: {
                "name": task.name,
                "owner": task.owner,
                "state": task.state.value,
                "dependencies": task.dependencies,
                "attempts": task.attempts,
                "result": task.result,
            }
            for task_id, task in run.tasks.items()
        },
        "events": [
            {
                "event": event.event,
                "state": event.state,
                "details": event.details,
                "timestamp": event.timestamp,
            }
            for event in run.events
        ],
    }


if __name__ == "__main__":
    print("\nTASK 2 - WORKFLOW ORCHESTRATION")
    print("=" * 60)

    orchestration_result = run_topic2_fixture()
    print(json.dumps(orchestration_result, indent=2))

