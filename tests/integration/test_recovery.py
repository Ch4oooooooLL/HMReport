from fastapi.testclient import TestClient

from cae_report_server.app import create_app


def test_server_and_worker_restart_resume_interrupted_task(
    client: TestClient,
    project_payload: dict[str, object],
) -> None:
    project = client.post("/api/v1/projects", json=project_payload).json()
    run_id = project["draft_run_id"]
    client.post(f"/api/v1/runs/{run_id}/start").raise_for_status()
    claimed = client.app.state.service.claim_task("worker-before-crash")
    assert claimed and claimed["status"] == "running"

    restarted = create_app(client.app.state.settings)
    with TestClient(restarted) as restarted_client:
        interrupted = restarted_client.get(f"/api/v1/tasks/{claimed['id']}").json()
        assert interrupted["status"] == "interrupted"
        restarted_client.post(
            "/api/v1/internal/workers/register",
            json={"worker_id": "worker-after-crash", "pid": 1, "hostname": "test", "capabilities": ["fem"]},
        ).raise_for_status()
        resumed = restarted_client.get(f"/api/v1/tasks/{claimed['id']}").json()
        assert resumed["status"] == "pending"
        assert restarted_client.get(f"/api/v1/runs/{run_id}").json()["status"] == "queued"

