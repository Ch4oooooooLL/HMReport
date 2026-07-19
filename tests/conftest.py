from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cae_report_server.app import create_app
from cae_report_server.settings import Settings

SAMPLE_FEM = """$HMNAME COMP 10 \"FRAME_LEFT\"
SOL 101
CEND
SUBCASE 1
  LABEL = FULL_LOAD
  SPC = 100
  LOAD = 200
BEGIN BULK
GRID,1,,0.,0.,0.
GRID,2,,10.,0.,0.
GRID,3,,10.,10.,0.
GRID,4,,0.,10.,0.
CQUAD4,1001,10,1,2,3,4
PSHELL,10,20,1.2
MAT1,20,210000.,,0.3,7.85E-9
SPC1,100,123456,1
FORCE,200,2,0,1250.,1.,0.,0.
RBE2,300,1,123456,2,3
ENDDATA
"""


@pytest.fixture
def source_files(tmp_path: Path) -> tuple[Path, Path]:
    external = tmp_path / "external"
    external.mkdir()
    fem = external / "model.fem"
    h3d = external / "result.h3d"
    fem.write_text(SAMPLE_FEM, encoding="utf-8")
    h3d.write_bytes(b"FAKE-H3D-FOR-CONTRACT-TEST")
    return fem, h3d


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(tmp_path / "workspace"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def project_payload(tmp_path: Path, source_files: tuple[Path, Path]) -> dict[str, object]:
    fem, h3d = source_files
    return {
        "name": "车身结构强度",
        "code": "BIW-001",
        "workspace_path": str(tmp_path / "projects"),
        "solver": "optistruct",
        "unit_system": "mm-N-MPa",
        "fem_path": str(fem),
        "h3d_path": str(h3d),
        "task_types": [
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
        ],
    }

