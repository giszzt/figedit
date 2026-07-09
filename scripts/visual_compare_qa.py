#!/usr/bin/env python3
"""Pixel-level comparison between the source figure and the rendered preview.

Produces three review images and a per-tile difference report, so crop
misplacement, text drift, missing elements, and color deviations surface as
concrete worst-region rectangles instead of relying on eyeballing alone.

Usage:
  python scripts/visual_compare_qa.py source.png out/preview.png --out-dir out/diagnostics/visual_qa

Outputs in --out-dir:
  side_by_side.png   source | preview
  blend.png          50/50 overlay; ghosting reveals drift
  diff_heatmap.png   red intensity = perceptual difference, worst tiles boxed
  visual_qa.json     global and per-tile scores

The report is advisory. High-difference tiles are review triggers, not
automatic failures: a legitimate redesign of a region (e.g. retyped text with
a cleaner font) also scores as difference.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image, ImageDraw


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """rgb float 0..255, shape (..., 3) -> CIE Lab (D65)."""
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = lin @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    lab = np.empty_like(xyz)
    lab[..., 0] = 116.0 * f[..., 1] - 16.0
    lab[..., 1] = 500.0 * (f[..., 0] - f[..., 1])
    lab[..., 2] = 200.0 * (f[..., 1] - f[..., 2])
    return lab


def compare(source: Image.Image, preview: Image.Image, out_dir: Path, tiles: int = 12, top_n: int = 8) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    src = source.convert("RGB")
    prev = preview.convert("RGB")
    if prev.size != src.size:
        prev = prev.resize(src.size, Image.LANCZOS)

    a = np.asarray(src, dtype=np.float64)
    b = np.asarray(prev, dtype=np.float64)
    delta = np.sqrt(((_srgb_to_lab(a) - _srgb_to_lab(b)) ** 2).sum(axis=2))

    h, w = delta.shape
    th, tw = max(32, h // tiles), max(32, w // tiles)
    tile_scores = []
    for ty in range(0, h, th):
        for tx in range(0, w, tw):
            block = delta[ty : min(h, ty + th), tx : min(w, tx + tw)]
            tile_scores.append({
                "x": tx, "y": ty, "w": int(min(w, tx + tw) - tx), "h": int(min(h, ty + th) - ty),
                "mean_delta_e": round(float(block.mean()), 2),
            })
    tile_scores.sort(key=lambda t: -t["mean_delta_e"])
    worst = tile_scores[:top_n]

    # side by side
    gap = 12
    sbs = Image.new("RGB", (src.width * 2 + gap, src.height), (255, 255, 255))
    sbs.paste(src, (0, 0))
    sbs.paste(prev, (src.width + gap, 0))
    sbs.thumbnail((2600, 2600))
    sbs.save(out_dir / "side_by_side.png")

    # blend
    Image.blend(src, prev, 0.5).save(out_dir / "blend.png")

    # heatmap: dimmed grayscale source + red channel by delta
    gray = np.asarray(src.convert("L"), dtype=np.float64) * 0.55
    heat = np.clip(delta / 40.0, 0.0, 1.0)  # deltaE 40 ≈ saturated red
    rgb = np.dstack([np.clip(gray + heat * 200.0, 0, 255), gray, gray]).astype(np.uint8)
    heat_img = Image.fromarray(rgb, "RGB")
    d = ImageDraw.Draw(heat_img)
    for t in worst:
        d.rectangle([t["x"], t["y"], t["x"] + t["w"], t["y"] + t["h"]], outline=(255, 255, 0), width=max(2, w // 800))
        d.text((t["x"] + 4, t["y"] + 4), str(t["mean_delta_e"]), fill=(255, 255, 0))
    heat_img.save(out_dir / "diff_heatmap.png")

    report = {
        "mean_delta_e": round(float(delta.mean()), 2),
        "p95_delta_e": round(float(np.percentile(delta, 95)), 2),
        "tile_grid": tiles,
        "worst_tiles": worst,
        "outputs": {
            "side_by_side": str(out_dir / "side_by_side.png"),
            "blend": str(out_dir / "blend.png"),
            "diff_heatmap": str(out_dir / "diff_heatmap.png"),
        },
        "note": "advisory report; high-difference tiles are review triggers, not automatic failures",
    }
    (out_dir / "visual_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("preview", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--tiles", type=int, default=12)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    report = compare(Image.open(args.source), Image.open(args.preview), args.out_dir, args.tiles, args.top)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
