from fastapi.testclient import TestClient


def test_v1_openapi_contains_required_surfaces(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    required = {
        "/api/v1/projects",
        "/api/v1/projects/{project_id}/runs",
        "/api/v1/projects/{project_id}/rerun",
        "/api/v1/runs/{run_id}/start",
        "/api/v1/runs/{run_id}/model-summary",
        "/api/v1/runs/{run_id}/hotspots",
        "/api/v1/captures/{capture_id}/restore-view",
        "/api/v1/view-restores/{restore_request_id}",
        "/api/v1/runs/{run_id}/report/export-pptx",
    }
    assert required <= set(paths)
