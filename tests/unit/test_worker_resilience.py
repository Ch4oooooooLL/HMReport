from __future__ import annotations

import httpx

from cae_report_worker.worker_app import WorkerApp


def test_worker_reconnects_after_transient_server_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CAE_REPORT_WORKER_LOG", str(tmp_path / "worker.jsonl"))
    worker = WorkerApp("http://127.0.0.1:1", poll_interval=0.01)
    registrations: list[str] = []
    attempts = 0

    monkeypatch.setattr(worker, "register", lambda: registrations.append("registered"))

    def run_once() -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("server temporarily unavailable")
        worker.running = False
        return True

    monkeypatch.setattr(worker, "run_once", run_once)
    monkeypatch.setattr("cae_report_worker.worker_app.time.sleep", lambda _seconds: None)

    worker.run_forever()
    worker.close()

    assert attempts == 2
    assert registrations == ["registered", "registered"]
