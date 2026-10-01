import result_review

def test_valid_result_is_accepted(monkeypatch):
    def fake_review_model( goal, expected_output, constraints, worker, result):
        return {
            "decision": "accept",
            "reason": "The result satisfies the requested output.",
            "feedback": "",
            "duration_ms": 12.0}

    monkeypatch.setattr(result_review, "call_review_model", fake_review_model)

    result = result_review.review_result(
        goal="Research AI memory.",
        expected_output="Short factual explanation.",
        constraints=["Keep it concise."],
        worker="research_worker",
        result="Short-term memory stores temporary task context.")

    assert result["status"] == "success"
    assert result["decision"] == "accept"
    assert result["result_owner"] == "supervisor"
    assert result["attempts"] == 1

def test_result_can_be_reassigned(monkeypatch):
    def fake_review_model(goal, expected_output, constraints, worker, result):
        return {
            "decision": "reassign",
            "reason": "The result does not match the expected format.",
            "feedback": "Return the answer as 3 concise bullet points.",
            "duration_ms": 10.0,
        }

    monkeypatch.setattr(result_review, "call_review_model", fake_review_model)

    result = result_review.review_result(
        goal="Research AI memory.",
        expected_output="Three bullet points.",
        constraints=["Keep it concise."],
        worker="research_worker",
        result="A long unstructured paragraph.")

    assert result["status"] == "success"
    assert result["decision"] == "reassign"
    assert result["feedback"] != ""

def test_result_can_be_rejected(monkeypatch):
    def fake_review_model(goal, expected_output, constraints, worker, result):
        return {
            "decision": "reject",
            "reason": "The result is unrelated to the delegated goal.",
            "feedback": "",
            "duration_ms": 9.0}

    monkeypatch.setattr(result_review, "call_review_model", fake_review_model)

    result = result_review.review_result(goal="Research AI memory.", expected_output="Short factual explanation.", constraints=[], worker="research_worker", result="This result discusses employee payroll.")

    assert result["status"] == "success"
    assert result["decision"] == "reject"

def test_empty_worker_result_is_rejected():
    result = result_review.review_result(goal="Research AI memory.", expected_output="Short explanation.", constraints=[], worker="research_worker", result="")

    assert result["status"] == "rejected"
    assert result["error"] == "empty_worker_result"

def test_invalid_review_decision_is_rejected(monkeypatch):
    def fake_review_model(goal,expected_output, constraints,worker, result):
        return {
            "decision": "publish",
            "reason": "Looks good.",
            "feedback": "",
            "duration_ms": 8.0,
        }

    monkeypatch.setattr(result_review, "call_review_model", fake_review_model)

    result = result_review.review_result(
        goal="Research AI memory.",
        expected_output="Short explanation.",
        constraints=[],
        worker="research_worker",
        result="Valid result.")

    assert result["status"] == "rejected"
    assert result["error"] == "invalid_review_decision"

def test_transient_review_failure_is_retried(monkeypatch):
    calls = {"count": 0}

    def fake_review_model(goal, expected_output, constraints, worker, result):
        calls["count"] += 1

        if calls["count"] == 1:
            raise Exception("503 temporarily unavailable")

        return {
            "decision": "accept",
            "reason": "Result satisfies requirements.",
            "feedback": "",
            "duration_ms": 11.0}

    monkeypatch.setattr(result_review, "call_review_model", fake_review_model)
    monkeypatch.setattr(result_review.time, "sleep", lambda _: None)

    result = result_review.review_result(
        goal="Research AI memory.",
        expected_output="Short explanation.",
        constraints=[],
        worker="research_worker",
        result="Valid factual explanation.")

    assert result["status"] == "success"
    assert result["decision"] == "accept"
    assert result["attempts"] == 2
    assert calls["count"] == 2