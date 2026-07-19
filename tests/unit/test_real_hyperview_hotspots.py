from __future__ import annotations

from pathlib import Path
from typing import Any

from cae_report_worker.hyperview.real_adapter import RealHyperViewAdapter


class StubSession:
    def request(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        assert command == "result.query_max"
        assert payload is not None
        return {
            "items": [
                {
                    "entity_type": "element",
                    "entity_pool": "2D",
                    "entity_id": 1016,
                    "component_id": 110,
                    "component_pool": "Global",
                    "component_name": "RBE3_LOAD_PATCH",
                    "value": 2084.0,
                }
            ]
        }


def test_real_hotspots_keep_pool_qualified_component_metadata(tmp_path: Path) -> None:
    adapter = RealHyperViewAdapter("test", tmp_path)
    adapter.session = StubSession()  # type: ignore[assignment]
    adapter._index = {
        "subcases": [{"id": 1, "name": "FULL_LOAD"}],
        "simulations": [
            {"subcase_id": 1, "index": 0, "name": "Static Analysis"}
        ],
        "result_types": [
            {
                "name": "Element Stresses (2D & 3D)",
                "components": ["vonMises"],
            }
        ],
    }

    [hotspot] = adapter.hotspots("stress", top_n=1)

    assert hotspot["entity_type"] == "element"
    assert hotspot["entity_pool"] == "2D"
    assert hotspot["entity_id"] == 1016
    assert hotspot["component_id"] == 110
    assert hotspot["component_pool"] == "Global"
    assert hotspot["component_name"] == "RBE3_LOAD_PATCH"
