from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TASK_TYPES = (
    "fem.model_summary",
    "fem.mesh_summary",
    "fem.material_property",
    "fem.boundary_conditions",
    "fem.subcases",
    "h3d.result_index",
    "result.stress_hotspots",
    "result.displacement_hotspots",
    "capture.standard_views",
    "report.prepare",
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    workspace_path: str
    code: str = ""
    product: str = ""
    analysis_type: str = "linear_static"
    solver: str = "optistruct"
    unit_system: str = "mm-N-MPa"
    description: str = ""
    fem_path: str
    h3d_path: str
    task_types: list[str] = Field(default_factory=lambda: list(TASK_TYPES))

    @field_validator("task_types")
    @classmethod
    def validate_tasks(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(TASK_TYPES)
        if unknown:
            raise ValueError(f"unknown task types: {sorted(unknown)}")
        return list(dict.fromkeys(value))


class ProjectPatch(BaseModel):
    name: str | None = None
    code: str | None = None
    product: str | None = None
    analysis_type: str | None = None
    solver: str | None = None
    unit_system: str | None = None
    description: str | None = None


class SourceCreate(BaseModel):
    source_type: Literal["fem", "h3d", "out", "op2", "xlsx", "other"]
    absolute_path: str

    @field_validator("absolute_path")
    @classmethod
    def absolute_only(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("source path must be absolute")
        return str(path.resolve())


class RunCreate(BaseModel):
    name: str = ""
    task_types: list[str] = Field(default_factory=lambda: list(TASK_TYPES))
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_types")
    @classmethod
    def validate_tasks(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(TASK_TYPES)
        if unknown:
            raise ValueError(f"unknown task types: {sorted(unknown)}")
        return list(dict.fromkeys(value))


class WorkerRegister(BaseModel):
    worker_id: str
    pid: int
    hostname: str
    capabilities: list[str]


class WorkerHeartbeat(BaseModel):
    worker_id: str
    status: str = "ready"


class TaskProgress(BaseModel):
    worker_id: str
    progress_current: int = Field(ge=0)
    progress_total: int = Field(gt=0)
    message: str = ""


class TaskComplete(BaseModel):
    worker_id: str
    status: Literal["completed", "completed_with_warnings", "failed", "cancelled"]
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


class ReviewRequest(BaseModel):
    note: str = ""


class RestoreRequest(BaseModel):
    bring_to_front: bool = False


class ReportUpdate(BaseModel):
    document: dict[str, Any]

