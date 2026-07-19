from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cae_report_worker.executors import TaskExecutor


def test_full_fake_run_capture_review_and_pptx(client: TestClient, project_payload: dict[str, object]) -> None:
    project = client.post("/api/v1/projects", json=project_payload).json()
    run_id = project["draft_run_id"]
    assert client.post(f"/api/v1/runs/{run_id}/start").status_code == 200
    service = client.app.state.service
    executor = TaskExecutor(fake_hyperview=True)
    completed = 0
    while task := service.claim_task("integration-worker"):
        result = executor.execute(task, lambda current, total, message: service.task_progress(task["id"], current, total, message))
        service.complete_task(task["id"], "completed", result, None, None)
        completed += 1
    assert completed == 10
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "completed"
    model = client.get(f"/api/v1/runs/{run_id}/model-summary").json()
    assert model["node_count"] == 4
    hotspots = client.get(f"/api/v1/runs/{run_id}/hotspots").json()
    assert len(hotspots) == 6
    hotspot = client.get(f"/api/v1/hotspots/{hotspots[0]['id']}").json()
    assert len(hotspot["captures"]) >= 7
    capture = hotspot["captures"][0]
    assert capture["versions"][0]["view_state"]["schema_version"] == 1
    reviewed = client.post(f"/api/v1/captures/{capture['id']}/approve", json={"note": "视角正确"}).json()
    assert reviewed["review_status"] == "approved"
    recapture = client.post(f"/api/v1/captures/{capture['id']}/recapture", json={"note": "更新图例"}).json()
    action = service.claim_action("integration-worker")
    assert action and action["id"] == recapture["id"]
    service.complete_action(action["id"], "completed", executor.execute_action(action), None, None)
    versioned = client.get(f"/api/v1/captures/{capture['id']}").json()
    assert len(versioned["versions"]) == 2
    assert versioned["versions"][0]["image_path"] != versioned["versions"][1]["image_path"]
    restore = client.post(f"/api/v1/captures/{capture['id']}/restore-view", json={"bring_to_front": True}).json()
    assert restore["status"] == "queued"
    action = service.claim_action("integration-worker")
    assert action and action["id"] == restore["id"]
    service.complete_action(action["id"], "completed", executor.execute_action(action), None, None)
    restore_row = client.app.state.db.one("SELECT status FROM view_restore_requests WHERE capture_id=?", (capture["id"],))
    assert restore_row == {"status": "exact"}
    report = client.get(f"/api/v1/runs/{run_id}/report").json()
    assert len(report["slides"]) == 12
    exported = client.post(f"/api/v1/runs/{run_id}/report/export-pptx").json()
    assert exported["status"] == "completed"
    assert Path(exported["path"]).is_file()
    assert Path(exported["path"]).read_bytes()[:2] == b"PK"
