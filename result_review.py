import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from handoff import build_handoff, execute_handoff

load_dotenv()

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2

ALLOWED_DECISIONS = {"accept", "reject", "reassign"}

client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))

MODEL_NAME = os.getenv("MODEL_NAME")

def validate_review_input( goal: str, expected_output: str, worker: str, result: str) -> dict:

    if not isinstance(goal, str) or not goal.strip():
        return {"status": "rejected", "error": "invalid_goal"}

    if not isinstance(expected_output, str) or not expected_output.strip():
        return {"status": "rejected", "error": "invalid_expected_output"}

    if not isinstance(worker, str) or not worker.strip():
        return {"status": "rejected", "error": "invalid_worker"}

    if not isinstance(result, str) or not result.strip():
        return {"status": "rejected", "error": "empty_worker_result"}

    return {"status": "success"}

def call_review_model(goal: str, expected_output: str, constraints: list[str], worker: str, result: str) -> dict:

    prompt = f"""You are the supervisor reviewing delegated work.

Original goal: {goal}
Expected output: {expected_output}
Constraints: {json.dumps(constraints, indent=2)}
Worker: {worker}
Worker result: {result}

Review the result carefully.
Return one of these decisions:
- accept: The result satisfies the goal, expected output, and constraints.
- reject: The result is unusable, unsafe, irrelevant, or clearly violates the task.
- reassign: The result may be recoverable, but another worker or another attempt is needed.

Rules:
1. Do not execute any task yourself.
2. Review only the provided worker result.
3. Give a short reason.
4. If reassigning, explain what needs improvement.
5. Return valid JSON only.

Return exactly:

{{
  "decision": "accept" | "reject" | "reassign",
  "reason": "short explanation",
  "feedback": "improvement instructions or empty string"
}} """

    start = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": "You are a delegation supervisor. Review delegated results and return only valid JSON."},
            {"role": "user", "content": prompt}],
        temperature=0,
        timeout=REQUEST_TIMEOUT_SECONDS)

    duration_ms = (time.perf_counter() - start) * 1000

    content = response.choices[0].message.content

    if not content:
        raise ValueError("empty_review_response")

    parsed = json.loads(content)

    parsed["duration_ms"] = round(duration_ms, 2)

    return parsed

def review_result(goal: str, expected_output: str, constraints: list[str], worker: str, result: str) -> dict:

    validation = validate_review_input(goal, expected_output, worker, result)

    if validation["status"] != "success":
        return validation

    attempts = 0
    last_error = None

    while attempts <= MAX_RETRIES:
        attempts += 1

        try:
            review = call_review_model(
                goal=goal,
                expected_output=expected_output,
                constraints=constraints,
                worker=worker,
                result=result)

            decision = review.get("decision")
            reason = review.get("reason")
            feedback = review.get("feedback", "")

            if decision not in ALLOWED_DECISIONS:
                return {"status": "rejected",
                    "error": "invalid_review_decision",
                    "decision": decision,
                    "attempts": attempts}

            if not isinstance(reason, str) or not reason.strip():
                return {"status": "rejected",
                    "error": "missing_review_reason",
                    "attempts": attempts}

            if not isinstance(feedback, str):
                return {"status": "rejected",
                    "error": "invalid_review_feedback",
                    "attempts": attempts}

            return {"status": "success",
                "decision": decision,
                "worker": worker,
                "reason": reason,
                "feedback": feedback,
                "result_owner": "supervisor",
                "attempts": attempts,
                "duration_ms": review.get("duration_ms")}

        except json.JSONDecodeError as exc:
            last_error = f"invalid_json: {exc}"

        except Exception as exc:
            last_error = str(exc)

            message = str(exc).lower()

            transient_error = any(text in message
                for text in ["timeout", "temporarily", "rate limit", "429", "500", "502", "503", "504", "connection"])

            if not transient_error:
                break

        if attempts <= MAX_RETRIES:
            time.sleep(0.5 * attempts)

    return {
        "status": "failed",
        "error": "review_model_failed",
        "details": last_error,
        "attempts": attempts}

if __name__ == "__main__":
    print("=== Result Review ===")

    goal = "Research factual information about short-term memory in AI agents."
    constraints = ["Keep the response concise.", "Use simple language.", "Do not invent citations."]
    expected_output = "A short factual explanation in 3 to 5 bullet points."

    print("\n=== Creating Handoff ===")

    handoff_result = build_handoff(
        goal=goal,
        context="This will be used in a beginner-level explanation of agent memory.",
        constraints=constraints,
        expected_output=expected_output)

    print(json.dumps(handoff_result, indent=2))

    worker_result = None
    review_result_output = None

    if handoff_result["status"] == "success":
        print("\n=== Worker Execution ===")

        worker_result = execute_handoff(handoff_result["handoff"])

        print(json.dumps(worker_result, indent=2))

        if worker_result["status"] == "success":
            print("\n=== Supervisor Review ===")

            review_result_output = review_result(
                goal=goal,
                expected_output=expected_output,
                constraints=constraints,
                worker=worker_result["worker"],
                result=worker_result["result"])

            print(json.dumps( review_result_output, indent=2))

    print("\n=== Rejection Path ===")

    rejected_review = review_result(
        goal="Research AI memory.",
        expected_output="Short factual explanation.",
        constraints=["Keep it factual."],
        worker="research_worker",
        result="")

    print(json.dumps(rejected_review,indent=2))

    output = {
        "handoff": handoff_result,
        "worker_execution": worker_result,
        "supervisor_review": review_result_output,
        "rejection_path": rejected_review
    }

    output_path = OUTPUT_DIR / "result_review.txt"

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
