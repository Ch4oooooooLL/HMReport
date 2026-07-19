from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL DEFAULT '', product TEXT NOT NULL DEFAULT '',
 analysis_type TEXT NOT NULL DEFAULT '', solver TEXT NOT NULL DEFAULT '', unit_system TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', workspace_path TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_opened_at TEXT
);
CREATE TABLE IF NOT EXISTS result_sources(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 source_type TEXT NOT NULL, absolute_path TEXT NOT NULL, filename TEXT NOT NULL, extension TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, modified_time_ns INTEGER NOT NULL, fingerprint_type TEXT NOT NULL,
 fingerprint TEXT NOT NULL, availability TEXT NOT NULL, last_verified_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(project_id, source_type)
);
CREATE TABLE IF NOT EXISTS analysis_runs(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 run_no INTEGER NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, configuration_json TEXT NOT NULL,
 input_snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
 error_summary TEXT, pause_requested INTEGER NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0,
 UNIQUE(project_id, run_no)
);
CREATE TABLE IF NOT EXISTS run_tasks(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
 task_type TEXT NOT NULL, parent_task_id TEXT, status TEXT NOT NULL, progress_current INTEGER NOT NULL DEFAULT 0,
 progress_total INTEGER NOT NULL DEFAULT 100, progress_message TEXT NOT NULL DEFAULT '',
 configuration_json TEXT NOT NULL DEFAULT '{}', input_hash TEXT NOT NULL DEFAULT '',
 output_manifest_json TEXT NOT NULL DEFAULT '{}', attempt_count INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 2, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
 heartbeat_at TEXT, error_code TEXT, error_message TEXT, UNIQUE(run_id, task_type)
);
CREATE TABLE IF NOT EXISTS task_dependencies(
 task_id TEXT NOT NULL REFERENCES run_tasks(id) ON DELETE CASCADE,
 depends_on_id TEXT NOT NULL REFERENCES run_tasks(id) ON DELETE CASCADE,
 PRIMARY KEY(task_id, depends_on_id)
);
CREATE TABLE IF NOT EXISTS task_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES run_tasks(id) ON DELETE CASCADE,
 timestamp TEXT NOT NULL, event TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS workers(
 id TEXT PRIMARY KEY, pid INTEGER NOT NULL, hostname TEXT NOT NULL, status TEXT NOT NULL,
 capabilities_json TEXT NOT NULL, registered_at TEXT NOT NULL, heartbeat_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_summaries(run_id TEXT PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS elements_summary(run_id TEXT PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS components(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS materials(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS properties(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS component_property_links(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subcases(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS loads(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS constraints(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS h3d_subcases(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS h3d_simulations(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS h3d_result_types(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hotspots(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
 result_kind TEXT NOT NULL, subcase TEXT NOT NULL, rank INTEGER NOT NULL, value REAL NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'unknown', data_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS captures(
 id TEXT PRIMARY KEY, hotspot_id TEXT REFERENCES hotspots(id) ON DELETE CASCADE, run_id TEXT NOT NULL,
 name TEXT NOT NULL, view_name TEXT NOT NULL, current_version_id TEXT, review_status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS capture_versions(
 id TEXT PRIMARY KEY, capture_id TEXT NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
 version_no INTEGER NOT NULL, image_path TEXT NOT NULL, thumbnail_path TEXT NOT NULL, sha256 TEXT NOT NULL,
 view_state_json TEXT NOT NULL, created_at TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1,
 UNIQUE(capture_id, version_no)
);
CREATE TABLE IF NOT EXISTS review_actions(id TEXT PRIMARY KEY, capture_id TEXT NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS view_restore_requests(id TEXT PRIMARY KEY, capture_id TEXT NOT NULL, status TEXT NOT NULL, bring_to_front INTEGER NOT NULL, missing_json TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS action_jobs(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, capture_id TEXT NOT NULL, run_id TEXT NOT NULL,
 status TEXT NOT NULL, payload_json TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}',
 error_code TEXT, error_message TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS report_documents(id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, document_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_slides(id TEXT PRIMARY KEY, report_id TEXT NOT NULL, position INTEGER NOT NULL, data_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_exports(id TEXT PRIMARY KEY, report_id TEXT NOT NULL, status TEXT NOT NULL, path TEXT, error_message TEXT, created_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS application_events(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, event TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_runs_project ON analysis_runs(project_id, run_no DESC);
CREATE INDEX IF NOT EXISTS ix_tasks_run ON run_tasks(run_id, status);
CREATE INDEX IF NOT EXISTS ix_hotspots_run ON hotspots(run_id, result_kind, rank);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (SCHEMA_VERSION,),
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.connect() as connection:
            connection.execute(sql, params)

    def one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def integrity(self) -> str:
        row = self.one("PRAGMA integrity_check")
        return str(next(iter(row.values()))) if row else "unknown"


def decode_json_fields(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    for key, value in list(row.items()):
        if key.endswith("_json") and isinstance(value, str):
            row[key[:-5]] = json.loads(value)
            del row[key]
    return row
