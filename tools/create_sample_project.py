from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

SAMPLE_FEM = """$HMNAME COMP 10 "FRAME_LEFT"
SOL 101
CEND
SUBCASE 1
  LABEL = FULL_LOAD
  SPC = 100
  LOAD = 200
BEGIN BULK
GRID,1,,0.,0.,0.
GRID,2,,100.,0.,0.
GRID,3,,100.,80.,0.
GRID,4,,0.,80.,0.
CQUAD4,1001,10,1,2,3,4
PSHELL,10,20,1.2
MAT1,20,210000.,,0.3,7.85E-9
SPC1,100,123456,1
FORCE,200,2,0,1250.,1.,0.,0.
RBE2,300,1,123456,2,3
ENDDATA
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic Fake HyperView sample inputs/project")
    parser.add_argument("--output", type=Path, default=Path("examples/generated_inputs"))
    parser.add_argument("--workspace", type=Path, default=Path("workspace/projects"))
    parser.add_argument("--server", help="Optional running server URL; creates the project and starts its draft run")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fem = output / "sample_vehicle.fem"
    h3d = output / "sample_vehicle.h3d"
    fem.write_text(SAMPLE_FEM, encoding="utf-8")
    h3d.write_bytes(b"FAKE-H3D-PROTOCOL-FIXTURE-V1")
    payload = {
        "name": "示例车身结构强度",
        "code": "SAMPLE-BIW-001",
        "workspace_path": str(args.workspace.resolve()),
        "solver": "optistruct",
        "unit_system": "mm-N-MPa",
        "fem_path": str(fem),
        "h3d_path": str(h3d),
        "task_types": [
            "fem.model_summary", "fem.mesh_summary", "fem.material_property",
            "fem.boundary_conditions", "fem.subcases", "h3d.result_index",
            "result.stress_hotspots", "result.displacement_hotspots",
            "capture.standard_views", "report.prepare",
        ],
    }
    manifest = output / "sample_project.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.server:
        with httpx.Client(base_url=args.server.rstrip("/"), timeout=30) as client:
            response = client.post("/api/v1/projects", json=payload)
            response.raise_for_status()
            project = response.json()
            client.post(f"/api/v1/runs/{project['draft_run_id']}/start").raise_for_status()
            print(json.dumps(project, ensure_ascii=False, indent=2))
    else:
        print(f"Created {fem}")
        print(f"Created Fake-only {h3d}")
        print(f"Manifest {manifest}")


if __name__ == "__main__":
    main()
