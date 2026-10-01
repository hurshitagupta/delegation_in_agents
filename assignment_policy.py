import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from worker_registry import build_registry

load_dotenv()

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_RETRIES = 2
REQUEST_TIMEOUT_SECONDS = 20

client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))

MODEL_NAME = os.getenv("MODEL_NAME")

def validate_goal(goal: str) -> dict:
    if not isinstance(goal, str):
        return {"status": "rejected", "error": "goal_must_be_string"}

    goal = goal.strip()

    if not goal:
        return {"status": "rejected", "error": "empty_goal"}

    if len(goal) > 500:
        return {"status": "rejected", "error": "goal_too_long"}

    return {"status": "success", "goal": goal}


def call_assignment_model(goal: str, workers: list[dict]) -> dict:
    prompt = f""" You are a supervisor responsible for delegating work.

Choose exactly one worker whose capabilities best match the user's goal.

Available workers: {json.dumps(workers, indent=2)}
Goal:{goal}

Rules:
1. Select only a worker from the provided registry.
2. Do not invent new workers.
3. Return rejected if none of the workers can reasonably perform the task.
4. Give a short reason for the decision.
5. Return valid JSON only.

Return exactly this schema:
{{
  "decision": "assigned" or "rejected",
  "worker": "worker name or null",
  "reason": "short explanation"
}}
"""

    start = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system","content": "You are a delegation supervisor. Return only valid JSON."},
                  {"role": "user", "content": prompt}],
        temperature=0, timeout=REQUEST_TIMEOUT_SECONDS)

    duration_ms = (time.perf_counter() - start) * 1000

    content = response.choices[0].message.content

    if not content:
        raise ValueError("empty_model_response")

    parsed = json.loads(content)

    parsed["duration_ms"] = round(duration_ms, 2)

    return parsed

def assign_worker(goal: str) -> dict:
    validation = validate_goal(goal)

    if validation["status"] != "success":
        return validation

    registry = build_registry()
    workers = registry.list_workers()

    allowed_workers = {worker["name"] for worker in workers}

    attempts = 0
    last_error = None

    while attempts <= MAX_RETRIES:
        attempts += 1

        try:
            model_result = call_assignment_model(validation["goal"], workers)

            decision = model_result.get("decision")
            worker = model_result.get("worker")
            reason = model_result.get("reason")

            if decision not in {"assigned", "rejected"}:
                return {
                    "status": "rejected",
                    "error": "invalid_model_decision",
                    "attempts": attempts,
                }

            if not isinstance(reason, str) or not reason.strip():
                return {
                    "status": "rejected",
                    "error": "missing_assignment_reason",
                    "attempts": attempts,
                }

            if decision == "rejected":
                return {
                    "status": "rejected",
                    "error": "no_matching_worker",
                    "reason": reason,
                    "attempts": attempts,
                    "duration_ms": model_result.get("duration_ms"),
                }

            if worker not in allowed_workers:
                return {
                    "status": "rejected",
                    "error": "worker_not_allowed",
                    "worker": worker,
                    "reason": reason,
                    "attempts": attempts,
                }

            selected = registry.get_worker(worker)

            return {
                "status": "success",
                "goal": validation["goal"],
                "worker": worker,
                "worker_details": selected["worker"],
                "reason": reason,
                "attempts": attempts,
                "duration_ms": model_result.get("duration_ms"),
            }

        except json.JSONDecodeError as exc:
            last_error = f"invalid_json: {exc}"

        except TimeoutError as exc:
            last_error = f"timeout: {exc}"

        except Exception as exc:
            message = str(exc).lower()

            transient_error = any(text in message
                for text in ["timeout", "temporarily", "rate limit", "429", "500", "502", "503", "504", "connection"])

            last_error = str(exc)

            if not transient_error:
                break

        if attempts <= MAX_RETRIES:
            time.sleep(0.5 * attempts)

    return {
        "status": "failed",
        "error": "assignment_model_failed",
        "details": last_error,
        "attempts": attempts,
    }


if __name__ == "__main__":
    print("=== Assignment Policy ===")

    print("\n=== Happy Path ===")

    happy_result = assign_worker("Research factual information about how AI agent memory works.")

    print(json.dumps(happy_result, indent=2))

    print("\n=== Writing Assignment ===")

    writing_result = assign_worker("Write a short summary explaining the benefits of delegation.")

    print(json.dumps(writing_result, indent=2))

    print("\n=== Rejection Path ===")

    rejected_result = assign_worker("Calculate the monthly salary tax for an employee.")

    print(json.dumps(rejected_result, indent=2))

    output = {
        "happy_path": happy_result,
        "writing_assignment": writing_result,
        "rejection_path": rejected_result,
    }

    output_path = OUTPUT_DIR / "assignment_policy.txt"

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"\nEvidence saved to: {output_path}")