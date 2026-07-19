from __future__ import annotations

import hashlib
import os
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image

from .fake_adapter import DEFAULT_VIEW_STATE
from .session_manager import HyperViewSession, HyperViewSessionManager


def _bootstrap_tcl() -> Path:
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return bundle_root / "hyperview" / "bootstrap.tcl"
    return Path(__file__).resolve().parents[4] / "hyperview" / "bootstrap.tcl"


def _restore_payload(view_state: dict[str, Any]) -> dict[str, str]:
    subcase = view_state.get("subcase") or {}
    simulation = view_state.get("simulation") or {}
    result = view_state.get("result") or {}
    contour = view_state.get("contour") or {}
    target = view_state.get("target") or {}
    camera = view_state.get("camera") or {}
    render = view_state.get("render") or {}
    matrix = camera.get("matrix")
    matrix_text = ""
    if isinstance(matrix, list) and len(matrix) == 16:
        matrix_text = " ".join(str(float(value)) for value in matrix)

    def boolean(value: Any) -> str:
        return "true" if bool(value) else "false"

    return {
        "subcase_name": str(subcase.get("name") or ""),
        "simulation_name": str(simulation.get("name") or ""),
        "result_type": str(result.get("type") or ""),
        "result_component": str(result.get("component") or ""),
        "contour_enabled": boolean(contour.get("enabled", True)),
        "averaging": str(contour.get("averaging") or ""),
        "legend_precision": str(contour.get("precision") if contour.get("precision") is not None else ""),
        "legend_visible": boolean(render.get("legend_visible", True)),
        "target_entity_type": str(target.get("entity_type") or ""),
        "target_entity_id": str(target.get("entity_id") if target.get("entity_id") is not None else ""),
        "camera_preset": str(camera.get("preset") or ""),
        "camera_matrix": matrix_text,
    }


class RealHyperViewAdapter:
    def __init__(
        self,
        run_id: str,
        runtime_dir: Path,
        *,
        background: bool | None = None,
    ) -> None:
        executable = Path(
            os.environ.get(
                "CAE_REPORT_HYPERVIEW_EXE",
                "C:/Program Files/Altair/2019/hw/bin/win64/hw.exe",
            )
        )
        self.run_id = run_id
        if background is None:
            background = os.environ.get("CAE_REPORT_HYPERVIEW_BACKGROUND", "1") != "0"
        self.background = background
        self.manager = HyperViewSessionManager(
            runtime_dir,
            executable,
            _bootstrap_tcl(),
            background=background,
        )
        self.session: HyperViewSession | None = None
        self.source: Path | None = None
        self.source_fingerprint = ""
        self._index: dict[str, Any] | None = None

    def open_source(self, path: Path, fingerprint: str) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(path)
        if self.session is None:
            self.session = self.manager.start(self.run_id, path)
        result = self.session.request("source.open", {"path": str(path.resolve())}, timeout=120)
        self.source = path.resolve()
        self.source_fingerprint = fingerprint
        self._index = None
        return {**result, "path": str(self.source)}

    def index(self) -> dict[str, Any]:
        session = self._require_session()
        if self._index is None:
            self._index = session.request("source.index", timeout=120)
        return self._index

    def hotspots(self, kind: str, top_n: int = 3) -> list[dict[str, Any]]:
        index = self.index()
        subcases = list(index.get("subcases", []))
        if not subcases:
            raise RuntimeError("H3D_INDEX_EMPTY: no subcases")
        result_types = list(index.get("result_types", []))
        if kind == "stress":
            result_type = next(
                (
                    item
                    for item in result_types
                    if "stress" in str(item.get("name", "")).lower()
                    and "2d" in str(item.get("name", "")).lower()
                ),
                None,
            )
            component = "vonMises"
            unit = "MPa"
        else:
            result_type = next(
                (
                    item
                    for item in result_types
                    if "displacement" in str(item.get("name", "")).lower()
                ),
                None,
            )
            component = "Mag"
            unit = "mm"
        if result_type is None:
            raise RuntimeError(f"H3D_RESULT_MISSING: no {kind} result type")
        components = [str(value) for value in result_type.get("components", [])]
        if component not in components:
            if not components:
                raise RuntimeError(f"H3D_RESULT_MISSING: no components for {result_type['name']}")
            component = components[0]

        subcase = subcases[0]
        subcase_id = int(subcase["id"])
        simulations = [
            item for item in index.get("simulations", []) if int(item.get("subcase_id", -1)) == subcase_id
        ]
        simulation = simulations[0] if simulations else {"index": 0, "name": ""}
        query = self._require_session().request(
            "result.query_max",
            {
                "subcase_id": str(subcase_id),
                "simulation_index": str(simulation.get("index", 0)),
                "data_type": str(result_type["name"]),
                "component": component,
                "count": str(max(top_n, 1)),
            },
            timeout=120,
        )
        hotspots: list[dict[str, Any]] = []
        for rank, item in enumerate(query.get("items", []), start=1):
            hotspots.append(
                {
                    "subcase": str(subcase.get("name", subcase_id)),
                    "simulation": str(simulation.get("name", "")),
                    "result_type": str(result_type["name"]),
                    "result_component": component,
                    "rank": rank,
                    "entity_type": str(item["entity_type"]),
                    "entity_id": int(item["entity_id"]),
                    "component_id": None,
                    "component_name": "",
                    "value": float(item["value"]),
                    "unit": unit,
                    "coordinate": None,
                    "cluster_id": f"{kind}:{subcase_id}:{item['entity_id']}",
                    "classification": "unknown",
                    "review_status": "unknown",
                }
            )
        if not hotspots:
            raise RuntimeError(f"H3D_RESULT_EMPTY: no {kind} values")
        return hotspots

    def capture(
        self,
        project_path: Path,
        run_id: str,
        name: str,
        view_name: str,
        *,
        hotspot: dict[str, Any] | None = None,
        logical_capture_id: str | None = None,
        view_state: dict[str, Any] | None = None,
        width: int = 1920,
        height: int = 1080,
    ) -> dict[str, Any]:
        session = self._require_session()
        capture_id = logical_capture_id or f"cap_{uuid.uuid4().hex}"
        file_id = f"capv_{uuid.uuid4().hex}"
        capture_dir = project_path / "captures" / run_id
        thumbnail_dir = project_path / "thumbnails" / run_id
        capture_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        image_path = capture_dir / f"{file_id}.png"
        thumbnail_path = thumbnail_dir / f"{file_id}.png"

        if view_state is None:
            target = {
                "entity_type": hotspot.get("entity_type", "") if hotspot else "",
                "entity_id": hotspot.get("entity_id") if hotspot else None,
                "component_id": hotspot.get("component_id") if hotspot else None,
                "coordinate": hotspot.get("coordinate") if hotspot else None,
            }
            view_state = {
                **DEFAULT_VIEW_STATE,
                "source_fingerprint": self.source_fingerprint,
                "subcase": {"name": hotspot.get("subcase")} if hotspot else {},
                "simulation": {"name": hotspot.get("simulation")} if hotspot else {},
                "result": {
                    "type": hotspot.get("result_type"),
                    "component": hotspot.get("result_component"),
                }
                if hotspot
                else {},
                "target": target,
                "camera": {
                    "preset": view_name,
                    "matrix": None,
                    "center": target.get("coordinate"),
                    "zoom": 1.0,
                },
            }
        else:
            view_state = deepcopy(view_state)
        session.request("view.apply", _restore_payload(view_state))
        session.request(
            "capture.execute",
            {"path": str(image_path.resolve()), "width": str(width), "height": str(height)},
            timeout=120,
        )
        with Image.open(image_path) as image:
            if image.format != "PNG" or image.size != (width, height):
                raise RuntimeError(
                    f"CAPTURE_INVALID: expected PNG {width}x{height}, got {image.format} {image.size}"
                )
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((480, 270))
            thumbnail.save(thumbnail_path, "PNG")
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        actual_view = session.request("view.read")
        actual_camera = actual_view.get("camera") or {}
        matrix = actual_camera.get("matrix")
        if isinstance(matrix, list) and len(matrix) == 16:
            view_state["camera"] = {**view_state["camera"], "matrix": matrix}
        return {
            "id": capture_id,
            "name": name,
            "view_name": view_name,
            "image_path": str(image_path.resolve()),
            "thumbnail_path": str(thumbnail_path.resolve()),
            "sha256": digest,
            "view_state": view_state,
            "width": width,
            "height": height,
        }

    def apply_view(
        self,
        view_state: dict[str, Any],
        *,
        bring_to_front: bool = False,
    ) -> dict[str, Any]:
        session = self._require_session()
        result = session.request("view.restore", _restore_payload(view_state), timeout=120)
        if bring_to_front:
            result["brought_to_front"] = session.bring_to_front()
        return result

    def close(self) -> None:
        if self.session is not None:
            self.session.stop()
            self.session = None

    @property
    def is_alive(self) -> bool:
        return self.session is not None and self.session.process.poll() is None

    def _require_session(self) -> HyperViewSession:
        if self.session is None:
            raise RuntimeError("HV_START_FAILED: source is not open")
        return self.session
