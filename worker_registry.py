from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable
import json
import time

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_WORKERS = 5
OPERATION_TIMEOUT_SECONDS = 2.0

@dataclass
class Worker:
    name: str
    capabilities: list[str]
    description: str
    handler: Callable[[dict], str]

class WorkerRegistry:
    def __init__(self, max_workers: int = MAX_WORKERS):
        self.max_workers = max_workers
        self._workers: dict[str, Worker] = {}

    def register(self, worker: Worker) -> dict:
        start = time.perf_counter()

        if not worker.name.strip():
            return {"status": "rejected", "error": "invalid_worker_name"}

        if not worker.capabilities:
            return {"status": "rejected", "error": "missing_capabilities"}

        if worker.name in self._workers:
            return {"status": "rejected", "error": "duplicate_worker"}

        if len(self._workers) >= self.max_workers:
            return {"status": "rejected", "error": "worker_limit_reached"}

        self._workers[worker.name] = worker

        elapsed_ms = (time.perf_counter() - start) * 1000

        if elapsed_ms > OPERATION_TIMEOUT_SECONDS * 1000:
            return {"status": "failed", "error": "operation_timeout"}

        return {
            "status": "success",
            "worker": worker.name,
            "capabilities": worker.capabilities,
            "registered_workers": len(self._workers),
            "duration_ms": round(elapsed_ms, 3),
        }

    def get_worker(self, name: str) -> dict:
        worker = self._workers.get(name)

        if worker is None:
            return {"status": "rejected", "error": "worker_not_allowed", "worker": name}

        return {"status": "success",
            "worker": {"name": worker.name, "capabilities": worker.capabilities, "description": worker.description}}

    def find_by_capability(self, capability: str) -> list[str]:
        return [worker.name for worker in self._workers.values() if capability in worker.capabilities]

    def list_workers(self) -> list[dict]:
        return [{
                "name": worker.name,
                "capabilities": worker.capabilities,
                "description": worker.description}
            for worker in self._workers.values()]


def research_handler(brief: dict) -> str:
    return f"Research completed for: {brief['goal']}"

def writing_handler(brief: dict) -> str:
    return f"Draft completed for: {brief['goal']}"

def build_registry() -> WorkerRegistry:
    registry = WorkerRegistry()

    registry.register(
        Worker(name="research_worker", capabilities=["research", "fact_checking", "information_gathering"],
            description="Collects and verifies information.", handler=research_handler))

    registry.register(
        Worker(name="writing_worker", capabilities=["writing", "summarization", "drafting"], description="Produces written drafts and summaries.", handler=writing_handler)
    )

    return registry

if __name__ == "__main__":
    registry = build_registry()

    print("=== Worker Registry ===")

    workers = registry.list_workers()

    print(json.dumps({"registered_workers": workers, "worker_count": len(workers), "max_workers": registry.max_workers},indent=2))

    print("\n=== Happy Path ===")

    result = registry.get_worker("research_worker")
    print(json.dumps(result, indent=2))

    print("\n=== Capability Lookup ===")

    capability_result = registry.find_by_capability("writing")

    print(json.dumps({"capability": "writing", "matching_workers": capability_result},
            indent=2))

    print("\n=== Rejection Path ===")

    rejected = registry.get_worker("unknown_worker")
    print(json.dumps(rejected, indent=2))

    output = {
        "worker_count": len(workers),
        "workers": workers,
        "happy_path": result,
        "capability_lookup": capability_result,
        "rejection_path": rejected,
    }

    output_path = OUTPUT_DIR / "worker_registry.txt"

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"\nEvidence saved to: {output_path}")