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

    # Viewport rectangle. Same size across views; the difference between views
    # is what is rendered inside it (so users can visually tell component
    # isolate / context / standard views apart from the global full-model shot).
    canvas_box = (120, 170, width - 120, height - 120)
    draw.rounded_rectangle(canvas_box, radius=28, fill=(224, 231, 238), outline=(123, 147, 168), width=4)

    # Derive per-component color from the hotspot's component id so different
    # components render in different colours and are visually distinguishable.
    component_id = (hotspot or {}).get("component_id")
    component_name = str((hotspot or {}).get("component_name", "")) or "Unassigned"
    coordinate = (hotspot or {}).get("coordinate") if hotspot else None
    seed = int(abs(hash((component_id, component_name)))) % 6
    palette = [(39, 85, 122), (53, 141, 156), (242, 174, 73), (203, 70, 70), (124, 58, 237), (13, 148, 136)]
    component_color = palette[seed]
    legend_items = ((39, 85, 122), (53, 141, 156), (242, 174, 73), (203, 70, 70))

    component_center = None
    if isinstance(coordinate, list) and len(coordinate) == 3:
        # Map a fake "component" rectangle near the hotspot coordinate so the
        # user can spot which component is being isolated / hovered.
        cx = (canvas_box[0] + canvas_box[2]) / 2.0 + (coordinate[0] % 400 - 200)
        cy = (canvas_box[1] + canvas_box[3]) / 2.0 + (coordinate[1] % 200 - 100)
        component_center = (cx, cy)

    def draw_full_model(*, faded_alpha: int = 255) -> None:
        """Draw the unified frame + cross-beam ellipse used for global views."""
        overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.ellipse(
            (width * 0.34, height * 0.28, width * 0.66, height * 0.78),
            fill=(54, 132, 148, faded_alpha),
            outline=(18, 86, 100, faded_alpha),
            width=8,
        )
        for index, color in enumerate(legend_items):
            overlay_draw.rectangle(
                (width - 250, 210 + index * 115, width - 185, 295 + index * 115),
                fill=(*color, faded_alpha),
            )
        image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"), (0, 0))

    def draw_component_block(highlight: bool) -> None:
        if component_center is None:
            draw_full_model()
            return
        cx, cy = component_center
        box_w, box_h = 460, 280
        box = (cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2)
        if highlight:
            # Draw faded frame first then highlight component on top
            draw_full_model(faded_alpha=90)
        draw.rectangle(box, fill=component_color, outline=(12, 36, 60), width=4)
        label = component_name[:22]
        try:
            bbox = draw.textbbox((0, 0), label, font=small)
            text_w = bbox[2] - bbox[0]
        except Exception:
            text_w = len(label) * 12
        draw.text((cx - text_w / 2, cy - 12), label, fill=(255, 255, 255), font=small)

    if view_name == "component_isolate":
        draw_component_block(highlight=False)
    elif view_name == "component_context":
        draw_component_block(highlight=True)
    elif view_name == "local_isometric":
        # Zoom on the hotspot's component box (only that block, larger)
        if component_center is None:
            draw.ellipse(
                (width * 0.30, height * 0.24, width * 0.70, height * 0.84),
                fill=(54, 132, 148), outline=(18, 86, 100), width=10,
            )
        else:
            cx, cy = component_center
            box_w, box_h = 760, 460
            draw.rectangle((cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2),
                           fill=component_color, outline=(12, 36, 60), width=6)
    else:
        # global / front / right / top -> full model silhouette
        draw_full_model()

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
    component_id = hotspot.get("component_id") if hotspot else None
    target = {
        "entity_type": hotspot.get("entity_type", "") if hotspot else "",
        "entity_pool": hotspot.get("entity_pool", "") if hotspot else "",
        "entity_id": hotspot.get("entity_id") if hotspot else None,
        "component_id": component_id,
        "component_pool": hotspot.get("component_pool", "") if hotspot else "",
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
