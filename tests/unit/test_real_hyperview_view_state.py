from cae_report_worker.hyperview.real_adapter import _restore_payload


def test_restore_payload_flattens_complete_view_state() -> None:
    payload = _restore_payload(
        {
            "subcase": {"name": "FULL_LOAD"},
            "simulation": {"name": "Static Analysis"},
            "result": {"type": "Element Stresses", "component": "vonMises"},
            "contour": {"enabled": True, "averaging": "simple", "precision": 4},
            "target": {"entity_type": "element", "entity_id": 1018},
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
        "target_entity_id": "1018",
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
