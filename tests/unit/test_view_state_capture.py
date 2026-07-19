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

