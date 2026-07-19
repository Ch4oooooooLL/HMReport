from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from cae_report_worker.hyperview import RealHyperViewAdapter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_H3D = ROOT / "examples" / "optistruct_feature_model" / "optistruct_feature_model.h3d"
VIEWS = (
    "global",
    "local_isometric",
    "front",
    "right",
    "top",
    "component_isolate",
    "component_context",
)


def _valid_png(capture: dict[str, Any]) -> None:
    with Image.open(capture["image_path"]) as image:
        if image.format != "PNG" or image.size != (1920, 1080):
            raise RuntimeError(
                f"{capture['view_name']}: expected PNG 1920x1080, "
                f"got {image.format} {image.size}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify component isolate/context captures against HyperView 2019."
    )
    parser.add_argument("--h3d", type=Path, default=DEFAULT_H3D)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runtime" / "component-capture-verification",
    )
    args = parser.parse_args()

    run_id = f"component_capture_{datetime.now():%Y%m%d_%H%M%S}"
    adapter = RealHyperViewAdapter(run_id, args.output / "hyperview")
    try:
        adapter.open_source(args.h3d.resolve(), "real-component-capture-verification")
        hotspots = adapter.hotspots("stress", top_n=1)
        hotspot = next(
            (
                item
                for item in hotspots
                if item.get("component_id") and item.get("entity_pool")
            ),
            None,
        )
        if hotspot is None:
            raise RuntimeError("No stress hotspot with component and entity-pool metadata")

        captures = [
            adapter.capture(
                args.output,
                run_id,
                f"Component verification / {view}",
                view,
                hotspot=hotspot,
            )
            for view in VIEWS
        ]
        for capture in captures:
            _valid_png(capture)

        hashes = {str(item["view_name"]): str(item["sha256"]) for item in captures}
        required_differences = (
            ("global", "component_isolate"),
            ("global", "component_context"),
            ("component_isolate", "component_context"),
            ("front", "right"),
            ("right", "top"),
        )
        identical = [
            f"{left} == {right}"
            for left, right in required_differences
            if hashes[left] == hashes[right]
        ]
        if identical:
            raise RuntimeError(
                "Component capture views did not change pixels: " + ", ".join(identical)
            )

        result = {
            "status": "passed",
            "h3d_path": str(args.h3d.resolve()),
            "run_id": run_id,
            "hotspot": hotspot,
            "captures": [
                {
                    "view_name": item["view_name"],
                    "image_path": item["image_path"],
                    "sha256": item["sha256"],
                }
                for item in captures
            ],
        }
        args.output.mkdir(parents=True, exist_ok=True)
        result_path = args.output / f"{run_id}.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({**result, "result_path": str(result_path)}, ensure_ascii=False, indent=2))
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
