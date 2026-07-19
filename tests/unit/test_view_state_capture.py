from __future__ import annotations

from pathlib import Path

from PIL import Image

from cae_report_worker.imaging import create_capture


def test_capture_has_view_state_and_valid_png(tmp_path: Path) -> None:
    capture = create_capture(tmp_path, "run_test", "Stress hotspot", "local_isometric", source_fingerprint="abc")
    assert capture["view_state"]["schema_version"] == 1
    assert capture["view_state"]["source_fingerprint"] == "abc"
    assert capture["sha256"]
    with Image.open(capture["image_path"]) as image:
        assert image.size == (1920, 1080)
        assert image.format == "PNG"


def test_component_views_keep_pool_qualified_hotspot_target(tmp_path: Path) -> None:
    hotspot = {
        "subcase": "FULL_LOAD",
        "entity_type": "element",
        "entity_pool": "Shell",
        "entity_id": 1234,
        "component_id": 7,
        "component_pool": "Part",
        "component_name": "RAIL_LEFT_INNER",
        "value": 205.5,
        "unit": "MPa",
        "coordinate": [10.0, 20.0, 30.0],
    }
    isolate = create_capture(tmp_path, "run_test", "iso", "component_isolate", hotspot=hotspot)
    context = create_capture(tmp_path, "run_test", "ctx", "component_context", hotspot=hotspot)
    local = create_capture(tmp_path, "run_test", "loc", "local_isometric", hotspot=hotspot)

    for capture in (isolate, context):
        target = capture["view_state"]["target"]
        assert target["entity_type"] == "element"
        assert target["entity_pool"] == "Shell"
        assert target["entity_id"] == 1234
        assert target["component_id"] == 7
        assert target["component_pool"] == "Part"

    # local_isometric stays pointed at the bare entity so view-state restore
    # can zoom HyperView on the actual hotspot peak.
    assert local["view_state"]["target"]["entity_type"] == "element"
    assert local["view_state"]["target"]["entity_id"] == 1234
    assert local["view_state"]["target"]["component_id"] == 7
