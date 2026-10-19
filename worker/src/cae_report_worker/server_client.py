from __future__ import annotations

from typing import Any

import httpx


class ServerClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def register(self, worker_id: str, pid: int, hostname: str, capabilities: list[str]) -> None:
        self._post("/api/v1/internal/workers/register", {"worker_id": worker_id, "pid": pid, "hostname": hostname, "capabilities": capabilities})

    def heartbeat(self, worker_id: str, status: str = "ready") -> None:
        self._post("/api/v1/internal/workers/heartbeat", {"worker_id": worker_id, "status": status})

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        response = self._post("/api/v1/internal/tasks/claim", {"worker_id": worker_id})
        return dict(response) if response else None

    def claim_action(self, worker_id: str) -> dict[str, Any] | None:
        response = self._post("/api/v1/internal/actions/claim", {"worker_id": worker_id})
        return dict(response) if response else None

    def progress(self, worker_id: str, task_id: str, current: int, total: int, message: str) -> None:
        self._post(f"/api/v1/internal/tasks/{task_id}/progress", {"worker_id": worker_id, "progress_current": current, "progress_total": total, "message": message})

    def complete(self, worker_id: str, task_id: str, status: str, result: dict[str, Any], error_code: str | None = None, error_message: str | None = None) -> dict[str, Any]:
        response = self._post(
            f"/api/v1/internal/tasks/{task_id}/complete",
            {"worker_id": worker_id, "status": status, "result": result, "error_code": error_code, "error_message": error_message},
            timeout=300.0,
        )
        return dict(response)

    def complete_action(self, worker_id: str, action_id: str, status: str, result: dict[str, Any], error_code: str | None = None, error_message: str | None = None) -> None:
        self._post(f"/api/v1/internal/actions/{action_id}/complete", {"worker_id": worker_id, "status": status, "result": result, "error_code": error_code, "error_message": error_message})

    def _post(self, path: str, payload: dict[str, Any], *, timeout: float = 30.0) -> Any:
        response = self.client.post(path, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json() if response.content else None

    def close(self) -> None:
        self.client.close()
