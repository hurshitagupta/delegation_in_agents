import json
import time
import uuid
from pathlib import Path
from assignment_policy import assign_worker
from handoff import execute_handoff
from result_review import review_result

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_STEPS = 4

def add_trace_event( trace: list[dict], step: str, status: str, details: dict) -> None:
    trace.append({"step_number": len(trace) + 1, "step": step, "status": status, "details": details})

def run_delegation(goal: str, context: str, constraints: list[str], expected_output: str) -> dict:

    run_id = str(uuid.uuid4())
    trace: list[dict] = []
    start_time = time.perf_counter()

    if not isinstance(goal, str) or not goal.strip():
        return {
            "run_id": run_id,
            "status": "rejected",
            "error": "invalid_goal",
            "trace": trace}

    if not isinstance(constraints, list):
        return {
            "run_id": run_id,
            "status": "rejected",
            "error": "constraints_must_be_list",
            "trace": trace}

    if len(trace) >= MAX_STEPS:
        return {
            "run_id": run_id,
            "status": "failed",
            "error": "step_limit_reached",
            "trace": trace}

    assignment = assign_worker(goal)

    add_trace_event(trace=trace, step="assignment", status=assignment["status"], details=assignment)

    if assignment["status"] != "success":
        duration_ms = (time.perf_counter() - start_time) * 1000

        return {
            "run_id": run_id,
            "status": "rejected",
            "final_state": "assignment_failed",
            "trace": trace,
            "step_count": len(trace),
            "duration_ms": round(duration_ms, 2)}

    if len(trace) >= MAX_STEPS:
        return {
            "run_id": run_id,
            "status": "failed",
            "error": "step_limit_reached",
            "trace": trace}

    handoff_brief = {
        "goal": goal.strip(),
        "context": context.strip(),
        "constraints": constraints,
        "expected_output": expected_output.strip(),
        "assigned_worker": assignment["worker"],
        "result_owner": "supervisor"}

    add_trace_event(trace=trace, step="handoff", status="success",
        details={"assigned_worker": assignment["worker"], "goal": goal, "context": context, "constraints": constraints, "expected_output": expected_output, "result_owner": "supervisor"})

    if len(trace) >= MAX_STEPS:
        return {"run_id": run_id, "status": "failed", "error": "step_limit_reached", "trace": trace}

    worker_result = execute_handoff(handoff_brief)

    add_trace_event(trace=trace, step="worker_execution", status=worker_result["status"], details=worker_result)

    if worker_result["status"] != "success":
        duration_ms = (time.perf_counter() - start_time) * 1000

        return {
            "run_id": run_id,
            "status": "failed",
            "final_state": "worker_execution_failed",
            "trace": trace,
            "step_count": len(trace),
            "duration_ms": round(duration_ms, 2)}

    if len(trace) >= MAX_STEPS:
        return {
            "run_id": run_id,
            "status": "failed",
            "error": "step_limit_reached",
            "trace": trace}

    review = review_result(
        goal=goal,
        expected_output=expected_output,
        constraints=constraints,
        worker=worker_result["worker"],
        result=worker_result["result"])

    add_trace_event(trace=trace, step="supervisor_review", status=review["status"], details=review)

    if review["status"] != "success":
        duration_ms = (time.perf_counter() - start_time) * 1000

        return {
            "run_id": run_id,
            "status": "failed",
            "final_state": "review_failed",
            "trace": trace,
            "step_count": len(trace),
            "duration_ms": round(duration_ms, 2)}
    
    decision = review["decision"]

    if decision == "accept":
        final_status = "success"
        final_state = "accepted"

    elif decision == "reject":
        final_status = "rejected"
        final_state = "rejected_by_supervisor"

    elif decision == "reassign":
        final_status = "needs_review"
        final_state = "reassignment_required"

    else:
        final_status = "failed"
        final_state = "invalid_review_state"

    duration_ms = (time.perf_counter() - start_time) * 1000

    return {
        "run_id": run_id,
        "status": final_status,
        "final_state": final_state,
        "worker": assignment["worker"],
        "review_decision": decision,
        "result_owner": "supervisor",
        "step_count": len(trace),
        "max_steps": MAX_STEPS,
        "duration_ms": round(duration_ms, 2),
        "trace": trace}

if __name__ == "__main__":
    print("=== Delegation Trace ===")

    print("\n=== Happy Path ===")

    result = run_delegation(
        goal="Research factual information about short-term memory in AI agents.",
        context="The findings will be used in beginner-level learning material.",
        constraints=["Keep the response concise.", "Use simple language.", "Do not invent citations."],
        expected_output="A short factual explanation in 3 to 5 bullet points.")

    print(json.dumps(result, indent=2))

    print("\n=== Rejection Path ===")

    rejected_result = run_delegation(
        goal="",
        context="Test context.",
        constraints=[],
        expected_output="Short response.")

    print(json.dumps(rejected_result, indent=2))

    output = {"happy_path": result, "rejection_path": rejected_result}
    output_path = OUTPUT_DIR / "delegation_trace.txt"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")