from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _is_background(pixel: tuple[int, int, int]) -> bool:
    """Recognize the light neutral checkerboard baked into the supplied image."""
    return min(pixel) >= 225 and max(pixel) - min(pixel) <= 8


def remove_connected_checkerboard(image: Image.Image) -> Image.Image:
    """Make only the checkerboard connected to the canvas edge transparent.

    Limiting removal to the edge-connected area protects the white report sheet and
    intentionally pale regions inside the dark model outline.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if not visited[index] and _is_background(pixels[x, y]):
            visited[index] = 1
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x:
            enqueue(x - 1, y)
        if x + 1 < width:
            enqueue(x + 1, y)
        if y:
            enqueue(x, y - 1)
        if y + 1 < height:
            enqueue(x, y + 1)

    rgba = rgb.convert("RGBA")
    alpha = Image.new("L", rgb.size, 255)
    alpha_pixels = alpha.load()
    for index, is_background in enumerate(visited):
        if is_background:
            alpha_pixels[index % width, index // width] = 0
    rgba.putalpha(alpha)
    return rgba


def generate(source: Path, png_output: Path, ico_output: Path) -> None:
    with Image.open(source) as source_image:
        icon = remove_connected_checkerboard(source_image)
    png_output.parent.mkdir(parents=True, exist_ok=True)
    icon.save(png_output, format="PNG", optimize=True)
    icon.save(ico_output, format="ICO", sizes=[(size, size) for size in ICO_SIZES])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate transparent PNG and Windows ICO assets.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--png", type=Path, default=Path("resources/app-icon.png"))
    parser.add_argument("--ico", type=Path, default=Path("resources/app-icon.ico"))
    args = parser.parse_args()
    generate(args.source, args.png, args.ico)


if __name__ == "__main__":
    main()
