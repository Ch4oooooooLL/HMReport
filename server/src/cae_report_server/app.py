from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import sys
import uuid
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from cae_report_shared.json_logging import configure_json_logger
from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Database
from .reporting import default_report, export_pptx
from .schemas import (
    ProjectCreate,
    ProjectPatch,
    ReportUpdate,
    RestoreRequest,
    ReviewRequest,
    RunCreate,
    SourceCreate,
    TaskComplete,
    TaskProgress,
    WorkerHeartbeat,
    WorkerRegister,
)
from .services import WorkbenchService, new_id, now
from .settings import Settings


class EventHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def publish(self, event: str, payload: dict[str, Any]) -> None:
        message = {"event": event, "timestamp": now(), "payload": payload}
        dead: list[WebSocket] = []
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or Settings(Path(os.environ.get("CAE_REPORT_WORKSPACE", "C:/CAEReportWorkbench")))
    active.ensure()
    db = Database(active.database_path)
    db.initialize()
    # A previous process may have exited between heartbeat updates. Preserve
    # completed results, mark only in-flight work interrupted, and let the next
    # registered Worker resume it within max-attempt limits.
    db.execute("UPDATE run_tasks SET status='interrupted' WHERE status='running'")
    db.execute("UPDATE analysis_runs SET status='interrupted' WHERE status='running'")
    db.execute("UPDATE action_jobs SET status='queued',started_at=NULL WHERE status='running'")
    service = WorkbenchService(db, active.projects_path)
    events = EventHub()
    logger = configure_json_logger("cae_report.server", "server", active.workspace / "app" / "logs" / "server.jsonl")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="CAE Result Analysis & Report Workbench", version="0.1.0", lifespan=lifespan)
    app.state.settings = active
    app.state.db = db
    app.state.service = service
    app.state.events = events

    @app.middleware("http")
    async def request_log(request: Any, call_next: Any) -> Any:
        started = asyncio.get_running_loop().time()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Request failed",
                extra={"event": "http.request_failed", "details": {"method": request.method, "path": request.url.path}},
            )
            raise
        logger.info(
            "Request completed",
            extra={
                "event": "http.request",
                "details": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
                },
            },
        )
        return response

    @app.exception_handler(KeyError)
    async def key_error_handler(_request: Any, exc: KeyError) -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content={"detail": f"not found: {exc.args[0]}"})

    @app.get("/health")
    def health() -> dict[str, Any]:
        worker = db.one("SELECT status,heartbeat_at FROM workers ORDER BY heartbeat_at DESC LIMIT 1")
        return {
            "status": "ready",
            "version": "0.1.0",
            "database": "ok" if db.integrity() == "ok" else "degraded",
            "worker": worker["status"] if worker else "disconnected",
        }

    @app.get("/api/v1/projects")
    def list_projects() -> list[dict[str, Any]]:
        return service.list_projects()

    @app.post("/api/v1/projects", status_code=201)
    async def create_project(request: ProjectCreate) -> dict[str, Any]:
        try:
            result = service.create_project(request)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        await events.publish("project.updated", {"project_id": result["id"]})
        return result

    @app.get("/api/v1/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        return service.get_project(project_id)

    @app.patch("/api/v1/projects/{project_id}")
    async def patch_project(project_id: str, request: ProjectPatch) -> dict[str, Any]:
        result = service.patch_project(project_id, request.model_dump(exclude_unset=True))
        await events.publish("project.updated", {"project_id": project_id})
        return result

    @app.delete("/api/v1/projects/{project_id}", status_code=204)
    def delete_project(project_id: str, remove_only: bool = Query(False)) -> None:
        service.delete_project(project_id, remove_only=remove_only)

    @app.post("/api/v1/projects/{project_id}/archive")
    def archive_project(project_id: str) -> dict[str, Any]:
        return service.archive_project(project_id)

    @app.post("/api/v1/projects/{project_id}/reveal-folder")
    def reveal_project(project_id: str) -> dict[str, Any]:
        project = service.get_project(project_id)
        if os.name == "nt":
            os.startfile(project["workspace_path"])
        return {"success": True}

    @app.get("/api/v1/projects/{project_id}/sources")
    def list_sources(project_id: str) -> list[dict[str, Any]]:
        return service.list_sources(project_id)

    @app.post("/api/v1/projects/{project_id}/sources", status_code=201)
    def add_source(project_id: str, request: SourceCreate) -> dict[str, Any]:
        return service.add_source(project_id, request)

    @app.patch("/api/v1/sources/{source_id}")
    def patch_source(source_id: str, request: SourceCreate) -> dict[str, Any]:
        source = db.one("SELECT project_id FROM result_sources WHERE id=?", (source_id,))
        if source is None:
            raise KeyError(source_id)
        return service.add_source(source["project_id"], request)

    @app.post("/api/v1/sources/{source_id}/verify")
    def verify_source(source_id: str) -> dict[str, Any]:
        return service.verify_source_id(source_id)

    @app.post("/api/v1/sources/{source_id}/relocate")
    def relocate_source(source_id: str, request: SourceCreate) -> dict[str, Any]:
        return patch_source(source_id, request)

    @app.get("/api/v1/projects/{project_id}/runs")
    def list_runs(project_id: str) -> list[dict[str, Any]]:
        return service.list_runs(project_id)

    @app.post("/api/v1/projects/{project_id}/runs", status_code=201)
    async def create_run(project_id: str, request: RunCreate) -> dict[str, Any]:
        try:
            result = service.create_run(project_id, request)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        await events.publish("run.created", {"run_id": result["id"], "project_id": project_id})
        return result

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return service.get_run(run_id)

    @app.post("/api/v1/runs/{run_id}/start")
    async def start_run(run_id: str) -> dict[str, Any]:
        try:
            result = service.start_run(run_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        await events.publish("run.started", {"run_id": run_id})
        return result

    @app.post("/api/v1/runs/{run_id}/pause")
    async def pause_run(run_id: str) -> dict[str, Any]:
        result = service.control_run(run_id, "pause")
        await events.publish("run.paused", {"run_id": run_id})
        return result

    @app.post("/api/v1/runs/{run_id}/resume")
    def resume_run(run_id: str) -> dict[str, Any]:
        return service.control_run(run_id, "resume")

    @app.post("/api/v1/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, Any]:
        return service.control_run(run_id, "cancel")

    @app.post("/api/v1/runs/{run_id}/retry-failed")
    def retry_failed(run_id: str) -> dict[str, Any]:
        return service.retry_failed(run_id)

    @app.get("/api/v1/runs/{run_id}/tasks")
    def list_tasks(run_id: str) -> list[dict[str, Any]]:
        return service.list_tasks(run_id)

    @app.get("/api/v1/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        return service.get_task(task_id)

    @app.get("/api/v1/tasks/{task_id}/events")
    def task_events(task_id: str) -> list[dict[str, Any]]:
        return db.all("SELECT * FROM task_events WHERE task_id=? ORDER BY id", (task_id,))

    for route_kind in ("model-summary", "mesh-summary", "components", "materials", "properties", "boundary-conditions", "subcases", "result-index", "hotspots"):
        def make_handler(kind: str) -> Any:
            def handler(run_id: str) -> Any:
                return service.model_data(run_id, kind)

            return handler

        app.get(f"/api/v1/runs/{{run_id}}/{route_kind}", name=f"get_{route_kind.replace('-', '_')}")(make_handler(route_kind))

    @app.get("/api/v1/hotspots/{hotspot_id}")
    def get_hotspot(hotspot_id: str) -> dict[str, Any]:
        return service.get_hotspot(hotspot_id)

    @app.get("/api/v1/hotspots/{hotspot_id}/captures")
    def hotspot_captures(hotspot_id: str) -> list[dict[str, Any]]:
        return service.captures_for_hotspot(hotspot_id)

    @app.get("/api/v1/captures/{capture_id}")
    def get_capture(capture_id: str) -> dict[str, Any]:
        return service.get_capture(capture_id)

    @app.post("/api/v1/captures/{capture_id}/approve")
    async def approve_capture(capture_id: str, request: ReviewRequest) -> dict[str, Any]:
        result = service.review_capture(capture_id, "approve", request.note)
        await events.publish("capture.updated", {"capture_id": capture_id, "status": "approved"})
        return result

    @app.post("/api/v1/captures/{capture_id}/reject")
    async def reject_capture(capture_id: str, request: ReviewRequest) -> dict[str, Any]:
        result = service.review_capture(capture_id, "reject", request.note)
        await events.publish("capture.updated", {"capture_id": capture_id, "status": "rejected"})
        return result

    @app.post("/api/v1/captures/{capture_id}/recapture")
    async def recapture(capture_id: str, request: ReviewRequest) -> dict[str, Any]:
        service.review_capture(capture_id, "recapture", request.note)
        result = service.queue_capture_action(capture_id, "capture.recapture")
        await events.publish("capture.updated", {"capture_id": capture_id, "status": "recapture_requested"})
        return result

    @app.post("/api/v1/captures/{capture_id}/restore-view")
    async def restore_view(capture_id: str, request: RestoreRequest) -> dict[str, Any]:
        result = service.restore_capture(capture_id, request.bring_to_front)
        await events.publish("task.started", {"task_type": "view.restore", **result})
        return result

    def version_file(version_id: str, field: str) -> FileResponse:
        row = db.one("SELECT image_path,thumbnail_path FROM capture_versions WHERE id=?", (version_id,))
        if row is None:
            raise KeyError(version_id)
        path = Path(row[field])
        if not path.is_file():
            raise HTTPException(404, "capture file missing")
        return FileResponse(path, media_type="image/png")

    @app.get("/api/v1/capture-versions/{version_id}/image")
    def capture_image(version_id: str) -> FileResponse:
        return version_file(version_id, "image_path")

    @app.get("/api/v1/capture-versions/{version_id}/thumbnail")
    def capture_thumbnail(version_id: str) -> FileResponse:
        return version_file(version_id, "thumbnail_path")

    @app.get("/api/v1/runs/{run_id}/report")
    def get_report(run_id: str) -> dict[str, Any]:
        return service.get_report(run_id)

    @app.put("/api/v1/runs/{run_id}/report")
    def update_report(run_id: str, request: ReportUpdate) -> dict[str, Any]:
        return service.save_report(run_id, request.document)

    @app.post("/api/v1/runs/{run_id}/report/generate-default")
    def generate_default_report(run_id: str) -> dict[str, Any]:
        run = service.get_run(run_id)
        project = service.get_project(run["project_id"])
        data: dict[str, Any] = {}
        for key, kind in {
            "model_summary": "model-summary",
            "mesh_summary": "mesh-summary",
            "materials": "materials",
            "properties": "properties",
            "boundary_conditions": "boundary-conditions",
            "subcases": "subcases",
            "hotspots": "hotspots",
        }.items():
            data[key] = service.model_data(run_id, kind)
        return service.save_report(run_id, default_report(run_id, project, data))

    @app.post("/api/v1/runs/{run_id}/report/export-pptx")
    async def export_report(run_id: str) -> dict[str, Any]:
        document = service.get_report(run_id)
        run = service.get_run(run_id)
        project = service.get_project(run["project_id"])
        export_id = new_id("export")
        target = Path(project["workspace_path"]) / "exports" / f"{run['name']}-{export_id[-8:]}.pptx"
        db.execute("INSERT INTO report_exports(id,report_id,status,path,created_at) VALUES(?,?, 'running',?,?)", (export_id, document["id"], str(target), now()))
        await events.publish("report.export_started", {"export_id": export_id, "run_id": run_id})
        try:
            await asyncio.to_thread(export_pptx, document, target)
            db.execute("UPDATE report_exports SET status='completed',finished_at=? WHERE id=?", (now(), export_id))
        except Exception as exc:
            db.execute("UPDATE report_exports SET status='failed',error_message=?,finished_at=? WHERE id=?", (str(exc), now(), export_id))
            raise HTTPException(500, "REPORT_EXPORT_FAILED") from exc
        await events.publish("report.export_completed", {"export_id": export_id, "run_id": run_id})
        return get_export(export_id)

    @app.get("/api/v1/report-exports/{export_id}")
    def get_export(export_id: str) -> dict[str, Any]:
        row = db.one("SELECT * FROM report_exports WHERE id=?", (export_id,))
        if row is None:
            raise KeyError(export_id)
        row["download_url"] = f"/api/v1/report-exports/{export_id}/download" if row["status"] == "completed" else None
        return row

    @app.get("/api/v1/report-exports/{export_id}/download")
    def download_export(export_id: str) -> FileResponse:
        row = get_export(export_id)
        if row["status"] != "completed" or not Path(row["path"]).is_file():
            raise HTTPException(404, "export unavailable")
        return FileResponse(row["path"], filename=Path(row["path"]).name)

    @app.post("/api/v1/diagnostics/export")
    def export_diagnostics() -> dict[str, Any]:
        diagnostics = active.workspace / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        diagnostic_id = f"diagnostics-{uuid.uuid4().hex[:12]}"
        target = diagnostics / f"{diagnostic_id}.zip"
        summary = {
            "created_at": now(),
            "version": "0.1.0",
            "database_integrity": db.integrity(),
            "schema_version": db.one("SELECT MAX(version) AS version FROM schema_migrations"),
            "projects": db.all("SELECT id,name,status,created_at,updated_at FROM projects"),
            "runs": db.all("SELECT id,project_id,run_no,status,created_at,started_at,finished_at,error_summary FROM analysis_runs"),
            "tasks": db.all("SELECT id,run_id,task_type,status,attempt_count,error_code,error_message FROM run_tasks"),
        }
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostics.json", json.dumps(summary, ensure_ascii=False, indent=2))
            logs_root = active.workspace / "app" / "logs"
            if logs_root.is_dir():
                for log_path in logs_root.glob("*.jsonl"):
                    archive.write(log_path, f"logs/{log_path.name}")
        return {"id": diagnostic_id, "download_url": f"/api/v1/diagnostics/{diagnostic_id}/download"}

    @app.get("/api/v1/diagnostics/{diagnostic_id}/download")
    def download_diagnostics(diagnostic_id: str) -> FileResponse:
        if not re.fullmatch(r"diagnostics-[0-9a-f]{12}", diagnostic_id):
            raise HTTPException(400, "invalid diagnostic id")
        target = active.workspace / "diagnostics" / f"{diagnostic_id}.zip"
        if not target.is_file():
            raise HTTPException(404, "diagnostic package missing")
        return FileResponse(target, filename=target.name)

    @app.post("/api/v1/internal/workers/register")
    async def register_worker(request: WorkerRegister) -> dict[str, Any]:
        timestamp = now()
        db.execute(
            """INSERT INTO workers(id,pid,hostname,status,capabilities_json,registered_at,heartbeat_at)
               VALUES(?,?,?,'ready',?,?,?) ON CONFLICT(id) DO UPDATE SET pid=excluded.pid,
               hostname=excluded.hostname,status='ready',capabilities_json=excluded.capabilities_json,heartbeat_at=excluded.heartbeat_at""",
            (request.worker_id, request.pid, request.hostname, json.dumps(request.capabilities), timestamp, timestamp),
        )
        db.execute(
            """UPDATE run_tasks SET status='pending',started_at=NULL,finished_at=NULL
               WHERE status='interrupted' AND attempt_count < max_attempts"""
        )
        db.execute(
            """UPDATE analysis_runs SET status='queued'
               WHERE status='interrupted' AND EXISTS(
                 SELECT 1 FROM run_tasks t WHERE t.run_id=analysis_runs.id AND t.status='pending'
               )"""
        )
        await events.publish("worker.status", {"worker_id": request.worker_id, "status": "connected"})
        return {"status": "registered", "worker_id": request.worker_id}

    @app.post("/api/v1/internal/workers/heartbeat")
    def worker_heartbeat(request: WorkerHeartbeat) -> dict[str, Any]:
        db.execute("UPDATE workers SET status=?,heartbeat_at=? WHERE id=?", (request.status, now(), request.worker_id))
        return {"status": "ok"}

    @app.post("/api/v1/internal/tasks/claim")
    async def claim_task(worker_id: str = Body(embed=True)) -> dict[str, Any] | None:
        task = service.claim_task(worker_id)
        if task:
            await events.publish("task.started", {"task_id": task["id"], "run_id": task["run_id"], "task_type": task["task_type"]})
        return task

    @app.post("/api/v1/internal/tasks/{task_id}/progress")
    async def task_progress(task_id: str, request: TaskProgress) -> dict[str, Any]:
        task = service.task_progress(task_id, request.progress_current, request.progress_total, request.message)
        await events.publish("task.progress", {"task_id": task_id, "run_id": task["run_id"], "current": request.progress_current, "total": request.progress_total, "message": request.message})
        return task

    @app.post("/api/v1/internal/tasks/{task_id}/complete")
    async def task_complete(task_id: str, request: TaskComplete) -> dict[str, Any]:
        task = service.complete_task(task_id, request.status, request.result, request.error_code, request.error_message)
        event = "task.failed" if request.status == "failed" else "task.completed"
        await events.publish(event, {"task_id": task_id, "run_id": task["run_id"], "status": request.status})
        run = service.get_run(task["run_id"])
        await events.publish("run.progress", {"run_id": run["id"], "status": run["status"], "progress": run["progress"]})
        if run["status"] in {"completed", "completed_with_errors", "failed", "cancelled"}:
            await events.publish("run.completed", {"run_id": run["id"], "status": run["status"]})
        return task

    @app.post("/api/v1/internal/actions/claim")
    def claim_action(worker_id: str = Body(embed=True)) -> dict[str, Any] | None:
        return service.claim_action(worker_id)

    @app.post("/api/v1/internal/actions/{action_id}/complete")
    async def complete_action(action_id: str, request: TaskComplete) -> dict[str, Any]:
        action = service.complete_action(action_id, request.status, request.result, request.error_code, request.error_message)
        await events.publish("capture.updated", {"capture_id": action["capture_id"], "action": action["kind"], "status": action["status"]})
        return action

    @app.websocket("/ws/v1/events")
    async def event_socket(websocket: WebSocket) -> None:
        if websocket.client and websocket.client.host not in {"127.0.0.1", "::1", "testclient"}:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        events.clients.add(websocket)
        try:
            await websocket.send_json({"event": "server.status", "timestamp": now(), "payload": {"status": "ready"}})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            events.clients.discard(websocket)

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        frontend_dist = Path(sys._MEIPASS) / "frontend" / "dist"
    else:
        frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (frontend_dist / path).resolve()
            if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
