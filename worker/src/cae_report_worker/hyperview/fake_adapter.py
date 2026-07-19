from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

DEFAULT_VIEW_STATE: dict[str, Any] = {
    "schema_version": 1,
    "source_fingerprint": "",
    "subcase": {},
    "simulation": {},
    "result": {},
    "contour": {"enabled": True, "averaging": "simple", "legend_min": None, "legend_max": None, "precision": 3},
    "deformation": {"enabled": False, "scale_mode": "model", "scale": 1.0},
    "visibility": {"visible_components": [], "hidden_components": []},
    "target": {"entity_type": "", "entity_id": None, "component_id": None, "coordinate": None},
    "camera": {"preset": "isometric", "matrix": None, "center": None, "zoom": None},
    "render": {"transparency": False, "legend_visible": True, "background": [248, 250, 252]},
}


class FakeHyperViewAdapter:
    def __init__(self) -> None:
        self.source: Path | None = None
        self.view_state = {**DEFAULT_VIEW_STATE}

    def open_source(self, path: Path, fingerprint: str) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(path)
        self.source = path
        self.view_state = {**DEFAULT_VIEW_STATE, "source_fingerprint": fingerprint}
        return {"status": "ready", "path": str(path)}

    def index(self) -> dict[str, Any]:
        if self.source is None:
            raise RuntimeError("source not open")
        return {
            "model": {"name": self.source.stem},
            "subcases": [
                {"id": 1, "name": "FULL_LOAD"},
                {"id": 2, "name": "BRAKE_LOAD"},
            ],
            "simulations": [
                {"id": 1, "subcase_id": 1, "name": "Static"},
                {"id": 2, "subcase_id": 2, "name": "Static"},
            ],
            "result_types": [
                {"id": "stress", "name": "Element Stresses", "components": ["vonMises", "XX", "YY", "XY"], "unit": "MPa"},
                {"id": "displacement", "name": "Displacement", "components": ["Mag", "X", "Y", "Z"], "unit": "mm"},
            ],
        }

    def hotspots(self, kind: str, top_n: int = 3) -> list[dict[str, Any]]:
        """Return ``top_n`` candidates PER subcase listed by :meth:`index`.

        The fake adapter's index advertises two subcases (FULL_LOAD,
        BRAKE_LOAD). For each subcase we return ``top_n`` synthetic
        hotspot candidates so the executor / dedup helper sees multiple
        subcases' worth of data (matching real HyperView behaviour where
        each subcase has its own top-N stress peaks).
        """
        if self.source is None:
            raise RuntimeError("source not open")
        seed = int(hashlib.sha256(str(self.source).encode()).hexdigest()[:8], 16)
        base = 220.0 if kind == "stress" else 4.8
        unit = "MPa" if kind == "stress" else "mm"
        entity_type = "element" if kind == "stress" else "node"
        result_type_name = "Element Stresses" if kind == "stress" else "Displacement"
        result_component = "vonMises" if kind == "stress" else "Mag"
        subcase_names = [str(item["name"]) for item in self.index().get("subcases", [])] or ["FULL_LOAD"]
        hotspots: list[dict[str, Any]] = []
        for subcase_offset, subcase_name in enumerate(subcase_names):
            for rank in range(1, top_n + 1):
                seed_rank = seed % 100000 + subcase_offset * 1000 + rank
                component_id = subcase_offset * 10 + rank
                hotspots.append(
                    {
                        "subcase": subcase_name,
                        "simulation": "Static",
                        "result_type": result_type_name,
                        "result_component": result_component,
                        "rank": rank,
                        "entity_type": entity_type,
                        "entity_id": seed_rank,
                        "component_id": component_id,
                        "component_name": f"{subcase_name}_STRUCT_{rank:02d}",
                        "value": round(base * (1 - (rank - 1) * 0.12) * (1.0 - 0.05 * subcase_offset), 4),
                        "unit": unit,
                        "coordinate": [100.0 + rank * 20 + subcase_offset * 400, 45.0 - rank * 3, 18.0 + rank],
                        "cluster_id": f"cluster-{subcase_offset}-{rank}",
                        "classification": "unknown",
                        "review_status": "unknown",
                    }
                )
        return hotspots

    def apply_view(self, view_state: dict[str, Any]) -> dict[str, Any]:
        self.view_state = view_state
        return {"restore": "exact", "missing": []}

    def read_view(self) -> dict[str, Any]:
        return self.view_state

