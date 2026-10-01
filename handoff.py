import json
import os
import time
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from assignment_policy import assign_worker

load_dotenv()

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2
MAX_CONTEXT_LENGTH = 1000

client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))

MODEL_NAME = os.getenv("MODEL_NAME")

class HandoffBrief(TypedDict):
    goal: str
    context: str
    constraints: list[str]
    expected_output: str
    assigned_worker: str
    result_owner: str

def validate_handoff(brief: HandoffBrief) -> dict:
    required_fields = ["goal", "context", "constraints", "expected_output", "assigned_worker", "result_owner"]

    for field in required_fields:
        if field not in brief:
            return {"status": "rejected", "error": f"missing_{field}"}

    if not brief["goal"].strip():
        return {"status": "rejected", "error": "empty_goal"}

    if len(brief["context"]) > MAX_CONTEXT_LENGTH:
        return {"status": "rejected", "error": "context_too_long"}

    if not isinstance(brief["constraints"], list):
        return {"status": "rejected", "error": "constraints_must_be_list"}

    if brief["result_owner"] != "supervisor":
        return {"status": "rejected", "error": "invalid_result_owner"}

    return {"status": "success"}

def build_handoff(goal: str, context: str, constraints: list[str], expected_output: str) -> dict:
    assignment = assign_worker(goal)

    if assignment["status"] != "success":
        return {
            "status": "rejected",
            "error": "assignment_failed",
            "assignment": assignment,
        }

    brief: HandoffBrief = {
        "goal": goal.strip(),
        "context": context.strip(),
        "constraints": constraints,
        "expected_output": expected_output.strip(),
        "assigned_worker": assignment["worker"],
        "result_owner": "supervisor",
    }

    validation = validate_handoff(brief)

    if validation["status"] != "success":
        return validation

    return {
        "status": "success",
        "handoff": brief,
        "assignment_reason": assignment["reason"],
    }


def call_worker_model(brief: HandoffBrief) -> dict:
    worker = brief["assigned_worker"]

    if worker == "research_worker":
        role_instruction = "You are a research worker. Provide factual, concise, well-structured findings. Do not claim access to sources you did not actually receive."

    elif worker == "writing_worker":
        role_instruction = "You are a writing worker. Create clear, concise written content matching the requested output."

    else:
        raise ValueError("worker_not_allowed")

    prompt = f""" You have received a delegated task.

Goal:{brief["goal"]}
Context:{brief["context"]}
Constraints: {json.dumps(brief["constraints"], indent=2)}
Expected output: {brief["expected_output"]}

Important:
- Stay within the delegated goal.
- Follow all constraints.
- Do not perform unrelated work.
- Return only the delegated work result.
"""
    start = time.perf_counter()

    response = client.chat.completions.create(model=MODEL_NAME,
        messages=[{"role": "system", "content": role_instruction},
                {"role": "user", "content": prompt}],
        temperature=0, timeout=REQUEST_TIMEOUT_SECONDS)

    duration_ms = (time.perf_counter() - start) * 1000

    content = response.choices[0].message.content

    if not content or not content.strip():
        raise ValueError("empty_worker_result")

    return {"result": content.strip(), "duration_ms": round(duration_ms, 2)}

def execute_handoff(brief: HandoffBrief) -> dict:
    validation = validate_handoff(brief)

    if validation["status"] != "success":
        return validation

    attempts = 0
    last_error = None

    while attempts <= MAX_RETRIES:
        attempts += 1

        try:
            worker_result = call_worker_model(brief)

            return {
                "status": "success",
                "worker": brief["assigned_worker"],
                "goal": brief["goal"],
                "result": worker_result["result"],
                "result_owner": brief["result_owner"],
                "attempts": attempts,
                "duration_ms": worker_result["duration_ms"]
            }

        except Exception as exc:
            message = str(exc).lower()
            last_error = str(exc)

            transient_error = any(text in message
                for text in ["timeout", "temporarily", "rate limit", "429", "500", "502", "503", "504", "connection"])

            if not transient_error:
                break

        if attempts <= MAX_RETRIES:
            time.sleep(0.5 * attempts)

    return {
        "status": "failed",
        "error": "worker_execution_failed",
        "details": last_error,
        "attempts": attempts
    }

if __name__ == "__main__":
    print("=== Handoff ===")

    print("\n=== Happy Path ===")

    handoff_result = build_handoff(
        goal="Research factual information about short-term memory in AI agents.",
        context="This will be used in a beginner-level explanation of agent memory.",
        constraints=["Keep the response concise.","Use simple language.", "Do not invent citations."],
        expected_output="A short factual explanation in 3 to 5 bullet points.",
    )

    print(json.dumps(handoff_result, indent=2))

    execution_result = None

    if handoff_result["status"] == "success":
        print("\n=== Worker Execution ===")

        execution_result = execute_handoff(handoff_result["handoff"])

        print(json.dumps(execution_result, indent=2))

    print("\n=== Rejection Path ===")

    invalid_brief: HandoffBrief = {
        "goal": "Research AI memory",
        "context": "Test context",
        "constraints": ["Keep it concise"],
        "expected_output": "Short explanation",
        "assigned_worker": "research_worker",
        "result_owner": "worker",
    }

    rejected_result = execute_handoff(invalid_brief)

    print(json.dumps(rejected_result, indent=2))

    output = {
        "handoff_creation": handoff_result,
        "worker_execution": execution_result,
        "rejection_path": rejected_result,
    }

    output_path = OUTPUT_DIR / "handoff.txt"

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
