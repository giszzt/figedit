#!/usr/bin/env python3
"""Key out a known solid chroma background from a regenerated asset sheet.

Alpha comes from color distance to the key color with a soft ramp, and
semi-transparent edge pixels are decontaminated by un-mixing the key color
(observed = alpha * true + (1 - alpha) * key, solved for true). This removes
color spill without channel hacks and works for any key color.

Usage:
  python scripts/chroma_key.py --input sheet_raw.png --out sheet.png --color "#00ff00"
  python scripts/chroma_key.py --input sheet_raw.png --out sheet.png --color "#ff00ff" --scale 2

The printed JSON report includes edge-quality warnings: residual key-colored
fringe, or opaque content close to the key color (risk of holes). Treat a
non-empty `warnings` list as a review trigger, not an automatic failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
from PIL import Image


def parse_color(text: str) -> Tuple[int, int, int]:
    value = text.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def key_image(
    image: Image.Image,
    key_rgb: Tuple[int, int, int],
    t0: float = 60.0,
    t1: float = 130.0,
    scale: int = 1,
) -> Tuple[Image.Image, Dict[str, Any]]:
    """Return (RGBA image, quality report). t0/t1 are the alpha ramp bounds:
    distance <= t0 becomes fully transparent, >= t1 fully opaque."""
    rgb = image.convert("RGB")

    # Image models often add a border or letterbox around the requested
    # canvas. Anything outside the key-colored region would survive keying as
    # a giant opaque frame, so trim to the bounding box of key-colored pixels
    # first (with a small safety inset).
    probe = np.asarray(rgb, dtype=np.float64)
    near_key = np.sqrt(((probe - np.array(key_rgb, dtype=np.float64)) ** 2).sum(axis=2)) <= t0
    if near_key.any():
        ys, xs = np.where(near_key)
        inset = 2
        bx1, by1 = int(xs.min()) + inset, int(ys.min()) + inset
        bx2, by2 = int(xs.max()) - inset + 1, int(ys.max()) - inset + 1
        if bx2 - bx1 > 16 and by2 - by1 > 16 and (bx1 > 0 or by1 > 0 or bx2 < rgb.width or by2 < rgb.height):
            rgb = rgb.crop((bx1, by1, bx2, by2))

    if scale > 1:
        rgb = rgb.resize((rgb.width * scale, rgb.height * scale), Image.LANCZOS)
    arr = np.asarray(rgb, dtype=np.float64)
    key = np.array(key_rgb, dtype=np.float64)

    dist = np.sqrt(((arr - key) ** 2).sum(axis=2))
    alpha = np.clip((dist - t0) / max(1.0, t1 - t0), 0.0, 1.0)

    # Decontaminate partially transparent pixels: solve observed = a*true + (1-a)*key.
    a3 = alpha[..., None]
    semi = (alpha > 0.02) & (alpha < 0.999)
    true_color = arr.copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        unmixed = (arr - (1.0 - a3) * key) / np.maximum(a3, 1e-6)
    true_color[semi] = np.clip(unmixed[semi], 0.0, 255.0)

    # Despill: antialiasing and jpeg compression smear the key color into a
    # band of fully-opaque pixels just inside the element boundary (they sit
    # past t1, so the alpha ramp never touches them). For opaque pixels near
    # the transparent region that still lean toward the key color, estimate
    # the contamination fraction from their key distance and unmix it.
    from scipy import ndimage

    t_spill = t1 * 1.8
    near_transparent = ndimage.binary_dilation(alpha < 0.5, iterations=max(3, 3 * scale))
    spill = near_transparent & (alpha >= 0.999) & (dist < t_spill)
    if spill.any():
        f = np.clip((t_spill - dist[spill]) / max(1.0, t_spill - t0), 0.0, 1.0) * 0.9
        f3 = f[:, None]
        true_color[spill] = np.clip((arr[spill] - f3 * key) / np.maximum(1.0 - f3, 0.1), 0.0, 255.0)

    # Global hue sweep. probe_palette guarantees that no legitimate content
    # color shares the key's hue direction, so any key-hued pixel anywhere in
    # the sheet is contamination: background showing through an enclosed hole,
    # a shadow the model cast onto the key despite the brief, or antialiasing
    # residue. Two tiers:
    #   - strongly key-colored -> it IS background; make it transparent
    #     (fixes interior holes the old contour-band pass could not reach)
    #   - weakly key-tinted    -> shadow or edge residue; desaturate to gray
    key_chroma = key - key.mean()
    key_norm = np.sqrt((key_chroma ** 2).sum())
    gray_all = true_color.mean(axis=2)
    chroma_all = true_color - gray_all[..., None]
    norms_all = np.sqrt((chroma_all ** 2).sum(axis=2))
    with np.errstate(divide="ignore", invalid="ignore"):
        cos_all = (chroma_all @ key_chroma) / np.maximum(norms_all * key_norm, 1e-6)
    visible = alpha > 0.02
    strong = visible & (cos_all > 0.92) & (norms_all > 80.0)
    weak = visible & ~strong & (cos_all > 0.90) & (norms_all > 18.0)
    if strong.any():
        alpha[strong] = 0.0
    if weak.any():
        true_color[weak] = gray_all[weak, None]

    # Unmix overshoot: on lossy (JPEG) sheets, decontaminating a blended edge
    # pixel can push it past neutral into the anti-key hue — a purple fringe
    # on a green key, a green fringe on a magenta key. Unlike the key hue,
    # anti-key colors can be legitimate content, so this cleanup is confined
    # to the thin boundary band where overshoot physically happens.
    edge_band = ndimage.binary_dilation(alpha < 0.5, iterations=max(2, 2 * scale)) & visible
    overshoot = edge_band & (cos_all < -0.90) & (norms_all > 18.0)
    if overshoot.any():
        true_color[overshoot] = gray_all[overshoot, None]

    out = np.dstack([true_color, alpha * 255.0]).astype(np.uint8)
    result = Image.fromarray(out, "RGBA")
    if scale > 1:
        result = result.resize((result.width // scale, result.height // scale), Image.LANCZOS)

    # Quality report on the final-resolution image. Fringe is measured on the
    # whole boundary band (opaque pixels adjacent to transparency included),
    # since that is where key-color residue actually survives.
    from scipy import ndimage as _ndimage

    fin = np.asarray(result, dtype=np.float64)
    fa = fin[..., 3] / 255.0
    fdist = np.sqrt(((fin[..., :3] - key) ** 2).sum(axis=2))
    edge = (fa > 0.05) & (fa < 0.95)
    band = _ndimage.binary_dilation(fa < 0.5, iterations=3) & (fa > 0.05)
    edge_count = int(edge.sum())
    band_count = int(band.sum())
    fringe = float((fdist[band] < t1).mean()) if band_count else 0.0
    opaque_near_key = int(((fa >= 0.95) & (fdist < t0)).sum())
    content_fraction = float((fa >= 0.5).mean())
    warnings = []
    if fringe > 0.08:
        warnings.append(f"residual key-colored fringe on {fringe:.1%} of edge pixels; inspect edges")
    if opaque_near_key > 200:
        warnings.append(f"{opaque_near_key} opaque pixels are near the key color; content may contain the key color (holes risk)")
    if content_fraction < 0.005:
        warnings.append("almost nothing survived keying; wrong key color or empty sheet")
    report = {
        "key_color": "#{:02x}{:02x}{:02x}".format(*key_rgb),
        "t0": t0,
        "t1": t1,
        "scale": scale,
        "content_fraction": round(content_fraction, 4),
        "edge_pixels": edge_count,
        "edge_fringe_fraction": round(fringe, 4),
        "opaque_near_key_pixels": opaque_near_key,
        "warnings": warnings,
    }
    return result, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--color", type=str, required=True, help="key color, e.g. '#00ff00'")
    parser.add_argument("--t0", type=float, default=60.0, help="distance below which pixels are fully transparent")
    parser.add_argument("--t1", type=float, default=130.0, help="distance above which pixels are fully opaque")
    parser.add_argument("--scale", type=int, default=1, help="supersampling factor for smoother edges")
    parser.add_argument("--report", type=Path, default=None, help="write the JSON quality report here")
    args = parser.parse_args()

    result, report = key_image(Image.open(args.input), parse_color(args.color), args.t0, args.t1, args.scale)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.out)
    report["output"] = str(args.out)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
