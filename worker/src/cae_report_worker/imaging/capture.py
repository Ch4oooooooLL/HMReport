from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from cae_report_worker.hyperview.fake_adapter import DEFAULT_VIEW_STATE


def create_capture(
    project_path: Path,
    run_id: str,
    name: str,
    view_name: str,
    *,
    hotspot: dict[str, Any] | None = None,
    source_fingerprint: str = "",
    width: int = 1920,
    height: int = 1080,
    logical_capture_id: str | None = None,
) -> dict[str, Any]:
    capture_id = logical_capture_id or f"cap_{uuid.uuid4().hex}"
    file_id = f"capv_{uuid.uuid4().hex}"
    capture_dir = project_path / "captures" / run_id
    thumbnail_dir = project_path / "thumbnails" / run_id
    capture_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    image_path = capture_dir / f"{file_id}.png"
    thumbnail_path = thumbnail_dir / f"{file_id}.png"
    image = Image.new("RGB", (width, height), (245, 248, 251))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=34)
    small = ImageFont.load_default(size=22)
    draw.rectangle((0, 0, width, 92), fill=(20, 38, 60))
    draw.text((48, 24), "CAE RESULT WORKBENCH / FAKE HYPERVIEW", fill=(255, 255, 255), font=font)
    draw.rounded_rectangle((120, 170, width - 120, height - 120), radius=28, fill=(224, 231, 238), outline=(123, 147, 168), width=4)
    draw.ellipse((width * 0.34, height * 0.28, width * 0.66, height * 0.78), fill=(54, 132, 148), outline=(18, 86, 100), width=8)
    for index, color in enumerate(((39, 85, 122), (53, 141, 156), (242, 174, 73), (203, 70, 70))):
        draw.rectangle((width - 250, 210 + index * 115, width - 185, 295 + index * 115), fill=color)
    draw.text((150, height - 200), name, fill=(21, 43, 62), font=font)
    detail = f"View: {view_name}"
    if hotspot:
        detail += f"  |  {hotspot.get('component_name')} / {hotspot.get('entity_type')} {hotspot.get('entity_id')}  |  {hotspot.get('value')} {hotspot.get('unit')}"
    draw.text((150, height - 155), detail, fill=(56, 76, 92), font=small)
    image.save(image_path, "PNG")
    thumb = image.copy()
    thumb.thumbnail((480, 270))
    thumb.save(thumbnail_path, "PNG")
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    target = {
        "entity_type": hotspot.get("entity_type", "") if hotspot else "",
        "entity_id": hotspot.get("entity_id") if hotspot else None,
        "component_id": hotspot.get("component_id") if hotspot else None,
        "coordinate": hotspot.get("coordinate") if hotspot else None,
    }
    view_state = {
        **DEFAULT_VIEW_STATE,
        "source_fingerprint": source_fingerprint,
        "subcase": {"name": hotspot.get("subcase")} if hotspot else {},
        "result": {"type": hotspot.get("result_type"), "component": hotspot.get("result_component")} if hotspot else {},
        "target": target,
        "camera": {"preset": view_name, "matrix": None, "center": target.get("coordinate"), "zoom": 1.0},
    }
    return {
        "id": capture_id,
        "name": name,
        "view_name": view_name,
        "image_path": str(image_path),
        "thumbnail_path": str(thumbnail_path),
        "sha256": digest,
        "view_state": view_state,
        "width": width,
        "height": height,
    }
