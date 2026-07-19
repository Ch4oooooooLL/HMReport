from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import Database, decode_json_fields
from .schemas import TASK_TYPES, ProjectCreate, RunCreate, SourceCreate

TASK_DEPENDENCIES: dict[str, set[str]] = {
    "fem.mesh_summary": {"fem.model_summary"},
    "fem.material_property": {"fem.model_summary"},
    "fem.boundary_conditions": {"fem.model_summary"},
    "fem.subcases": {"fem.model_summary"},
    "result.stress_hotspots": {"h3d.result_index"},
    "result.displacement_hotspots": {"h3d.result_index"},
    "capture.standard_views": {"h3d.result_index"},
    "report.prepare": {
        "fem.model_summary",
        "fem.mesh_summary",
        "fem.material_property",
        "fem.boundary_conditions",
        "fem.subcases",
        "h3d.result_index",
    },
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return slug[:48] or "project"


def file_fingerprint(path: Path, *, fast: bool | None = None) -> tuple[str, str]:
    stat = path.stat()
    use_fast = fast if fast is not None else path.suffix.lower() == ".h3d"
    digest = hashlib.sha256()
    if use_fast and stat.st_size > 8 * 1024 * 1024:
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
        with path.open("rb") as stream:
            digest.update(stream.read(4 * 1024 * 1024))
            stream.seek(max(0, stat.st_size - 4 * 1024 * 1024))
            digest.update(stream.read(4 * 1024 * 1024))
        return "fast-sha256", digest.hexdigest()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256", digest.hexdigest()


def verify_source(path: Path, source_type: str) -> dict[str, Any]:
    if not path.exists():
        return {"availability": "missing", "error": "SOURCE_MISSING"}
    if not path.is_file() or not os.access(path, os.R_OK):
        return {"availability": "unreadable", "error": "SOURCE_UNREADABLE"}
    allowed = {
        "fem": {".fem", ".bdf", ".dat", ".nas"},
        "h3d": {".h3d"},
        "out": {".out"},
        "op2": {".op2"},
        "xlsx": {".xlsx", ".xls"},
    }
    if source_type in allowed and path.suffix.lower() not in allowed[source_type]:
        return {"availability": "unsupported", "error": "SOURCE_UNSUPPORTED"}
    fingerprint_type, fingerprint = file_fingerprint(path)
    stat = path.stat()
    return {
        "availability": "available",
        "fingerprint_type": fingerprint_type,
        "fingerprint": fingerprint,
        "size_bytes": stat.st_size,
        "modified_time_ns": stat.st_mtime_ns,
    }


def expand_tasks(selected: list[str]) -> list[str]:
    expanded = set(selected)
    changed = True
    while changed:
        changed = False
        for task_type in list(expanded):
            for dependency in TASK_DEPENDENCIES.get(task_type, set()):
                if dependency not in expanded:
                    expanded.add(dependency)
                    changed = True
    return [task_type for task_type in TASK_TYPES if task_type in expanded]


class WorkbenchService:
    def __init__(self, db: Database, projects_root: Path) -> None:
        self.db = db
        self.projects_root = projects_root.resolve()

    def project_path(self, project: dict[str, Any]) -> Path:
        return Path(str(project["workspace_path"])).resolve()

    def create_project(self, request: ProjectCreate) -> dict[str, Any]:
        fem = Path(request.fem_path).expanduser().resolve()
        h3d = Path(request.h3d_path).expanduser().resolve()
        fem_check = verify_source(fem, "fem")
        h3d_check = verify_source(h3d, "h3d")
        if fem_check["availability"] != "available":
            raise ValueError(f"FEM source invalid: {fem_check['availability']}")
        if h3d_check["availability"] != "available":
            raise ValueError(f"H3D source invalid: {h3d_check['availability']}")

        project_id = new_id("prj")
        requested_root = Path(request.workspace_path).expanduser().resolve()
        requested_root.mkdir(parents=True, exist_ok=True)
        if not os.access(requested_root, os.W_OK):
            raise ValueError("WORKSPACE_NOT_WRITABLE")
        project_path = requested_root / f"{slugify(request.name)}_{project_id[-8:]}"
        project_path.mkdir(parents=False, exist_ok=False)
        for name in (
            "artifacts",
            "captures",
            "thumbnails",
            "reports",
            "exports",
            "logs",
            "cache",
            "runtime",
            "backups",
        ):
            (project_path / name).mkdir()
        timestamp = now()
        project_doc = {
            "id": project_id,
            "name": request.name,
            "code": request.code,
            "workspace_path": str(project_path),
            "sources": {"fem": str(fem), "h3d": str(h3d)},
            "created_at": timestamp,
        }
        (project_path / "project.json").write_text(
            json.dumps(project_doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            with self.db.connect() as connection:
                connection.execute(
                    """INSERT INTO projects(id,name,code,product,analysis_type,solver,unit_system,description,
                       workspace_path,status,created_at,updated_at,last_opened_at)
                       VALUES(?,?,?,?,?,?,?,?,?,'ready',?,?,?)""",
                    (
                        project_id,
                        request.name,
                        request.code,
                        request.product,
                        request.analysis_type,
                        request.solver,
                        request.unit_system,
                        request.description,
                        str(project_path),
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
            self.add_source(project_id, SourceCreate(source_type="fem", absolute_path=str(fem)))
            self.add_source(project_id, SourceCreate(source_type="h3d", absolute_path=str(h3d)))
            run = self.create_run(
                project_id,
                RunCreate(name="初始分析", task_types=request.task_types, configuration={}),
            )
        except Exception:
            shutil.rmtree(project_path, ignore_errors=True)
            self.db.execute("DELETE FROM projects WHERE id=?", (project_id,))
            raise
        project = self.get_project(project_id)
        project["draft_run_id"] = run["id"]
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.db.all(
            """SELECT p.*, (SELECT status FROM analysis_runs r WHERE r.project_id=p.id
            ORDER BY run_no DESC LIMIT 1) AS latest_run_status,
            (SELECT id FROM analysis_runs r WHERE r.project_id=p.id ORDER BY run_no DESC LIMIT 1) AS latest_run_id
            FROM projects p ORDER BY COALESCE(last_opened_at, updated_at) DESC"""
        )
        return rows

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM projects WHERE id=?", (project_id,))
        if row is None:
            raise KeyError(project_id)
        row["sources"] = self.list_sources(project_id)
        row["runs"] = self.list_runs(project_id)
        return row

    def patch_project(self, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "code", "product", "analysis_type", "solver", "unit_system", "description"}
        changes = {key: value for key, value in values.items() if key in allowed and value is not None}
        if changes:
            changes["updated_at"] = now()
            sql = ",".join(f"{key}=?" for key in changes)
            self.db.execute(f"UPDATE projects SET {sql} WHERE id=?", (*changes.values(), project_id))
        return self.get_project(project_id)

    def archive_project(self, project_id: str) -> dict[str, Any]:
        self.db.execute("UPDATE projects SET status='archived',updated_at=? WHERE id=?", (now(), project_id))
        return self.get_project(project_id)

    def delete_project(self, project_id: str, *, remove_only: bool = False) -> None:
        project = self.get_project(project_id)
        project_path = self.project_path(project)
        source_paths = {Path(item["absolute_path"]).resolve() for item in project["sources"]}
        self.db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        if not remove_only and project_path.exists():
            if project_path in source_paths or any(project_path == p.parent for p in source_paths):
                raise ValueError("PROJECT_DELETE_FAILED: source path overlaps project workspace")
            shutil.rmtree(project_path)

    def add_source(self, project_id: str, request: SourceCreate) -> dict[str, Any]:
        if self.db.one("SELECT id FROM projects WHERE id=?", (project_id,)) is None:
            raise KeyError(project_id)
        path = Path(request.absolute_path)
        check = verify_source(path, request.source_type)
        timestamp = now()
        source_id = new_id("src")
        self.db.execute(
            """INSERT INTO result_sources(id,project_id,source_type,absolute_path,filename,extension,size_bytes,
               modified_time_ns,fingerprint_type,fingerprint,availability,last_verified_at,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id,source_type) DO UPDATE SET absolute_path=excluded.absolute_path,
               filename=excluded.filename,extension=excluded.extension,size_bytes=excluded.size_bytes,
               modified_time_ns=excluded.modified_time_ns,fingerprint_type=excluded.fingerprint_type,
               fingerprint=excluded.fingerprint,availability=excluded.availability,
               last_verified_at=excluded.last_verified_at,updated_at=excluded.updated_at""",
            (
                source_id,
                project_id,
                request.source_type,
                str(path),
                path.name,
                path.suffix.lower(),
                check.get("size_bytes", 0),
                check.get("modified_time_ns", 0),
                check.get("fingerprint_type", "none"),
                check.get("fingerprint", ""),
                check["availability"],
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        row = self.db.one(
            "SELECT * FROM result_sources WHERE project_id=? AND source_type=?",
            (project_id, request.source_type),
        )
        assert row is not None
        return row

    def list_sources(self, project_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM result_sources WHERE project_id=? ORDER BY source_type", (project_id,))

    def verify_source_id(self, source_id: str) -> dict[str, Any]:
        source = self.db.one("SELECT * FROM result_sources WHERE id=?", (source_id,))
        if source is None:
            raise KeyError(source_id)
        path = Path(source["absolute_path"])
        check = verify_source(path, source["source_type"])
        availability = check["availability"]
        if availability == "available" and source["fingerprint"] != check["fingerprint"]:
            availability = "changed"
        fingerprint_type = check.get("fingerprint_type", source["fingerprint_type"])
        fingerprint = check.get("fingerprint", source["fingerprint"])
        if availability == "changed":
            # Keep the accepted fingerprint until the user explicitly relocates
            # or re-accepts the source. A second verify must not silently clear
            # SOURCE_CHANGED.
            fingerprint_type = source["fingerprint_type"]
            fingerprint = source["fingerprint"]
        self.db.execute(
            """UPDATE result_sources SET size_bytes=?,modified_time_ns=?,fingerprint_type=?,fingerprint=?,
               availability=?,last_verified_at=?,updated_at=? WHERE id=?""",
            (
                check.get("size_bytes", 0),
                check.get("modified_time_ns", 0),
                fingerprint_type,
                fingerprint,
                availability,
                now(),
                now(),
                source_id,
            ),
        )
        result = self.db.one("SELECT * FROM result_sources WHERE id=?", (source_id,))
        assert result is not None
        return result

    def create_run(self, project_id: str, request: RunCreate) -> dict[str, Any]:
        project = self.get_project(project_id)
        sources = {item["source_type"]: item for item in project["sources"]}
        if any(sources.get(kind, {}).get("availability") != "available" for kind in ("fem", "h3d")):
            raise ValueError("SOURCE_MISSING_OR_CHANGED")
        for kind in ("fem", "h3d"):
            current = verify_source(Path(sources[kind]["absolute_path"]), kind)
            if current["availability"] != "available":
                self.db.execute("UPDATE result_sources SET availability=?,updated_at=? WHERE id=?", (current["availability"], now(), sources[kind]["id"]))
                raise ValueError("SOURCE_MISSING_OR_CHANGED")
            if current["fingerprint"] != sources[kind]["fingerprint"]:
                self.db.execute("UPDATE result_sources SET availability='changed',updated_at=? WHERE id=?", (now(), sources[kind]["id"]))
                raise ValueError("SOURCE_CHANGED")
        row = self.db.one("SELECT COALESCE(MAX(run_no),0)+1 AS next_no FROM analysis_runs WHERE project_id=?", (project_id,))
        run_no = int(row["next_no"]) if row else 1
        run_id = new_id("run")
        timestamp = now()
        selected = expand_tasks(request.task_types)
        snapshot = {
            kind: {"path": sources[kind]["absolute_path"], "fingerprint": sources[kind]["fingerprint"]}
            for kind in ("fem", "h3d")
        }
        self.db.execute(
            """INSERT INTO analysis_runs(id,project_id,run_no,name,status,configuration_json,input_snapshot_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                run_id,
                project_id,
                run_no,
                request.name or f"Run {run_no:03d}",
                "draft",
                json.dumps({**request.configuration, "task_types": selected}, ensure_ascii=False),
                json.dumps(snapshot, ensure_ascii=False),
                timestamp,
            ),
        )
        ids: dict[str, str] = {}
        for task_type in selected:
            task_id = new_id("task")
            ids[task_type] = task_id
            task_input = hashlib.sha256(
                json.dumps({"snapshot": snapshot, "task": task_type, "configuration": request.configuration}, sort_keys=True).encode()
            ).hexdigest()
            self.db.execute(
                """INSERT INTO run_tasks(id,run_id,task_type,status,configuration_json,input_hash,created_at)
                   VALUES(?,?,?,'pending',?,?,?)""",
                (task_id, run_id, task_type, json.dumps(request.configuration), task_input, timestamp),
            )
        for task_type, task_id in ids.items():
            dependencies = set(TASK_DEPENDENCIES.get(task_type, set()))
            if task_type == "report.prepare":
                dependencies.update(
                    selected_task
                    for selected_task in selected
                    if selected_task.startswith("result.")
                )
            for dependency in dependencies:
                if dependency in ids:
                    self.db.execute(
                        "INSERT INTO task_dependencies(task_id,depends_on_id) VALUES(?,?)",
                        (task_id, ids[dependency]),
                    )
        return self.get_run(run_id)

    def rerun_project(self, project_id: str) -> dict[str, Any]:
        runs = self.list_runs(project_id)
        if not runs:
            raise ValueError("RUN_NOT_FOUND")
        terminal = {"completed", "completed_with_errors", "failed", "cancelled"}
        if any(run["status"] not in terminal for run in runs):
            raise ValueError("RUN_ALREADY_ACTIVE")

        project = self.get_project(project_id)
        sources = {item["source_type"]: item for item in project["sources"]}
        checks: dict[str, dict[str, Any]] = {}
        changes: dict[str, dict[str, Any]] = {}
        for kind in ("fem", "h3d"):
            source = sources.get(kind)
            if source is None:
                raise ValueError("SOURCE_MISSING")
            check = verify_source(Path(source["absolute_path"]), kind)
            if check["availability"] != "available":
                raise ValueError("SOURCE_MISSING_OR_CHANGED")
            checks[kind] = check
            changes[kind] = {
                "path": source["absolute_path"],
                "previous_fingerprint": source["fingerprint"],
                "current_fingerprint": check["fingerprint"],
                "changed": source["fingerprint"] != check["fingerprint"],
            }

        timestamp = now()
        for kind, check in checks.items():
            source = sources[kind]
            self.db.execute(
                """UPDATE result_sources SET size_bytes=?,modified_time_ns=?,fingerprint_type=?,
                   fingerprint=?,availability='available',last_verified_at=?,updated_at=? WHERE id=?""",
                (
                    check["size_bytes"],
                    check["modified_time_ns"],
                    check["fingerprint_type"],
                    check["fingerprint"],
                    timestamp,
                    timestamp,
                    source["id"],
                ),
            )

        previous = runs[0]
        previous_configuration = dict(previous.get("configuration", {}))
        task_types = list(previous_configuration.pop("task_types", TASK_TYPES))
        next_no = int(previous["run_no"]) + 1
        request = RunCreate(
            name=f"重新分析 {next_no:03d}",
            task_types=task_types,
            configuration={
                **previous_configuration,
                "rerun_of": previous["id"],
                "source_changes": changes,
            },
        )
        run = self.create_run(project_id, request)
        return self.start_run(run["id"])

    def list_runs(self, project_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM analysis_runs WHERE project_id=? ORDER BY run_no DESC", (project_id,))
        return [decode_json_fields(row) or {} for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = decode_json_fields(self.db.one("SELECT * FROM analysis_runs WHERE id=?", (run_id,)))
        if row is None:
            raise KeyError(run_id)
        row["tasks"] = self.list_tasks(run_id)
        completed = sum(1 for task in row["tasks"] if task["status"] in {"completed", "completed_with_warnings", "skipped"})
        row["progress"] = round(100 * completed / len(row["tasks"])) if row["tasks"] else 0
        return row

    def start_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] not in {"draft", "paused", "interrupted", "failed"}:
            if run["status"] == "running":
                raise ValueError("RUN_ALREADY_RUNNING: 当前 Run 正在运行中，无需重复启动")
            elif run["status"] == "queued":
                raise ValueError("RUN_ALREADY_QUEUED: 当前 Run 已在排队等待中，无需重复启动")
            elif run["status"] == "completed":
                raise ValueError("RUN_ALREADY_COMPLETED: 当前 Run 已完成分析。如需重新运行，请点击『重新运行』按钮")
            else:
                raise ValueError(f"RUN_INVALID_STATUS: 当前 Run 状态为 {run['status']}，无法启动")
        sources = self.db.all(
            """SELECT s.* FROM result_sources s JOIN analysis_runs r ON r.project_id=s.project_id
               WHERE r.id=? AND s.source_type IN ('fem','h3d')""",
            (run_id,),
        )
        snapshot = run["input_snapshot"]
        for source in sources:
            current = verify_source(Path(source["absolute_path"]), source["source_type"])
            if current["availability"] != "available":
                raise ValueError("SOURCE_MISSING: 依赖的 FEM/H3D 源文件丢失或无法读取，无法启动分析")
            if current["fingerprint"] != snapshot[source["source_type"]]["fingerprint"]:
                raise ValueError("SOURCE_CHANGED: 原始 FEM/H3D 文件指纹发生变更，请创建新 Run 重新运行")
        self.db.execute(
            "UPDATE analysis_runs SET status='queued',started_at=COALESCE(started_at,?),pause_requested=0,cancel_requested=0 WHERE id=?",
            (now(), run_id),
        )
        self.db.execute("UPDATE run_tasks SET status='pending' WHERE run_id=? AND status IN ('failed','interrupted')", (run_id,))
        return self.get_run(run_id)

    def control_run(self, run_id: str, action: str) -> dict[str, Any]:
        mapping = {
            "pause": ("pause_requested=1,status='paused'", ()),
            "resume": ("pause_requested=0,status='queued'", ()),
            "cancel": ("cancel_requested=1,status='cancel_requested'", ()),
        }
        if action not in mapping:
            raise ValueError(action)
        clause, params = mapping[action]
        self.db.execute(f"UPDATE analysis_runs SET {clause} WHERE id=?", (*params, run_id))
        if action == "cancel":
            self.db.execute("UPDATE run_tasks SET status='cancelled',finished_at=? WHERE run_id=? AND status IN ('pending','blocked','queued')", (now(), run_id))
        return self.get_run(run_id)

    def retry_failed(self, run_id: str) -> dict[str, Any]:
        self.db.execute(
            """UPDATE run_tasks SET status='pending',error_code=NULL,error_message=NULL,finished_at=NULL
               WHERE run_id=? AND status IN ('failed','interrupted')""",
            (run_id,),
        )
        self.db.execute("UPDATE analysis_runs SET status='queued',finished_at=NULL,error_summary=NULL WHERE id=?", (run_id,))
        return self.get_run(run_id)

    def list_tasks(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM run_tasks WHERE run_id=? ORDER BY created_at", (run_id,))
        return [decode_json_fields(row) or {} for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = decode_json_fields(self.db.one("SELECT * FROM run_tasks WHERE id=?", (task_id,)))
        if row is None:
            raise KeyError(task_id)
        return row

    def claim_task(self, worker_id: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """SELECT t.* FROM run_tasks t JOIN analysis_runs r ON r.id=t.run_id
                   WHERE t.status='pending' AND r.status IN ('queued','running')
                   AND r.pause_requested=0 AND r.cancel_requested=0
                   AND NOT EXISTS(
                     SELECT 1 FROM task_dependencies d JOIN run_tasks dep ON dep.id=d.depends_on_id
                     WHERE d.task_id=t.id AND dep.status NOT IN ('completed','completed_with_warnings','skipped')
                   ) ORDER BY t.created_at LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            task = dict(row)
            updated = connection.execute(
                """UPDATE run_tasks SET status='running',started_at=COALESCE(started_at,?),heartbeat_at=?,
                   attempt_count=attempt_count+1 WHERE id=? AND status='pending'""",
                (now(), now(), task["id"]),
            )
            if updated.rowcount != 1:
                return None
            connection.execute("UPDATE analysis_runs SET status='running' WHERE id=?", (task["run_id"],))
        task = self.get_task(task["id"])
        run = self.get_run(task["run_id"])
        project = self.get_project(run["project_id"])
        task["run"] = run
        task["project"] = project
        task["worker_id"] = worker_id
        return task

    def task_progress(self, task_id: str, current: int, total: int, message: str) -> dict[str, Any]:
        self.db.execute(
            """UPDATE run_tasks SET progress_current=?,progress_total=?,progress_message=?,heartbeat_at=?
               WHERE id=? AND status='running'""",
            (current, total, message, now(), task_id),
        )
        self.db.execute(
            "INSERT INTO task_events(task_id,timestamp,event,message) VALUES(?,?,'task.progress',?)",
            (task_id, now(), message),
        )
        return self.get_task(task_id)

    def complete_task(self, task_id: str, status: str, result: dict[str, Any], error_code: str | None, error_message: str | None) -> dict[str, Any]:
        task = self.get_task(task_id)
        if status == "failed" and task["attempt_count"] < task["max_attempts"]:
            self.db.execute(
                """UPDATE run_tasks SET status='pending',progress_message='等待自动重试',finished_at=NULL,
                   error_code=?,error_message=? WHERE id=?""",
                (error_code, error_message, task_id),
            )
            self.db.execute(
                "INSERT INTO task_events(task_id,timestamp,event,message) VALUES(?,?,'task.retry','任务失败，等待自动重试')",
                (task_id, now()),
            )
            return self.get_task(task_id)
        if status in {"completed", "completed_with_warnings"}:
            self._persist_result(task, result)
        self.db.execute(
            """UPDATE run_tasks SET status=?,progress_current=CASE WHEN ? LIKE 'completed%' THEN progress_total ELSE progress_current END,
               output_manifest_json=?,finished_at=?,heartbeat_at=?,error_code=?,error_message=? WHERE id=?""",
            (status, status, json.dumps(result, ensure_ascii=False), now(), now(), error_code, error_message, task_id),
        )
        self._refresh_run(task["run_id"])
        return self.get_task(task_id)

    def _persist_result(self, task: dict[str, Any], result: dict[str, Any]) -> None:
        run_id = task["run_id"]
        task_type = task["task_type"]
        if task_type == "fem.model_summary":
            self.db.execute("INSERT OR REPLACE INTO model_summaries(run_id,data_json) VALUES(?,?)", (run_id, json.dumps(result)))
            self._replace_entities("components", run_id, result.get("components", []), "cmp")
        elif task_type == "fem.mesh_summary":
            self.db.execute("INSERT OR REPLACE INTO elements_summary(run_id,data_json) VALUES(?,?)", (run_id, json.dumps(result)))
        elif task_type == "fem.material_property":
            self._replace_entities("materials", run_id, result.get("materials", []), "mat")
            self._replace_entities("properties", run_id, result.get("properties", []), "prop")
        elif task_type == "fem.boundary_conditions":
            self._replace_entities("loads", run_id, result.get("loads", []), "load")
            self._replace_entities("constraints", run_id, result.get("constraints", []), "spc")
            self._replace_entities("connections", run_id, result.get("connections", []), "conn")
        elif task_type == "fem.subcases":
            self._replace_entities("subcases", run_id, result.get("subcases", []), "sub")
        elif task_type == "h3d.result_index":
            self._replace_entities("h3d_subcases", run_id, result.get("subcases", []), "h3dsub")
            self._replace_entities("h3d_simulations", run_id, result.get("simulations", []), "sim")
            self._replace_entities("h3d_result_types", run_id, result.get("result_types", []), "rtype")
        elif task_type in {"result.stress_hotspots", "result.displacement_hotspots"}:
            kind = "stress" if "stress" in task_type else "displacement"
            self.db.execute("DELETE FROM hotspots WHERE run_id=? AND result_kind=?", (run_id, kind))
            for item in result.get("hotspots", []):
                hotspot_id = str(item.get("id") or new_id("hotspot"))
                data = {**item, "id": hotspot_id, "result_kind": kind}
                self.db.execute(
                    """INSERT INTO hotspots(id,run_id,result_kind,subcase,rank,value,review_status,data_json)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (hotspot_id, run_id, kind, str(data.get("subcase", "")), int(data.get("rank", 0)), float(data.get("value", 0)), str(data.get("review_status", "unknown")), json.dumps(data)),
                )
                for capture in item.get("captures", []):
                    self._persist_capture(run_id, hotspot_id, capture)
        elif task_type == "capture.standard_views":
            for capture in result.get("captures", []):
                self._persist_capture(run_id, None, capture)
        elif task_type == "report.prepare" and result.get("document"):
            report_id = str(result["document"].get("id") or new_id("report"))
            document = {**result["document"], "id": report_id, "run_id": run_id}
            self.db.execute(
                """INSERT INTO report_documents(id,run_id,document_json,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET document_json=excluded.document_json,updated_at=excluded.updated_at""",
                (report_id, run_id, json.dumps(document, ensure_ascii=False), now()),
            )

    def _replace_entities(self, table: str, run_id: str, items: list[dict[str, Any]], prefix: str) -> None:
        allowed = {"components", "materials", "properties", "subcases", "loads", "constraints", "connections", "h3d_subcases", "h3d_simulations", "h3d_result_types"}
        if table not in allowed:
            raise ValueError(table)
        self.db.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
        used_ids: set[str] = set()
        for index, item in enumerate(items):
            entity_id = f"{run_id}:{prefix}:{item.get('id', index)}"
            if entity_id in used_ids:
                entity_id = f"{entity_id}:{index}"
            used_ids.add(entity_id)
            self.db.execute(f"INSERT INTO {table}(id,run_id,data_json) VALUES(?,?,?)", (entity_id, run_id, json.dumps(item, ensure_ascii=False)))

    def _persist_capture(self, run_id: str, hotspot_id: str | None, capture: dict[str, Any]) -> None:
        capture_id = str(capture.get("id") or new_id("cap"))
        existing = self.db.one("SELECT * FROM captures WHERE id=?", (capture_id,))
        version_row = self.db.one("SELECT COALESCE(MAX(version_no),0)+1 AS next_no FROM capture_versions WHERE capture_id=?", (capture_id,))
        version_no = int(version_row["next_no"]) if version_row else 1
        version_id = new_id("capv")
        view_state = capture.get("view_state") or {}
        if not view_state:
            raise ValueError("CAPTURE_INVALID: ViewState required")
        run_project = self.db.one(
            """SELECT p.workspace_path FROM projects p JOIN analysis_runs r ON r.project_id=p.id
               WHERE r.id=?""",
            (run_id,),
        )
        if run_project is None:
            raise KeyError(run_id)
        project_path = Path(run_project["workspace_path"]).resolve()
        image = Path(str(capture["image_path"])).resolve()
        thumbnail = Path(str(capture.get("thumbnail_path", image))).resolve()
        if project_path not in image.parents or project_path not in thumbnail.parents:
            raise ValueError("CAPTURE_INVALID: output path is outside project workspace")
        if not image.is_file() or not thumbnail.is_file():
            raise ValueError("CAPTURE_INVALID: image file missing")
        image_path = str(image)
        thumb_path = str(thumbnail)
        digest = str(capture.get("sha256") or file_fingerprint(image, fast=False)[1])
        if existing is None:
            self.db.execute(
                """INSERT INTO captures(id,hotspot_id,run_id,name,view_name,current_version_id,review_status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,'pending',?,?)""",
                (capture_id, hotspot_id, run_id, str(capture.get("name", "Capture")), str(capture.get("view_name", "isometric")), version_id, now(), now()),
            )
        else:
            self.db.execute("UPDATE capture_versions SET is_current=0 WHERE capture_id=?", (capture_id,))
            self.db.execute("UPDATE captures SET current_version_id=?,review_status='pending',updated_at=? WHERE id=?", (version_id, now(), capture_id))
        self.db.execute(
            """INSERT INTO capture_versions(id,capture_id,version_no,image_path,thumbnail_path,sha256,view_state_json,created_at,is_current)
               VALUES(?,?,?,?,?,?,?,?,1)""",
            (version_id, capture_id, version_no, image_path, thumb_path, digest, json.dumps(view_state), now()),
        )

    def _refresh_run(self, run_id: str) -> None:
        tasks = self.list_tasks(run_id)
        terminal = {"completed", "completed_with_warnings", "failed", "cancelled", "skipped"}
        if tasks and all(task["status"] in terminal for task in tasks):
            run = self.db.one("SELECT status,cancel_requested FROM analysis_runs WHERE id=?", (run_id,))
            if run and (run["cancel_requested"] or run["status"] == "cancel_requested"):
                status = "cancelled"
            elif any(task["status"] == "failed" for task in tasks):
                status = "completed_with_errors"
            elif all(task["status"] == "cancelled" for task in tasks):
                status = "cancelled"
            else:
                status = "completed"
            self.db.execute("UPDATE analysis_runs SET status=?,finished_at=? WHERE id=?", (status, now(), run_id))

    def model_data(self, run_id: str, kind: str) -> Any:
        scalar_tables = {"model-summary": "model_summaries", "mesh-summary": "elements_summary"}
        list_tables = {
            "components": "components",
            "materials": "materials",
            "properties": "properties",
            "boundary-conditions": None,
            "subcases": "subcases",
            "result-index": None,
            "hotspots": "hotspots",
        }
        if kind in scalar_tables:
            row = self.db.one(f"SELECT data_json FROM {scalar_tables[kind]} WHERE run_id=?", (run_id,))
            return json.loads(row["data_json"]) if row else {}
        if kind == "boundary-conditions":
            return {
                name: [json.loads(row["data_json"]) for row in self.db.all(f"SELECT data_json FROM {table} WHERE run_id=?", (run_id,))]
                for name, table in {"loads": "loads", "constraints": "constraints", "connections": "connections"}.items()
            }
        if kind == "result-index":
            return {
                name: [json.loads(row["data_json"]) for row in self.db.all(f"SELECT data_json FROM {table} WHERE run_id=?", (run_id,))]
                for name, table in {"subcases": "h3d_subcases", "simulations": "h3d_simulations", "result_types": "h3d_result_types"}.items()
            }
        table = list_tables.get(kind)
        if table is None:
            raise KeyError(kind)
        rows = self.db.all(f"SELECT * FROM {table} WHERE run_id=? ORDER BY id", (run_id,))
        if kind == "hotspots":
            return [{**json.loads(row["data_json"]), "review_status": row["review_status"]} for row in rows]
        return [json.loads(row["data_json"]) for row in rows]

    def get_hotspot(self, hotspot_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM hotspots WHERE id=?", (hotspot_id,))
        if row is None:
            raise KeyError(hotspot_id)
        result = {**json.loads(row["data_json"]), "review_status": row["review_status"]}
        result["captures"] = self.captures_for_hotspot(hotspot_id)
        return result

    def captures_for_hotspot(self, hotspot_id: str) -> list[dict[str, Any]]:
        return [self.get_capture(row["id"]) for row in self.db.all("SELECT id FROM captures WHERE hotspot_id=? ORDER BY created_at", (hotspot_id,))]

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM captures WHERE id=?", (capture_id,))
        if row is None:
            raise KeyError(capture_id)
        versions = self.db.all("SELECT * FROM capture_versions WHERE capture_id=? ORDER BY version_no DESC", (capture_id,))
        for version in versions:
            version["view_state"] = json.loads(version.pop("view_state_json"))
        row["versions"] = versions
        return row

    def review_capture(self, capture_id: str, action: str, note: str) -> dict[str, Any]:
        status = {"approve": "approved", "reject": "rejected", "recapture": "recapture_requested"}[action]
        self.db.execute("UPDATE captures SET review_status=?,updated_at=? WHERE id=?", (status, now(), capture_id))
        self.db.execute(
            "INSERT INTO review_actions(id,capture_id,action,note,created_at) VALUES(?,?,?,?,?)",
            (new_id("review"), capture_id, action, note, now()),
        )
        return self.get_capture(capture_id)

    def queue_capture_action(
        self,
        capture_id: str,
        kind: str,
        *,
        bring_to_front: bool = False,
        restore_request_id: str | None = None,
    ) -> dict[str, Any]:
        capture = self.get_capture(capture_id)
        action_id = new_id("action")
        payload: dict[str, Any] = {"bring_to_front": bring_to_front}
        if restore_request_id is not None:
            payload["restore_request_id"] = restore_request_id
        self.db.execute(
            """INSERT INTO action_jobs(id,kind,capture_id,run_id,status,payload_json,created_at)
               VALUES(?,?,?,?, 'queued',?,?)""",
            (action_id, kind, capture_id, capture["run_id"], json.dumps(payload), now()),
        )
        return {"id": action_id, "kind": kind, "capture_id": capture_id, "status": "queued", **payload}

    def restore_capture(self, capture_id: str, bring_to_front: bool) -> dict[str, Any]:
        self.get_capture(capture_id)
        request_id = new_id("restore")
        self.db.execute(
            """INSERT INTO view_restore_requests(id,capture_id,status,bring_to_front,missing_json,created_at)
               VALUES(?,?,'queued',?,'[]',?)""",
            (request_id, capture_id, int(bring_to_front), now()),
        )
        job = self.queue_capture_action(
            capture_id,
            "view.restore",
            bring_to_front=bring_to_front,
            restore_request_id=request_id,
        )
        job["restore_request_id"] = request_id
        return job

    def get_restore_request(self, restore_request_id: str) -> dict[str, Any]:
        request = self.db.one(
            "SELECT * FROM view_restore_requests WHERE id=?",
            (restore_request_id,),
        )
        if request is None:
            raise KeyError(restore_request_id)
        request["bring_to_front"] = bool(request["bring_to_front"])
        request["missing"] = json.loads(request.pop("missing_json"))
        return request

    def claim_action(self, worker_id: str) -> dict[str, Any] | None:
        del worker_id
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM action_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                return None
            job = dict(row)
            updated = connection.execute(
                "UPDATE action_jobs SET status='running',started_at=? WHERE id=? AND status='queued'",
                (now(), job["id"]),
            )
            if updated.rowcount != 1:
                return None
        job["payload"] = json.loads(job.pop("payload_json"))
        job.pop("result_json", None)
        capture = self.get_capture(job["capture_id"])
        current = next((version for version in capture["versions"] if version["is_current"]), capture["versions"][0])
        run = self.get_run(job["run_id"])
        project = self.get_project(run["project_id"])
        job["capture"] = capture
        job["view_state"] = current["view_state"]
        job["run"] = run
        job["project"] = project
        return job

    def complete_action(
        self,
        action_id: str,
        status: str,
        result: dict[str, Any],
        error_code: str | None,
        error_message: str | None,
    ) -> dict[str, Any]:
        job = self.db.one("SELECT * FROM action_jobs WHERE id=?", (action_id,))
        if job is None:
            raise KeyError(action_id)
        if status == "completed" and job["kind"] == "capture.recapture":
            self._persist_capture(job["run_id"], None, result["capture"])
        if job["kind"] == "view.restore":
            restore_status = result.get("restore", "failed") if status == "completed" else "failed"
            payload = json.loads(job["payload_json"])
            self.db.execute(
                """UPDATE view_restore_requests SET status=?,missing_json=?,finished_at=?
                   WHERE id=?""",
                (
                    restore_status,
                    json.dumps(result.get("missing", [])),
                    now(),
                    payload.get("restore_request_id"),
                ),
            )
        self.db.execute(
            """UPDATE action_jobs SET status=?,result_json=?,error_code=?,error_message=?,finished_at=? WHERE id=?""",
            (status, json.dumps(result), error_code, error_message, now(), action_id),
        )
        updated = self.db.one("SELECT * FROM action_jobs WHERE id=?", (action_id,))
        assert updated is not None
        updated["result"] = json.loads(updated.pop("result_json"))
        updated["payload"] = json.loads(updated.pop("payload_json"))
        return updated

    def get_report(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM report_documents WHERE run_id=?", (run_id,))
        if row is None:
            raise KeyError(run_id)
        document = json.loads(row["document_json"])
        if not isinstance(document, dict):
            raise ValueError("REPORT_DOCUMENT_INVALID")
        return document

    def save_report(self, run_id: str, document: dict[str, Any]) -> dict[str, Any]:
        run_project = self.db.one(
            """SELECT p.workspace_path FROM projects p JOIN analysis_runs r ON r.project_id=p.id
               WHERE r.id=?""",
            (run_id,),
        )
        if run_project is None:
            raise KeyError(run_id)
        project_path = Path(run_project["workspace_path"]).resolve()
        for slide in document.get("slides", []):
            for element in slide.get("elements", []):
                if element.get("type") == "image" and element.get("src"):
                    image = Path(str(element["src"])).resolve()
                    if project_path not in image.parents or not image.is_file():
                        raise ValueError("REPORT_DOCUMENT_INVALID: image is outside project workspace")
        row = self.db.one("SELECT id FROM report_documents WHERE run_id=?", (run_id,))
        report_id = str(document.get("id") or (row["id"] if row else new_id("report")))
        normalized = {**document, "id": report_id, "run_id": run_id}
        self.db.execute(
            """INSERT INTO report_documents(id,run_id,document_json,updated_at) VALUES(?,?,?,?)
               ON CONFLICT(run_id) DO UPDATE SET document_json=excluded.document_json,updated_at=excluded.updated_at""",
            (report_id, run_id, json.dumps(normalized, ensure_ascii=False), now()),
        )
        return normalized
