import pytest

from cae_report_worker.hyperview.real_adapter import _require_exact_view, _restore_payload


def test_restore_payload_flattens_complete_view_state() -> None:
    payload = _restore_payload(
        {
            "subcase": {"name": "FULL_LOAD"},
            "simulation": {"name": "Static Analysis"},
            "result": {"type": "Element Stresses", "component": "vonMises"},
            "contour": {"enabled": True, "averaging": "simple", "precision": 4},
            "target": {
                "entity_type": "element",
                "entity_pool": "Shell",
                "entity_id": 1018,
                "component_id": 7,
                "component_pool": "Part",
            },
            "camera": {"preset": "local_isometric", "matrix": list(range(16))},
            "render": {"legend_visible": False},
        }
    )

    assert payload == {
        "subcase_name": "FULL_LOAD",
        "simulation_name": "Static Analysis",
        "result_type": "Element Stresses",
        "result_component": "vonMises",
        "contour_enabled": "true",
        "averaging": "simple",
        "legend_precision": "4",
        "legend_visible": "false",
        "target_entity_type": "element",
        "target_entity_pool": "Shell",
        "target_entity_id": "1018",
        "target_component_id": "7",
        "target_component_pool": "Part",
        "camera_preset": "local_isometric",
        "camera_matrix": " ".join(str(float(value)) for value in range(16)),
    }


def test_restore_payload_keeps_legacy_view_without_matrix_restorable() -> None:
    payload = _restore_payload(
        {
            "camera": {"preset": "front", "matrix": None},
            "contour": {"enabled": True, "precision": None},
        }
    )

    assert payload["camera_preset"] == "front"
    assert payload["camera_matrix"] == ""
    assert payload["legend_precision"] == ""
    assert payload["target_component_id"] == ""
    assert payload["target_component_pool"] == ""


def test_capture_rejects_partially_applied_view() -> None:
    with pytest.raises(
        RuntimeError,
        match=r"VIEW_APPLY_PARTIAL: target, visibility \| unsupported API",
    ):
        _require_exact_view(
            {
                "restore": "partial",
                "missing": ["target", "visibility"],
                "warning": "unsupported API",
            }
        )
