
# Workflow State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> created
    created --> running: start
    created --> cancelled: cancel

    running --> waiting: pause
    running --> completed: complete
    running --> failed: fail
    running --> needs_review: review

    waiting --> running: resume
    waiting --> cancelled: cancel

    failed --> needs_review: review

    needs_review --> running: retry
    needs_review --> cancelled: cancel

    completed --> [*]
    cancelled --> [*]
```

## State Descriptions

| State | Description |
|---|---|
| created | Workflow has been initialized |
| running | Workflow execution is active |
| waiting | Workflow is paused pending an event or approval |
| completed | All required workflow work has completed |
| failed | Workflow execution has failed |
| needs_review | Operator review is required |
| cancelled | Workflow execution has been cancelled |

Transitions are validated against `LEGAL_TRANSITIONS` in the source module.
