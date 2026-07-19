from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

FEM_PATH = ROOT / "examples" / "optistruct_feature_model" / "optistruct_feature_model.fem"
H3D_PATH = ROOT / "examples" / "optistruct_feature_model" / "optistruct_feature_model.h3d"


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wait_ready(client: httpx.Client, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.get("/health").json()["status"] == "ready":
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise TimeoutError("Server did not become ready")


def wait_action(database: Path, action_id: str, timeout: float = 30.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        connection = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT status,result_json,error_code,error_message FROM action_jobs WHERE id=?",
                (action_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is not None and row[0] in {"completed", "failed"}:
            return {
                "status": row[0],
                "result": json.loads(row[1]),
                "error_code": row[2],
                "error_message": row[3],
            }
        time.sleep(0.2)
    raise TimeoutError(f"Action did not complete: {action_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the real FEM/H3D workflow")
    parser.add_argument("--server-exe", type=Path)
    parser.add_argument("--worker-exe", type=Path)
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    source_before = {
        "fem": {
            "sha256": sha256(FEM_PATH),
            "size": FEM_PATH.stat().st_size,
            "mtime_ns": FEM_PATH.stat().st_mtime_ns,
        },
        "h3d": {
            "sha256": sha256(H3D_PATH),
            "size": H3D_PATH.stat().st_size,
            "mtime_ns": H3D_PATH.stat().st_mtime_ns,
        },
    }
    run_root = ROOT / "runtime" / f"verify-real-{datetime.now():%Y%m%d-%H%M%S}"
    run_root.mkdir(parents=True, exist_ok=True)
    workspace = run_root / "workspace"
    server_log = (run_root / "server.log").open("w", encoding="utf-8")
    server_err = (run_root / "server.err.log").open("w", encoding="utf-8")
    worker_log = (run_root / "worker.log").open("w", encoding="utf-8")
    worker_err = (run_root / "worker.err.log").open("w", encoding="utf-8")

    port = 8877
    base_url = f"http://127.0.0.1:{port}"

    server_cmd = (
        [
            str(args.server_exe.resolve()),
            "--workspace",
            str(workspace),
            "--port",
            str(port),
        ]
        if args.server_exe
        else [
            sys.executable,
            "-m",
            "cae_report_server.main",
            "--workspace",
            str(workspace),
            "--port",
            str(port),
        ]
    )
    print(f"[1/5] Starting Server: {' '.join(server_cmd)}")
    server = subprocess.Popen(server_cmd, cwd=ROOT, stdout=server_log, stderr=server_err)

    worker: subprocess.Popen[bytes] | None = None
    try:
        with httpx.Client(base_url=base_url, timeout=60) as client:
            wait_ready(client, timeout=30)
            print(f"[2/5] Server ready at {base_url}")

            worker_cmd = (
                [
                    str(args.worker_exe.resolve()),
                    "--server",
                    base_url,
                    "--real-hyperview",
                ]
                if args.worker_exe
                else [
                    sys.executable,
                    "-m",
                    "cae_report_worker.main",
                    "--server",
                    base_url,
                    "--real-hyperview",
                ]
            )
            print(f"[2/5] Starting Worker with --real-hyperview: {' '.join(worker_cmd)}")
            worker = subprocess.Popen(worker_cmd, cwd=ROOT, stdout=worker_log, stderr=worker_err)

            time.sleep(2)

            payload = {
                "name": "真实模型验证",
                "code": "VERIFY-REAL",
                "workspace_path": str(workspace / "projects"),
                "solver": "optistruct",
                "unit_system": "mm-N-MPa",
                "fem_path": str(FEM_PATH.resolve()),
                "h3d_path": str(H3D_PATH.resolve()),
                "task_types": [
                    "fem.model_summary", "fem.mesh_summary", "fem.material_property",
                    "fem.boundary_conditions", "fem.subcases", "h3d.result_index",
                    "result.stress_hotspots", "result.displacement_hotspots",
                    "capture.standard_views", "report.prepare",
                ],
            }
            print(f"[3/5] Creating project with FEM: {FEM_PATH}")
            print(f"       H3D: {H3D_PATH}")
            try:
                project = client.post("/api/v1/projects", json=payload).raise_for_status().json()
            except httpx.HTTPStatusError as exc:
                print(f"ERROR creating project: {exc.response.status_code} {exc.response.text}")
                raise

            print(f"       Project ID: {project['id']}")
            print(f"       Draft Run ID: {project['draft_run_id']}")

            print("[4/5] Starting run...")
            client.post(f"/api/v1/runs/{project['draft_run_id']}/start").raise_for_status()

            print("[5/5] Waiting for run to complete (timeout: 300s)...")
            deadline = time.monotonic() + 300
            run_status = ""
            last_progress = ""
            while time.monotonic() < deadline:
                run = client.get(f"/api/v1/runs/{project['draft_run_id']}").raise_for_status().json()
                status = run.get("status", "unknown")
                progress = run.get("progress", 0)
                progress_str = f"status={status} progress={progress}"
                if progress_str != last_progress:
                    print(f"       {progress_str}")
                    last_progress = progress_str
                if status in {"completed", "completed_with_errors", "failed", "cancelled"}:
                    run_status = status
                    break
                time.sleep(0.5)

            if run_status != "completed":
                print(f"WARNING: Run ended as '{run_status}'")
            else:
                print("SUCCESS: Run completed!")

            print("\n--- RESULTS ---")
            run_detail = client.get(f"/api/v1/runs/{project['draft_run_id']}").json()
            print(f"Run status: {run_detail['status']}")
            print(f"Run progress: {run_detail['progress']}")

            tasks = client.get(f"/api/v1/runs/{project['draft_run_id']}/tasks").json()
            print(f"\nTask summary ({len(tasks)} tasks):")
            for t in tasks:
                icon = "OK" if t["status"] == "completed" else "FAIL" if t["status"] == "failed" else "..."
                print(f"  [{icon}] {t['task_type']}: {t['status']}")
                if t.get("error_message"):
                    print(f"         error: {t['error_message']}")

            try:
                hotspots = client.get(f"/api/v1/runs/{project['draft_run_id']}/hotspots").json()
                print(f"\nHotspots: {len(hotspots)} found")
            except Exception:
                hotspots = []
                print("\nHotspots: not available")

            try:
                report = client.get(f"/api/v1/runs/{project['draft_run_id']}/report").json()
                print(f"Report: {len(report.get('slides', []))} slides")
            except Exception:
                report = {}
                print("Report: not available")

            result_index = client.get(
                f"/api/v1/runs/{project['draft_run_id']}/result-index"
            ).raise_for_status().json()
            web = client.get(f"/projects/{project['id']}").raise_for_status()

            capture_count = 0
            capture_dimensions: dict[str, int] = {}
            capture_hashes: set[str] = set()
            capture_file_hashes: dict[Path, str] = {}
            project_path = Path(project["workspace_path"])
            for image_path in project_path.glob(
                f"captures/{project['draft_run_id']}/*.png"
            ):
                with Image.open(image_path) as image:
                    size = f"{image.width}x{image.height}"
                    capture_dimensions[size] = capture_dimensions.get(size, 0) + 1
                    if image.format != "PNG":
                        raise RuntimeError(f"Capture is not PNG: {image_path}")
                capture_count += 1
                image_digest = sha256(image_path)
                capture_hashes.add(image_digest)
                capture_file_hashes[image_path] = image_digest

            capture_review: dict[str, object] = {}
            if hotspots:
                hotspot = client.get(
                    f"/api/v1/hotspots/{hotspots[0]['id']}"
                ).raise_for_status().json()
                capture = hotspot["captures"][0]
                version = next(
                    item for item in capture["versions"] if item["is_current"]
                )
                image_response = client.get(
                    f"/api/v1/capture-versions/{version['id']}/image"
                ).raise_for_status()
                if image_response.content[:8] != b"\x89PNG\r\n\x1a\n":
                    raise RuntimeError("Capture image endpoint did not return PNG")
                approved = client.post(
                    f"/api/v1/captures/{capture['id']}/approve",
                    json={"note": "真实业务流程自动验证"},
                ).raise_for_status().json()
                client.post(
                    f"/api/v1/captures/{capture['id']}/recapture",
                    json={"note": "验证真实 HyperView 重拍"},
                ).raise_for_status()
                deadline = time.monotonic() + 30
                versioned: dict[str, object] = {}
                while time.monotonic() < deadline:
                    versioned = client.get(
                        f"/api/v1/captures/{capture['id']}"
                    ).raise_for_status().json()
                    if len(versioned["versions"]) >= 2:
                        break
                    time.sleep(0.2)
                if len(versioned.get("versions", [])) < 2:
                    raise TimeoutError("Real HyperView recapture did not complete")
                restore = client.post(
                    f"/api/v1/captures/{capture['id']}/restore-view",
                    json={"bring_to_front": False},
                ).raise_for_status().json()
                restore_completion = wait_action(
                    run_root / "workspace" / "app" / "app.sqlite",
                    restore["id"],
                )
                if restore_completion["status"] != "completed":
                    raise RuntimeError(f"Real HyperView view restore failed: {restore_completion}")
                capture_review = {
                    "capture_id": capture["id"],
                    "approved_status": approved["review_status"],
                    "version_count_after_recapture": len(versioned["versions"]),
                    "restore_queue_status": restore["status"],
                    "restore_completion": restore_completion,
                }

            export = client.post(
                f"/api/v1/runs/{project['draft_run_id']}/report/export-pptx"
            ).raise_for_status().json()
            download = client.get(export["download_url"]).raise_for_status()
            if download.content[:2] != b"PK":
                raise RuntimeError("PPTX download is not a ZIP/OOXML file")
            diagnostics = client.post(
                "/api/v1/diagnostics/export", json={}
            ).raise_for_status().json()

            rerun_result: dict[str, object] = {}
            if args.rerun:
                rerun = client.post(
                    f"/api/v1/projects/{project['id']}/rerun"
                ).raise_for_status().json()
                deadline = time.monotonic() + 300
                while time.monotonic() < deadline:
                    rerun = client.get(
                        f"/api/v1/runs/{rerun['id']}"
                    ).raise_for_status().json()
                    if rerun["status"] in {
                        "completed",
                        "completed_with_errors",
                        "failed",
                        "cancelled",
                    }:
                        break
                    time.sleep(0.5)
                if rerun["status"] != "completed":
                    raise RuntimeError(f"Real HyperView rerun failed: {rerun['status']}")
                archived_files_unchanged = all(
                    path.is_file() and sha256(path) == digest
                    for path, digest in capture_file_hashes.items()
                )
                runs = client.get(
                    f"/api/v1/projects/{project['id']}/runs"
                ).raise_for_status().json()
                rerun_hotspots = client.get(
                    f"/api/v1/runs/{rerun['id']}/hotspots"
                ).raise_for_status().json()
                rerun_result = {
                    "run_id": rerun["id"],
                    "run_no": rerun["run_no"],
                    "status": rerun["status"],
                    "run_count": len(runs),
                    "previous_run_id": project["draft_run_id"],
                    "previous_run_preserved": any(
                        item["id"] == project["draft_run_id"] for item in runs
                    ),
                    "previous_capture_files_unchanged": archived_files_unchanged,
                    "hotspot_count": len(rerun_hotspots),
                }

            source_after = {
                "fem": {
                    "sha256": sha256(FEM_PATH),
                    "size": FEM_PATH.stat().st_size,
                    "mtime_ns": FEM_PATH.stat().st_mtime_ns,
                },
                "h3d": {
                    "sha256": sha256(H3D_PATH),
                    "size": H3D_PATH.stat().st_size,
                    "mtime_ns": H3D_PATH.stat().st_mtime_ns,
                },
            }
            if source_after != source_before:
                raise RuntimeError("Source FEM/H3D changed during validation")

            result = {
                "run_status": run_detail["status"],
                "task_count": len(tasks),
                "completed_tasks": sum(1 for t in tasks if t["status"] == "completed"),
                "failed_tasks": sum(1 for t in tasks if t["status"] == "failed"),
                "h3d_index": {
                    "subcases": len(result_index.get("subcases", [])),
                    "simulations": len(result_index.get("simulations", [])),
                    "result_types": len(result_index.get("result_types", [])),
                },
                "hotspot_count": len(hotspots),
                "stress_max": max(
                    (
                        float(item["value"])
                        for item in hotspots
                        if item["result_kind"] == "stress"
                    ),
                    default=None,
                ),
                "displacement_max": max(
                    (
                        float(item["value"])
                        for item in hotspots
                        if item["result_kind"] == "displacement"
                    ),
                    default=None,
                ),
                "capture_count": capture_count,
                "capture_dimensions": capture_dimensions,
                "unique_capture_hashes": len(capture_hashes),
                "capture_review": capture_review,
                "report_slides": len(report.get("slides", [])),
                "pptx_export": {
                    "status": export["status"],
                    "path": export["path"],
                    "download_bytes": len(download.content),
                },
                "web_status": web.status_code,
                "diagnostics": diagnostics["id"],
                "sources_unchanged": source_after == source_before,
                "rerun": rerun_result,
            }
            result_path = run_root / "result.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nResult saved to: {result_path}")

    finally:
        for process in (worker, server):
            if process is not None:
                stop_process_tree(process)
        for stream in (server_log, server_err, worker_log, worker_err):
            stream.close()
        print("\nDone.")


if __name__ == "__main__":
    main()
