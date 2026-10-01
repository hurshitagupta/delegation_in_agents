# Topic 14 — Implement Delegation

## Overview

This project implements a delegation workflow where a supervisor assigns work to specialized workers, passes structured handoff context, reviews the returned result, and keeps ownership of the final decision.

## Features

- Worker registry with allowed capabilities
- LLM-based assignment policy
- Structured handoff with goal, context, constraints, and expected output
- Real LLM worker execution
- Supervisor result review
- Accept, reject, and reassign decisions
- End-to-end delegation trace
- Step limits, validation, timeout, and retry handling
- Saved outputs and pytest evidence

## Project Structure

```text
delegation/
│
├── worker_registry.py
├── assignment_policy.py
├── handoff.py
├── result_review.py
├── delegation_trace.py
│
├── tests/
│   ├── test_worker_registry.py
│   ├── test_assignment_policy.py
│   ├── test_handoff.py
│   ├── test_result_review.py
│   └── test_delegation_trace.py
│
├── outputs/
│   ├── worker_registry.txt
│   ├── test_worker_registry.txt
│   ├── assignment_policy.txt
│   ├── test_assignment_policy.txt
│   ├── handoff.txt
│   ├── test_handoff.txt
│   ├── result_review.txt
│   ├── test_result_review.txt
│   ├── delegation_trace.txt
│   └── test_delegation_trace.txt
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

## Task 1 — Worker Registry

`worker_registry.py` defines the workers available for delegation.

Each worker contains:

- name
- capabilities
- description
- execution handler

The registry supports worker registration, lookup, capability matching, duplicate detection, and worker limits. It also rejects unknown or invalid workers.

### Run

```bash
python worker_registry.py
```

### Test

```bash
pytest tests/test_worker_registry.py -v
```
---

## Task 2 — Assignment Policy

`assignment_policy.py` uses a real OpenRouter LLM call to select the most suitable registered worker for a goal.

The supervisor receives:

- user goal
- available workers
- worker capabilities

The returned worker is validated against the registry before the assignment is accepted.

If the model selects an unknown worker or no suitable worker exists, the assignment is rejected.

### Run

```bash
python assignment_policy.py
```

### Test

```bash
pytest tests/test_assignment_policy.py -v
```
---

## Task 3 — Handoff

`handoff.py` creates a structured handoff between the supervisor and selected worker.

The handoff contains:

```text
goal
context
constraints
expected_output
assigned_worker
result_owner
```

The assigned worker then performs the delegated task using a real OpenRouter LLM call. The result owner always remains the supervisor.

### Run

```bash
python handoff.py
```

### Test

```bash
pytest tests/test_handoff.py -v
```

---

## Task 4 — Result Review

`result_review.py` implements the supervisor review boundary.

After a worker returns its result, the supervisor reviews it using a real OpenRouter LLM call.

The supervisor can return only:

```text
accept
reject
reassign
```
The model output is validated before it is accepted as a valid review decision.This ensures delegated work does not automatically become the final outcome.

### Run

```bash
python result_review.py
```

### Test

```bash
pytest tests/test_result_review.py -v
```
---

## Task 5 — Delegation Trace

`delegation_trace.py` combines the complete delegation workflow.

The trace records:

```text
assignment
→ handoff
→ worker execution
→ supervisor review
→ final state
```

Each trace event contains:

- step number
- step name
- status
- details

The final state can be:

```text
accepted
rejected_by_supervisor
reassignment_required
assignment_failed
worker_execution_failed
review_failed
```

### Run

```bash
python delegation_trace.py
```

### Test

```bash
pytest tests/test_delegation_trace.py -v
```
## Setup

Create and activate a virtual environment.

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file.

The API key is loaded only from environment variables and is not stored in source code.

## Requirements

Example `requirements.txt`:

```text
openai
python-dotenv
pytest
```

## Run All Tests

```bash
pytest tests -v
```
## Guardrails

The project includes the required safety and reliability controls.

### Step Limits

- Worker registry has a maximum worker limit.
- LLM calls have bounded retry attempts.
- Delegation trace uses a fixed maximum number of workflow steps.

### Timeout

External OpenRouter calls use a per-request timeout.

### Retry

Retries are used only for transient failures such as:

- timeouts
- connection failures
- rate limits
- temporary 5xx API errors

Validation errors and unsupported workers are not retried.

### Validation

Validation is applied to:

- goals
- registered workers
- worker capabilities
- handoff fields
- result ownership
- LLM decisions
- worker results
- supervisor review decisions

### Secret Hygiene

Credentials are loaded through `.env`.

The `.env` file should be excluded using `.gitignore`.

## Evidence

Each task saves observable evidence inside the `outputs/` folder. Pytest outputs are also stored in the same folder.

## Conclusion

This assessment demonstrates delegation as a controlled supervisor-worker workflow rather than simply forwarding a prompt to another model.