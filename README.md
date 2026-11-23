# Workflow Orchestration Assessment

**Topic 19 --- Workflow Orchestration**\

## Overview

This project implements and evaluates a deterministic multi-step
workflow orchestration system. It demonstrates workflow contracts and
state transitions, dependency-aware task execution, failure handling and
replay safety, injectable external-service integration, structured
observability, and operator-facing evidence.

The implementation uses Python and pytest. External-service behavior is
tested with a fake adapter so the assessment can run locally without
contacting a live service.

## Assessment tasks

### Task 1 --- Workflow contract

-   Defines workflow and task state behavior.
-   Registers tasks and declares dependencies.
-   Verifies legal state transitions and rejects illegal transitions.
-   Records structured workflow events and ownership information.
-   Evidence: `outputs/task1_workflow_contract.json`.

### Task 2 --- Orchestration engine

-   Validates the task registry and dependency graph before execution.
-   Rejects invalid dependencies and cycles before handlers run.
-   Executes tasks in dependency order.
-   Enforces a workflow step limit.
-   Records task and workflow events and returns a workflow result.
-   Demonstration fixture completes six tasks: validation, inventory
    check, inventory reservation, payment, shipment, and customer
    notification.
-   Evidence: `outputs/task2_orchestration.json`.

### Task 3 --- Failure, retry, and replay safety

-   Classifies transient, timeout, malformed-response, and permanent
    failures.
-   Retries transient errors and simulated timeouts within a bounded
    attempt limit.
-   Routes malformed responses and permanent failures to operator
    review.
-   Uses an idempotency store and trigger tracking to demonstrate replay
    behavior.
-   Verifies that a simulated non-idempotent side effect occurs once, a
    new trigger can retrieve the completed result, and a repeated
    trigger is rejected.
-   Evidence: `outputs/task3_failure_retry_replay.json`.

### Task 4 --- Integration boundary and observability

-   Defines an injectable external-service adapter contract.
-   Provides a deterministic fake adapter for success and failure tests.
-   Records structured JSON events and exports JSONL traces.
-   Exposes dependency status and basic call metrics.
-   Redacts recognized secret dictionary keys, including nested values.
-   Evidence: `outputs/task4_integration_evidence.json`.
-   Measurement report: `outputs/task4_measurement_report.json`.
-   Metrics: `outputs/task4_metrics.json`.
-   Trace: `traces/task4_integration_trace.jsonl`.

### Task 5 --- Operator runbook and evidence report

-   Documents success, failure, retry/recovery, replay, and
    duplicate-trigger scenarios.
-   Summarizes operator actions, output excerpts, measurements, trace
    references, and known limitations.
-   Includes an approximately 300-word engineering reflection.
-   Report: `reports/operator_runbook.md`.
-   Consolidated evidence: `outputs/task5_consolidated_evidence.json`.

## Environment

The verified development environment for this assessment was:

-   Windows
-   Python 3.13.9
-   pytest 9.2.0
-   Pydantic 2.14.4
-   Virtual environment: `.venv`

Use the project's `requirements.txt` for the dependency list.

## Setup

Open Command Prompt in the project directory:

``` cmd
cd /d E:\Tayana_Projects\Workflow_Orchestration\Implement_Workflow_Orchestration_Assessment
```

Create and activate a virtual environment if needed:

``` cmd
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

``` cmd
python -m pip install -r requirements.txt
```

## Run the assessment

Generate evidence in task order:

``` cmd
python generate_task1_evidence.py
python generate_task2_evidence.py
python task3_failure_retry_replay.py
python generate_task3_evidence.py
python task4_integration_observability.py
python generate_task4_evidence.py
python generate_task5_evidence.py
```

Run the full automated test suite:

``` cmd
python -m pytest -q
```

**Last verified result:** `40 passed in 0.14s` (November 23, 2026).
Re-run the command to verify the current environment.

## Evidence directory structure

``` text
Implement_Workflow_Orchestration_Assessment/
├── diagrams/
├── outputs/
│   ├── task1_workflow_contract.json
│   ├── task2_orchestration.json
│   ├── task3_failure_retry_replay.json
│   ├── task4_integration_evidence.json
│   ├── task4_measurement_report.json
│   ├── task4_metrics.json
│   └── task5_consolidated_evidence.json
├── reports/
│   └── operator_runbook.md
├── tests/
├── traces/
│   └── task4_integration_trace.jsonl
├── workflow_orchestration_assessment.py
├── task3_failure_retry_replay.py
├── task4_integration_observability.py
├── generate_task1_evidence.py
├── generate_task2_evidence.py
├── generate_task3_evidence.py
├── generate_task4_evidence.py
├── generate_task5_evidence.py
├── requirements.txt
└── README.md
```

The directory listing is a guide to the principal assessment artifacts;
retain any additional source, test, and evidence files created during
implementation.

## Measurement snapshot

The Task 4 fake-adapter demonstration recorded:

  Metric                      Observed value
  ------------------------- ----------------
  Dependency calls                         2
  Successful calls                         1
  Failed calls                             1
  Structured trace events                  4

The measured duration is a local fake-adapter execution time, not a
production network-latency benchmark.

## Known limitations

-   The external dependency is represented by a fake adapter; no live
    service is called.
-   Retry attempts are bounded but do not implement exponential backoff
    or jitter.
-   The demonstration idempotency and trigger stores are in-memory, not
    durable or atomic across processes.
-   The timeout fixture raises a simulated timeout exception; it does
    not forcibly cancel a real external operation. An external side
    effect may have occurred even if a caller times out.
-   Events and metrics are held in memory until exported; persistent
    telemetry and distributed tracing are not implemented.
-   Secret redaction is based on recognized dictionary key names and
    cannot identify every secret embedded in arbitrary strings.
-   Task 2's independent branches execute sequentially in this
    implementation; parallel task execution is not demonstrated.

## Engineering reflection (\~300 words)

This assessment demonstrated how a multi-step workflow can be structured
around explicit task dependencies, controlled state transitions, and
observable execution. Task 1 established the workflow contract and state
model. Task 2 extended that foundation into an orchestrator that
validates dependencies, executes eligible tasks, and records task-level
outcomes. This made execution order and workflow state easier to inspect
than an unstructured sequence of function calls.

Task 3 focused on reliability. Transient errors and simulated timeouts
were retried within a bounded attempt limit, while malformed responses
and permanent failures were treated as conditions requiring review.
Replay testing demonstrated why idempotency matters: a completed
operation could be returned for a new trigger without repeating the
simulated non-idempotent side effect, while a duplicate trigger was
rejected. These controls reduce duplicate-processing risk, although they
do not guarantee exactly-once execution against an arbitrary external
service.

Task 4 introduced an injectable dependency boundary. A fake adapter made
success and failure behavior deterministic and testable without
contacting a live service. Structured events, status lookup, JSONL trace
export, and basic call metrics made dependency behavior observable.
Secret redaction was verified for recognized sensitive dictionary keys,
including nested values.

The implementation has important production limitations. The fake
adapter does not validate real network behavior. Retry timing is bounded
but does not provide exponential backoff or jitter. Idempotency and
event storage are in-memory, so they are not durable or atomic across
processes. The timeout fixture simulates a timeout exception rather than
forcibly cancelling an external operation. Redaction by key name cannot
detect every possible secret.

The main engineering lesson is to make workflow state, failure
categories, replay behavior, and operator decisions explicit. Before
production use, the design would need durable idempotency storage,
authenticated external adapters, secure secret management, persistent
telemetry, real timeout handling, and operational alerts. This
assessment provides a testable foundation, not a production-ready
distributed workflow platform.
