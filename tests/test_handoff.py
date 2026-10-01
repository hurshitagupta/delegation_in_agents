import handoff

def test_valid_handoff_is_created(monkeypatch):
    def fake_assign_worker(goal):
        return {
            "status": "success",
            "worker": "research_worker",
            "reason": "Research capability matches."
        }

    monkeypatch.setattr( handoff, "assign_worker", fake_assign_worker)

    result = handoff.build_handoff(
        goal="Research AI memory.",
        context="Beginner explanation.",
        constraints=["Keep it concise."],
        expected_output="Three bullet points."
    )

    assert result["status"] == "success"
    assert result["handoff"]["assigned_worker"] == "research_worker"
    assert result["handoff"]["result_owner"] == "supervisor"


def test_worker_executes_handoff(monkeypatch):
    def fake_worker_call(brief):
        return {"result": "Short-term memory stores temporary task context.", "duration_ms": 15.0 }

    monkeypatch.setattr(handoff, "call_worker_model", fake_worker_call)

    brief = {
        "goal": "Research AI memory.",
        "context": "Beginner-level material.",
        "constraints": ["Keep it concise."],
        "expected_output": "Short explanation.",
        "assigned_worker": "research_worker",
        "result_owner": "supervisor"
    }

    result = handoff.execute_handoff(brief)

    assert result["status"] == "success"
    assert result["worker"] == "research_worker"
    assert result["result_owner"] == "supervisor"
    assert result["attempts"] == 1

def test_invalid_result_owner_is_rejected():
    brief = {
        "goal": "Research AI memory.",
        "context": "Test context.",
        "constraints": [],
        "expected_output": "Short answer.",
        "assigned_worker": "research_worker",
        "result_owner": "worker"
    }

    result = handoff.execute_handoff(brief)

    assert result["status"] == "rejected"
    assert result["error"] == "invalid_result_owner"

def test_missing_field_is_rejected():
    brief = {
        "goal": "Research AI memory.",
        "context": "Test context.",
        "constraints": [],
        "assigned_worker": "research_worker",
        "result_owner": "supervisor"
    }

    result = handoff.validate_handoff(brief)

    assert result["status"] == "rejected"
    assert result["error"] == "missing_expected_output"

def test_context_limit_is_enforced():
    brief = {
        "goal": "Research AI memory.",
        "context": "x" * 1001,
        "constraints": [],
        "expected_output": "Short answer.",
        "assigned_worker": "research_worker",
        "result_owner": "supervisor"
    }

    result = handoff.validate_handoff(brief)

    assert result["status"] == "rejected"
    assert result["error"] == "context_too_long"

def test_transient_worker_failure_is_retried(monkeypatch):
    calls = {"count": 0}

    def fake_worker_call(brief):
        calls["count"] += 1

        if calls["count"] == 1:
            raise Exception("503 temporarily unavailable")

        return {"result": "Recovered result", "duration_ms": 12.0}

    monkeypatch.setattr(handoff, "call_worker_model", fake_worker_call)

    monkeypatch.setattr(handoff.time, "sleep", lambda _: None)

    brief = {
        "goal": "Research AI memory.",
        "context": "Test context.",
        "constraints": [],
        "expected_output": "Short answer.",
        "assigned_worker": "research_worker",
        "result_owner": "supervisor"
    }

    result = handoff.execute_handoff(brief)

    assert result["status"] == "success"
    assert result["attempts"] == 2
    assert calls["count"] == 2