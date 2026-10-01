import assignment_policy

def test_valid_assignment(monkeypatch):
    def fake_model_call(goal, workers):
        return {
            "decision": "assigned",
            "worker": "research_worker",
            "reason": "The goal requires research and fact gathering.",
            "duration_ms": 12.5,
        }

    monkeypatch.setattr(assignment_policy, "call_assignment_model", fake_model_call)

    result = assignment_policy.assign_worker("Research factual information about agent memory.")

    assert result["status"] == "success"
    assert result["worker"] == "research_worker"
    assert result["attempts"] == 1


def test_writing_assignment(monkeypatch):
    def fake_model_call(goal, workers):
        return {
            "decision": "assigned",
            "worker": "writing_worker",
            "reason": "The goal requires written content.",
            "duration_ms": 10.0,
        }

    monkeypatch.setattr(assignment_policy, "call_assignment_model", fake_model_call)

    result = assignment_policy.assign_worker("Write a short summary about delegation.")

    assert result["status"] == "success"
    assert result["worker"] == "writing_worker"

def test_unknown_worker_is_rejected(monkeypatch):
    def fake_model_call(goal, workers):
        return {
            "decision": "assigned",
            "worker": "finance_worker",
            "reason": "The task concerns finance.",
            "duration_ms": 8.0,
        }

    monkeypatch.setattr(assignment_policy, "call_assignment_model", fake_model_call)

    result = assignment_policy.assign_worker("Calculate a finance report.")

    assert result["status"] == "rejected"
    assert result["error"] == "worker_not_allowed"

def test_model_can_reject_when_no_worker_matches(monkeypatch):
    def fake_model_call(goal, workers):
        return {
            "decision": "rejected",
            "worker": None,
            "reason": "No registered worker supports this capability.",
            "duration_ms": 8.0,
        }

    monkeypatch.setattr(assignment_policy, "call_assignment_model", fake_model_call)

    result = assignment_policy.assign_worker("Calculate employee payroll taxes.")

    assert result["status"] == "rejected"
    assert result["error"] == "no_matching_worker"

def test_empty_goal_is_rejected():
    result = assignment_policy.assign_worker("")

    assert result["status"] == "rejected"
    assert result["error"] == "empty_goal"

def test_retry_on_transient_failure(monkeypatch):
    calls = {"count": 0}

    def fake_model_call(goal, workers):
        calls["count"] += 1

        if calls["count"] == 1:
            raise Exception("503 temporarily unavailable")

        return {
            "decision": "assigned",
            "worker": "research_worker",
            "reason": "Research capability matches the task.",
            "duration_ms": 11.0,
        }

    monkeypatch.setattr(assignment_policy, "call_assignment_model", fake_model_call)

    monkeypatch.setattr(assignment_policy.time, "sleep", lambda _: None)

    result = assignment_policy.assign_worker("Research AI memory.")

    assert result["status"] == "success"
    assert result["attempts"] == 2
    assert calls["count"] == 2