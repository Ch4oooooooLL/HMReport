from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from create_sample_project import SAMPLE_FEM

ROOT = Path(__file__).resolve().parents[1]


def wait_ready(client: httpx.Client, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.get("/health").json()["status"] == "ready":
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise TimeoutError("Server did not become ready")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Server/Worker process-level E2E")
    parser.add_argument("--server-exe", type=Path)
    parser.add_argument("--worker-exe", type=Path)
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    run_root = ROOT / "runtime" / f"process-e2e-{datetime.now():%Y%m%d-%H%M%S}"
    inputs = run_root / "inputs"
    workspace = run_root / "workspace"
    inputs.mkdir(parents=True)
    fem = inputs / "sample.fem"
    h3d = inputs / "sample.h3d"
    fem.write_text(SAMPLE_FEM, encoding="utf-8")
    h3d.write_bytes(b"FAKE-H3D-PROCESS-E2E")
    server_out = (run_root / "server.log").open("w", encoding="utf-8")
    server_err = (run_root / "server.err.log").open("w", encoding="utf-8")
    worker_out = (run_root / "worker.log").open("w", encoding="utf-8")
    worker_err = (run_root / "worker.err.log").open("w", encoding="utf-8")
    server_command = (
        [str(args.server_exe.resolve()), "--workspace", str(workspace), "--port", str(args.port)]
        if args.server_exe
        else [sys.executable, "-m", "cae_report_server.main", "--workspace", str(workspace), "--port", str(args.port)]
    )
    base_url = f"http://127.0.0.1:{args.port}"
    server = subprocess.Popen(
        server_command,
        cwd=ROOT,
        stdout=server_out,
        stderr=server_err,
    )
    worker: subprocess.Popen[bytes] | None = None
    try:
        with httpx.Client(base_url=base_url, timeout=30) as client:
            wait_ready(client)
            worker_command = (
                [str(args.worker_exe.resolve()), "--server", base_url, "--fake-hyperview"]
                if args.worker_exe
                else [
                    sys.executable,
                    "-m",
                    "cae_report_worker.main",
                    "--server",
                    base_url,
                    "--fake-hyperview",
                ]
            )
            worker = subprocess.Popen(
                worker_command,
                cwd=ROOT,
                stdout=worker_out,
                stderr=worker_err,
            )
            payload = {
                "name": "进程级 E2E",
                "code": "PROCESS-E2E",
                "workspace_path": str(workspace / "projects"),
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
            project = client.post("/api/v1/projects", json=payload).raise_for_status().json()
            client.post(f"/api/v1/runs/{project['draft_run_id']}/start").raise_for_status()
            deadline = time.monotonic() + 90
            run: dict[str, object] = {}
            while time.monotonic() < deadline:
                run = client.get(f"/api/v1/runs/{project['draft_run_id']}").raise_for_status().json()
                if run["status"] in {"completed", "completed_with_errors", "failed"}:
                    break
                time.sleep(0.2)
            if run.get("status") != "completed":
                raise RuntimeError(f"Run ended as {run.get('status')}")
            hotspots = client.get(f"/api/v1/runs/{run['id']}/hotspots").raise_for_status().json()
            web = client.get(f"/projects/{project['id']}").raise_for_status()
            diagnostics = client.post("/api/v1/diagnostics/export", json={}).raise_for_status().json()
            result = {
                "status": run["status"],
                "progress": run["progress"],
                "task_count": len(run["tasks"]),
                "hotspot_count": len(hotspots),
                "web_status": web.status_code,
                "diagnostics": diagnostics["id"],
                "workspace": str(workspace),
            }
            (run_root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        for process in (worker, server):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        for stream in (server_out, server_err, worker_out, worker_err):
            stream.close()


if __name__ == "__main__":
    main()
