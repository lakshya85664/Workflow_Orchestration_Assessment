
import pytest

from workflow_orchestration_assessment import (
    WorkflowRun,
    WorkflowTask,
    WorkflowState,
    TaskState,
    transition,
)


def create_run():
    return WorkflowRun(
        run_id="RUN-001",
        business_key="BUSINESS-001",
        owner="test_operator",
    )


def test_workflow_starts_successfully():
    run = create_run()

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING
    assert len(run.events) == 1
    assert run.events[0].event == "start"


def test_workflow_completes_successfully():
    run = create_run()

    transition(run, "start")
    transition(run, "complete")

    assert run.state == WorkflowState.COMPLETED


def test_illegal_transition_is_rejected():
    run = create_run()

    with pytest.raises(ValueError, match="Illegal transition"):
        transition(run, "complete")

    assert run.state == WorkflowState.CREATED
    assert len(run.events) == 0


def test_workflow_can_pause_and_resume():
    run = create_run()

    transition(run, "start")
    transition(run, "pause")

    assert run.state == WorkflowState.WAITING

    transition(run, "resume")

    assert run.state == WorkflowState.RUNNING


def test_task_registration_and_dependencies():
    run = create_run()

    first_task = WorkflowTask(
        task_id="task_1",
        name="validate",
        owner="validation_service",
    )

    second_task = WorkflowTask(
        task_id="task_2",
        name="execute",
        owner="execution_service",
        dependencies=["task_1"],
    )

    run.register_task(first_task)
    run.register_task(second_task)

    assert len(run.tasks) == 2
    assert run.tasks["task_2"].dependencies == ["task_1"]
    assert run.tasks["task_1"].state == TaskState.PENDING


def test_duplicate_task_registration_is_rejected():
    run = create_run()

    task = WorkflowTask(
        task_id="task_1",
        name="validate",
        owner="validation_service",
    )

    run.register_task(task)

    with pytest.raises(ValueError, match="already registered"):
        run.register_task(task)


def test_empty_workflow_owner_is_rejected():
    with pytest.raises(ValueError, match="owner"):
        WorkflowRun(
            run_id="RUN-002",
            business_key="BUSINESS-002",
            owner="",
        )


def test_invalid_max_steps_is_rejected():
    with pytest.raises(ValueError, match="max_steps"):
        WorkflowRun(
            run_id="RUN-003",
            business_key="BUSINESS-003",
            owner="operator",
            max_steps=0,
        )


def test_duplicate_dependencies_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        WorkflowTask(
            task_id="task_3",
            name="duplicate_dependency",
            owner="worker",
            dependencies=["task_1", "task_1"],
        )


# ============================================================
# TASK 2 - ORCHESTRATION TESTS
# ============================================================

from workflow_orchestration_assessment import (
    WorkflowOrchestrator,
    WorkflowValidationError,
    run_topic2_fixture,
)


def test_deterministic_workflow_completes():
    result = run_topic2_fixture()

    assert result["status"] == "completed"
    assert result["next_action"] == "none"
    assert result["task_count"] == 6
    assert result["completed_tasks"] == 6
    assert result["steps_executed"] == 6


def test_workflow_respects_task_dependencies():
    result = run_topic2_fixture()

    tasks = result["tasks"]

    assert tasks["check_inventory"]["state"] == "completed"
    assert tasks["reserve_inventory"]["dependencies"] == [
        "check_inventory"
    ]
    assert tasks["create_shipment"]["dependencies"] == [
        "reserve_inventory",
        "process_payment",
    ]


def test_workflow_records_task_execution_events():
    result = run_topic2_fixture()

    event_names = [
        event["event"] for event in result["events"]
    ]

    assert "workflow_started" in event_names
    assert "task_started" in event_names
    assert "task_completed" in event_names
    assert "workflow_completed" in event_names


def test_missing_dependency_is_rejected_before_execution():
    run = create_run()

    run.register_task(
        WorkflowTask(
            task_id="task_a",
            name="Task A",
            owner="worker",
            dependencies=["missing_task"],
        )
    )

    side_effects = []

    handlers = {
        "task_a": lambda context: side_effects.append("executed")
    }

    orchestrator = WorkflowOrchestrator(run, handlers)

    with pytest.raises(
        WorkflowValidationError,
        match="Unknown dependency",
    ):
        orchestrator.execute()

    assert side_effects == []
    assert run.state == WorkflowState.CREATED


def test_dependency_cycle_is_rejected_before_execution():
    run = create_run()

    run.register_task(
        WorkflowTask(
            task_id="task_a",
            name="Task A",
            owner="worker",
            dependencies=["task_b"],
        )
    )

    run.register_task(
        WorkflowTask(
            task_id="task_b",
            name="Task B",
            owner="worker",
            dependencies=["task_a"],
        )
    )

    side_effects = []

    handlers = {
        "task_a": lambda context: side_effects.append("a"),
        "task_b": lambda context: side_effects.append("b"),
    }

    orchestrator = WorkflowOrchestrator(run, handlers)

    with pytest.raises(
        WorkflowValidationError,
        match="Dependency cycle",
    ):
        orchestrator.execute()

    assert side_effects == []
    assert run.state == WorkflowState.CREATED


def test_workflow_step_limit_is_enforced():
    run = WorkflowRun(
        run_id="RUN-LIMIT-001",
        business_key="BUSINESS-LIMIT-001",
        owner="test_operator",
        max_steps=1,
    )

    run.register_task(
        WorkflowTask(
            task_id="task_a",
            name="Task A",
            owner="worker",
        )
    )

    run.register_task(
        WorkflowTask(
            task_id="task_b",
            name="Task B",
            owner="worker",
            dependencies=["task_a"],
        )
    )

    handlers = {
        "task_a": lambda context: {"success": True},
        "task_b": lambda context: {"success": True},
    }

    orchestrator = WorkflowOrchestrator(run, handlers)
    result = orchestrator.execute()

    assert result.status == "needs_review"
    assert result.error_type == "StepLimitExceeded"
    assert result.next_action == "review_workflow_step_limit"
    assert run.steps_executed == 1
