from worker_registry import Worker, WorkerRegistry, build_registry

def dummy_handler(brief: dict) -> str:
    return "done"

def test_registered_worker_can_be_retrieved():
    registry = build_registry()

    result = registry.get_worker("research_worker")

    assert result["status"] == "success"
    assert result["worker"]["name"] == "research_worker"
    assert "research" in result["worker"]["capabilities"]

def test_unknown_worker_is_rejected():
    registry = build_registry()
    result = registry.get_worker("unknown_worker")

    assert result["status"] == "rejected"
    assert result["error"] == "worker_not_allowed"

def test_worker_without_capabilities_is_rejected():
    registry = WorkerRegistry()

    worker = Worker(name="invalid_worker", capabilities=[], description="Invalid test worker.", handler=dummy_handler)

    result = registry.register(worker)

    assert result["status"] == "rejected"
    assert result["error"] == "missing_capabilities"


def test_duplicate_worker_is_rejected():
    registry = WorkerRegistry()

    worker = Worker(name="research_worker", capabilities=["research"], description="Research worker", handler=dummy_handler)

    first = registry.register(worker)
    second = registry.register(worker)

    assert first["status"] == "success"
    assert second["status"] == "rejected"
    assert second["error"] == "duplicate_worker"


def test_worker_limit_is_enforced():
    registry = WorkerRegistry(max_workers=1)

    first_worker = Worker(name="worker_1", capabilities=["research"], description="Worker one", handler=dummy_handler)

    second_worker = Worker(name="worker_2", capabilities=["writing"], description="Worker two", handler=dummy_handler)

    assert registry.register(first_worker)["status"] == "success"

    result = registry.register(second_worker)

    assert result["status"] == "rejected"
    assert result["error"] == "worker_limit_reached"


def test_find_worker_by_capability():
    registry = build_registry()

    workers = registry.find_by_capability("writing")

    assert "writing_worker" in workers