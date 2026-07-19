from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_project_sources_are_referenced_and_runs_are_historical(client: TestClient, project_payload: dict[str, object], source_files: tuple[Path, Path]) -> None:
    created = client.post("/api/v1/projects", json=project_payload)
    assert created.status_code == 201, created.text
    project = created.json()
    project_path = Path(project["workspace_path"])
    fem, h3d = source_files
    assert project_path.is_dir()
    assert not list(project_path.rglob("*.fem"))
    assert not list(project_path.rglob("*.h3d"))
    assert fem.is_file() and h3d.is_file()
    run = client.post(f"/api/v1/projects/{project['id']}/runs", json={"name": "第二次分析", "task_types": ["fem.model_summary"]})
    assert run.status_code == 201
    runs = client.get(f"/api/v1/projects/{project['id']}/runs").json()
    assert [item["run_no"] for item in runs] == [2, 1]


def test_remove_project_never_deletes_external_sources(client: TestClient, project_payload: dict[str, object], source_files: tuple[Path, Path]) -> None:
    project = client.post("/api/v1/projects", json=project_payload).json()
    response = client.delete(f"/api/v1/projects/{project['id']}")
    assert response.status_code == 204
    assert all(path.is_file() for path in source_files)


def test_changed_source_blocks_old_draft_and_new_run(client: TestClient, project_payload: dict[str, object], source_files: tuple[Path, Path]) -> None:
    project = client.post("/api/v1/projects", json=project_payload).json()
    fem, _ = source_files
    fem.write_text(fem.read_text(encoding="utf-8") + "$ changed\n", encoding="utf-8")
    blocked_start = client.post(f"/api/v1/runs/{project['draft_run_id']}/start")
    assert blocked_start.status_code == 409
    blocked_run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"name": "changed", "task_types": ["fem.model_summary"]},
    )
    assert blocked_run.status_code == 409
