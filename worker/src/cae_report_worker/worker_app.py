from __future__ import annotations

import os
import socket
import time
import uuid
from pathlib import Path

import httpx
from cae_report_shared.json_logging import configure_json_logger

from .executors import TaskExecutor
from .server_client import ServerClient


class WorkerApp:
    def __init__(self, server_url: str, *, poll_interval: float = 0.25, fake_hyperview: bool = True) -> None:
        self.worker_id = f"worker_{uuid.uuid4().hex}"
        self.client = ServerClient(server_url)
        self.executor = TaskExecutor(fake_hyperview=fake_hyperview)
        self.poll_interval = poll_interval
        self.running = True
        log_path = Path(os.environ.get("CAE_REPORT_WORKER_LOG", "runtime/worker.jsonl")).resolve()
        self.logger = configure_json_logger("cae_report.worker", "worker", log_path)

    def register(self) -> None:
        hyperview_capability = "fake-hyperview" if self.executor.fake_hyperview else "real-hyperview"
        self.client.register(
            self.worker_id,
            os.getpid(),
            socket.gethostname(),
            ["fem", "dag", "image-validation", hyperview_capability],
        )
        self.logger.info("Worker registered", extra={"event": "worker.registered", "details": {"worker_id": self.worker_id}})

    def run_once(self) -> bool:
        task = self.client.claim(self.worker_id)
        if task is None:
            action = self.client.claim_action(self.worker_id)
            if action is None:
                self.client.heartbeat(self.worker_id)
                return False
            try:
                result = self.executor.execute_action(action)
                self.client.complete_action(self.worker_id, action["id"], "completed", result)
            except Exception as exc:
                code = str(exc).split(":", 1)[0] if ":" in str(exc) else "ACTION_EXECUTION_FAILED"
                self.client.complete_action(self.worker_id, action["id"], "failed", {}, code, str(exc))
            finally:
                self.executor.release_action_session(str(action["run_id"]))
            return True
        task_id = task["id"]
        try:
            result = self.executor.execute(
                task,
                lambda current, total, message: self.client.progress(self.worker_id, task_id, current, total, message),
            )
            completed = self.client.complete(self.worker_id, task_id, "completed", result)
            self._release_terminal_run(task, completed)
            self.logger.info("Task completed", extra={"event": "task.completed", "task_id": task_id, "run_id": task["run_id"]})
        except Exception as exc:
            code = str(exc).split(":", 1)[0] if ":" in str(exc) else "TASK_EXECUTION_FAILED"
            completed = self.client.complete(self.worker_id, task_id, "failed", {}, code, str(exc))
            self._release_terminal_run(task, completed)
            self.logger.exception("Task failed", extra={"event": "task.failed", "task_id": task_id, "run_id": task["run_id"], "details": {"error_code": code}})
        return True

    def _release_terminal_run(
        self,
        task: dict[str, object],
        completion: dict[str, object],
    ) -> None:
        if completion.get("run_status") in {
            "completed",
            "completed_with_errors",
            "failed",
            "cancelled",
        }:
            self.executor.release_run(str(task["run_id"]))

    def run_forever(self) -> None:
        registered = False
        retry_delay = max(0.5, self.poll_interval)
        while self.running:
            try:
                if not registered:
                    self.register()
                    registered = True
                worked = self.run_once()
                retry_delay = max(0.5, self.poll_interval)
                if not worked:
                    time.sleep(self.poll_interval)
            except httpx.HTTPError as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                registered = False
                self.logger.warning(
                    "Server connection interrupted; retrying",
                    extra={
                        "event": "worker.server_retry",
                        "details": {"error": str(exc), "retry_delay_seconds": retry_delay},
                    },
                )
                time.sleep(retry_delay)
                retry_delay = min(30.0, retry_delay * 2)

    def close(self) -> None:
        self.running = False
        try:
            self.executor.close()
        finally:
            self.client.close()
