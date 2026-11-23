# Topic 19 — Operator Runbook and Evidence Report

## 1. Purpose

This report documents the workflow lifecycle demonstrations, operator responses, measurements, trace artifacts, and known limitations for the Workflow Orchestration Assessment.

## 2. Execution commands

Run from the project root with the virtual environment activated:

```cmd
python generate_task1_evidence.py
python generate_task2_evidence.py
python task3_failure_retry_replay.py
python generate_task3_evidence.py
python task4_integration_observability.py
python generate_task4_evidence.py
python -m pytest -q
python generate_task5_evidence.py
```

## 3. Lifecycle scenarios and operator actions

| Scenario | Demonstrated behavior | Operator action |
|---|---|---|
| Success | Six workflow tasks complete | Verify final outputs and retain the evidence |
| Transient failure | Retry succeeds on second attempt | Inspect attempt events and bounded retry count |
| Timeout | Simulated timeout followed by successful retry | Verify external operation status before repeating it |
| Permanent failure | Workflow moves to needs_review | Inspect the error and resolve the cause before re-execution |
| Malformed response | Invalid response is rejected | Review the handler and response contract |
| Replay | Cached completed result is returned | Verify the business operation key and existing result |
| Duplicate trigger | Repeated trigger is rejected | Inspect the original workflow status; do not repeat the side effect |
| Dependency failure | External call failure is recorded | Inspect error type and trace; decide on safe retry or review |

## 4. Output excerpts

### Task 2 — successful workflow

The Task 2 evidence confirms the deterministic six-task workflow completed, with all six tasks completed and 22 workflow events.

### Task 3 — failure and replay

- Transient retry: completed in 2 attempts.
- Timeout retry: completed in 2 attempts.
- Malformed response: needs_review.
- Permanent failure: needs_review.
- Replay: replayed.
- Duplicate trigger: rejected.
- Non-idempotent side effect count: 1.

### Task 4 — dependency measurements

```json
{
  "calls": 2,
  "successes": 1,
  "failures": 1,
  "total_duration_ms": 0.009,
  "average_duration_ms": 0.005
}
```

## 5. Measurement table

| Measurement | Observed value |
|---|---:|
| External dependency calls | 2 |
| Successful dependency calls | 1 |
| Failed dependency calls | 1 |
| Total duration (ms) | 0.009 |
| Average duration (ms) | 0.005 |
| Structured trace events | 4 |
| Automated tests | 40 passed in last verified run |

The dependency timings are measurements from a local fake adapter. They are not representative of real network latency or production throughput.

## 6. Trace and evidence files

| Artifact | Purpose |
|---|---|
| `outputs/task1_workflow_contract.json` | Workflow contract evidence |
| `outputs/task2_orchestration.json` | Orchestration evidence |
| `outputs/task3_failure_retry_replay.json` | Failure, retry, replay evidence |
| `outputs/task4_integration_evidence.json` | Adapter and redaction evidence |
| `outputs/task4_measurement_report.json` | Dependency scenario report |
| `outputs/task4_metrics.json` | Dependency measurements |
| `traces/task4_integration_trace.jsonl` | Structured dependency events |
| `outputs/task5_consolidated_evidence.json` | Task 5 verification |

## 7. Known limitations

- The external dependency is represented by a fake adapter; no live service is called.
- Retries are bounded but do not use exponential backoff or jitter.
- Idempotency and trigger stores are in-memory, not durable or atomic across processes.
- A simulated timeout does not cancel a real external operation. An external side effect may have occurred despite a timeout.
- Events and metrics are held in memory until exported.
- Distributed tracing and persistent telemetry are not implemented.
- Secret redaction relies on recognized dictionary key names and cannot detect every secret embedded in arbitrary strings.
- Fake adapter timings are not production performance benchmarks.

## 8. Engineering reflection (~300 words)

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

## 9. Verification

Generated at: 2026-11-23T12:15:39.274931+00:00

The evidence generator checks the availability and validity of the Task 1–4 artifacts. The full automated suite was last verified at 40 passing tests. Run `python -m pytest -q` again to confirm the current environment.
