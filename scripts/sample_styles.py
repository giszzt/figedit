#!/usr/bin/env python3
"""Color and style sampling helpers for SVG reconstruction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def _rgb_to_hex(rgb: np.ndarray | tuple[int, int, int]) -> str:
    r, g, b = [int(v) for v in rgb[:3]]
    return f"#{r:02x}{g:02x}{b:02x}"


def _sample_box(arr: np.ndarray, x: int, y: int, w: int, h: int) -> str:
    height, width = arr.shape[:2]
    x1 = max(0, min(width - 1, x))
    y1 = max(0, min(height - 1, y))
    x2 = max(x1 + 1, min(width, x + w))
    y2 = max(y1 + 1, min(height, y + h))
    pixels = arr[y1:y2, x1:x2, :3].reshape(-1, 3)
    return _rgb_to_hex(np.median(pixels, axis=0))


def sample_styles(image_path: Path, primitives: dict[str, Any] | None = None) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    arr = np.asarray(image)
    h, w = arr.shape[:2]
    corner = np.vstack([arr[: max(5, h // 30), : max(5, w // 30)], arr[-max(5, h // 30) :, -max(5, w // 30) :]]).reshape(-1, 3)
    background = _rgb_to_hex(np.median(corner, axis=0))

    rect_styles = []
    for rect in (primitives or {}).get("rectangles", [])[:80]:
        x, y, rw, rh = int(rect["x"]), int(rect["y"]), int(rect["w"]), int(rect["h"])
        interior = _sample_box(arr, x + max(2, rw // 8), y + max(2, rh // 8), max(1, rw // 2), max(1, rh // 2))
        stroke_samples = []
        for px, py in [(x, y + rh // 2), (x + rw - 1, y + rh // 2), (x + rw // 2, y), (x + rw // 2, y + rh - 1)]:
            if 0 <= px < w and 0 <= py < h:
                stroke_samples.append(arr[py, px, :3])
        stroke = _rgb_to_hex(np.median(np.asarray(stroke_samples), axis=0)) if stroke_samples else "#111111"
        rect_styles.append({"element_id": rect.get("id"), "fill": interior, "stroke": stroke, "stroke_width": 2})

    dominant = []
    small = image.resize((max(1, w // 8), max(1, h // 8)))
    q = np.asarray(small).reshape(-1, 3)
    q = (q // 16) * 16
    colors, counts = np.unique(q, axis=0, return_counts=True)
    for idx in np.argsort(counts)[-10:][::-1]:
        dominant.append({"color": _rgb_to_hex(colors[idx]), "count": int(counts[idx])})

    return {
        "background": background,
        "dominant_colors": dominant,
        "rect_styles": rect_styles,
        "default_stroke": "#111111",
        "default_text": "#111111",
        "style_source": "pixel-sampling",
    }


def save_style_outputs(image_path: Path, primitives_json: Path, out_json: Path, overlay_path: Path) -> dict[str, Any]:
    primitives = {}
    if primitives_json.exists():
        primitives = json.loads(primitives_json.read_text(encoding="utf-8"))
    styles = sample_styles(image_path, primitives)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(styles, ensure_ascii=False, indent=2), encoding="utf-8")

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    y = 12
    for item in styles.get("dominant_colors", [])[:8]:
        color = item["color"]
        draw.rectangle([12, y, 62, y + 24], fill=color)
        draw.text((70, y + 5), color, fill=(0, 0, 0))
        y += 30
    image.save(overlay_path)
    return styles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--primitives", type=Path, default=Path("detected_primitives.json"))
    parser.add_argument("--out", type=Path, default=Path("style_tokens.json"))
    parser.add_argument("--overlay", type=Path, default=Path("diagnostics/style_overlay.png"))
    args = parser.parse_args()
    styles = save_style_outputs(args.image, args.primitives, args.out, args.overlay)
    print(json.dumps({"background": styles.get("background"), "dominant": len(styles.get("dominant_colors", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
