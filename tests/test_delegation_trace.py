import delegation_trace

def test_complete_delegation_trace(monkeypatch):
    def fake_assign_worker(goal):
        return {"status": "success",
            "worker": "research_worker",
            "reason": "Research capability matches.",
            "attempts": 1,
            "duration_ms": 10.0}

    def fake_execute_handoff(brief):
        return {"status": "success",
            "worker": "research_worker",
            "goal": brief["goal"],
            "result": "Short-term memory stores temporary context.",
            "result_owner": "supervisor",
            "attempts": 1,
            "duration_ms": 15.0}

    def fake_review_result(goal, expected_output, constraints, worker, result):
        return {
            "status": "success",
            "decision": "accept",
            "worker": worker,
            "reason": "The result satisfies the request.",
            "feedback": "",
            "result_owner": "supervisor",
            "attempts": 1,
            "duration_ms": 12.0}

    monkeypatch.setattr( delegation_trace, "assign_worker", fake_assign_worker)
    monkeypatch.setattr(delegation_trace, "execute_handoff", fake_execute_handoff)
    monkeypatch.setattr(delegation_trace,"review_result", fake_review_result)

    result = delegation_trace.run_delegation(goal="Research AI memory.", context="Beginner learning material.", constraints=["Keep it concise."], expected_output="Short explanation.")

    assert result["status"] == "success"
    assert result["final_state"] == "accepted"
    assert result["review_decision"] == "accept"
    assert result["result_owner"] == "supervisor"
    assert result["step_count"] == 4
    assert result["trace"][0]["step"] == "assignment"
    assert result["trace"][1]["step"] == "handoff"
    assert result["trace"][2]["step"] == "worker_execution"
    assert result["trace"][3]["step"] == "supervisor_review"

def test_invalid_goal_is_rejected():

    result = delegation_trace.run_delegation(goal="", context="Test context.", constraints=[], expected_output="Short answer.")

    assert result["status"] == "rejected"
    assert result["error"] == "invalid_goal"
    assert result["trace"] == []

def test_assignment_failure_stops_execution(monkeypatch):

    def fake_assign_worker(goal):
        return { "status": "rejected", "error": "no_matching_worker"}

    monkeypatch.setattr(delegation_trace, "assign_worker", fake_assign_worker)

    result = delegation_trace.run_delegation(goal="Perform unsupported specialist task.", context="Test.", constraints=[], expected_output="Result.")

    assert result["status"] == "rejected"
    assert result["final_state"] == "assignment_failed"
    assert result["step_count"] == 1

def test_worker_failure_stops_before_review(monkeypatch):

    def fake_assign_worker(goal):
        return {"status": "success", "worker": "research_worker", "reason": "Research worker matches."}

    def fake_execute_handoff(brief):
        return {"status": "failed", "error": "worker_execution_failed", "attempts": 3}

    monkeypatch.setattr(delegation_trace, "assign_worker", fake_assign_worker)
    monkeypatch.setattr(delegation_trace, "execute_handoff", fake_execute_handoff)

    result = delegation_trace.run_delegation(goal="Research AI memory.", context="Test.", constraints=[], expected_output="Short response.")

    assert result["status"] == "failed"
    assert result["final_state"] == "worker_execution_failed"
    assert result["step_count"] == 3

def test_reassign_decision_requires_further_review(monkeypatch):

    def fake_assign_worker(goal):
        return {"status": "success",
            "worker": "research_worker",
            "reason": "Research match."}

    def fake_execute_handoff(brief):
        return {"status": "success",
            "worker": "research_worker",
            "result": "Incomplete result.",
            "result_owner": "supervisor"}

    def fake_review_result(goal, expected_output, constraints, worker, result):
        return {"status": "success",
            "decision": "reassign",
            "reason": "Result needs improvement.",
            "feedback": "Provide structured bullet points.",
            "result_owner": "supervisor"}

    monkeypatch.setattr(delegation_trace, "assign_worker", fake_assign_worker)
    monkeypatch.setattr(delegation_trace, "execute_handoff", fake_execute_handoff)
    monkeypatch.setattr( delegation_trace, "review_result", fake_review_result)

    result = delegation_trace.run_delegation(goal="Research AI memory.", context="Test.", constraints=[], expected_output="Three bullets.")

    assert result["status"] == "needs_review"
    assert result["final_state"] == "reassignment_required"
    assert result["review_decision"] == "reassign"

def test_step_limit_is_defined():
    assert delegation_trace.MAX_STEPS == 4