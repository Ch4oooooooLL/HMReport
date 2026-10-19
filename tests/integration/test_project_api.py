from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from cae_report_worker.executors import TaskExecutor


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


def test_changed_included_fem_blocks_new_run(
    client: TestClient,
    project_payload: dict[str, object],
    source_files: tuple[Path, Path],
) -> None:
    fem, _ = source_files
    include = fem.with_name("body.inc")
    include.write_text("GRID,99,,0.,0.,0.\n", encoding="utf-8")
    fem.write_text(
        fem.read_text(encoding="utf-8").replace("ENDDATA", "INCLUDE 'body.inc'\nENDDATA"),
        encoding="utf-8",
    )
    project = client.post("/api/v1/projects", json=project_payload).json()
    include.write_text("GRID,99,,10.,0.,0.\n", encoding="utf-8")

    blocked_run = client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"name": "include changed", "task_types": ["fem.model_summary"]},
    )

    assert blocked_run.status_code == 409
    assert "SOURCE_CHANGED" in blocked_run.text


def test_rerun_accepts_replaced_sources_and_archives_previous_run(
    client: TestClient,
    project_payload: dict[str, object],
    source_files: tuple[Path, Path],
) -> None:
    project = client.post("/api/v1/projects", json=project_payload).json()
    first_run_id = project["draft_run_id"]
    client.post(f"/api/v1/runs/{first_run_id}/start").raise_for_status()
    service = client.app.state.service
    executor = TaskExecutor(fake_hyperview=True)
    while task := service.claim_task("rerun-test-worker"):
        result = executor.execute(task, lambda *_args: None)
        service.complete_task(task["id"], "completed", result, None, None)
    executor.close()
    first_run = client.get(f"/api/v1/runs/{first_run_id}").json()
    assert first_run["status"] == "completed"
    first_model = client.get(f"/api/v1/runs/{first_run_id}/model-summary").json()

    fem, h3d = source_files
    fem.write_text(fem.read_text(encoding="utf-8") + "$ rerun content\n", encoding="utf-8")
    h3d.write_bytes(h3d.read_bytes() + b"-RERUN")

    rerun_response = client.post(f"/api/v1/projects/{project['id']}/rerun")
    assert rerun_response.status_code == 201, rerun_response.text
    rerun = rerun_response.json()
    assert rerun["run_no"] == 2
    assert rerun["status"] == "queued"
    assert rerun["input_snapshot"]["fem"]["path"] == first_run["input_snapshot"]["fem"]["path"]
    assert rerun["input_snapshot"]["h3d"]["path"] == first_run["input_snapshot"]["h3d"]["path"]
    assert (
        rerun["input_snapshot"]["fem"]["fingerprint"]
        != first_run["input_snapshot"]["fem"]["fingerprint"]
    )
    assert (
        rerun["input_snapshot"]["h3d"]["fingerprint"]
        != first_run["input_snapshot"]["h3d"]["fingerprint"]
    )

    runs = client.get(f"/api/v1/projects/{project['id']}/runs").json()
    assert [item["id"] for item in runs] == [rerun["id"], first_run_id]
    assert client.get(f"/api/v1/runs/{first_run_id}/model-summary").json() == first_model
