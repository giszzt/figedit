#!/usr/bin/env python3
"""Quantify whether a generated clean plate is registered to its source region.

Fixed-aspect backends can silently RECOMPOSE the scene (re-frame, not stretch)
to fill their native canvas. A recomposed plate makes every source-measured
coordinate wrong, and the drift is invisible to a casual glance. This script
turns "does the plate line up?" into numbers: it builds a structure mask from
both images (pixels near a reference structure color — road gray, border
gray, line ink), then brute-force searches scale and offset for the maximum
IoU between the two masks.

A registered plate scores best near scale 1.00 / offset 0. A clearly non-unit
scale or offset means the backend re-framed the scene: reject the plate and
regenerate with the stretch-compensation workflow in
references/image_generation.md (Fixed-Aspect Backends).

Usage:
  python scripts/check_plate_registration.py --source source.png --region 120,80,900,600 \
         --plate plate.png --mask-color "#e0e0e0" --tol 22
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
from PIL import Image

SEARCH_SCALES = np.arange(0.80, 1.3001, 0.025)
OFFSET_LIMIT = 0.18
OFFSET_STEP = 0.02
WORK_SIZE = 320
PASS_SCALE_TOL = 0.03
PASS_OFFSET_TOL = 0.02


def parse_color(text: str) -> Tuple[int, int, int]:
    value = text.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def structure_mask(image: Image.Image, color: Tuple[int, int, int], tol: float) -> np.ndarray:
    arr = np.asarray(image.convert("RGB"), dtype=np.float64)
    dist = np.sqrt(((arr - np.array(color, dtype=np.float64)) ** 2).sum(axis=2))
    return dist <= tol


def _downscale_mask(mask: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = mask.shape
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return mask
    im = Image.fromarray((mask * 255).astype(np.uint8))
    im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    return np.asarray(im) > 96


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = float(np.logical_and(a, b).sum())
    union = float(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def _shift(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(mask)
    h, w = mask.shape
    ys1, ys2 = max(0, dy), min(h, h + dy)
    xs1, xs2 = max(0, dx), min(w, w + dx)
    yt1, yt2 = max(0, -dy), min(h, h - dy)
    xt1, xt2 = max(0, -dx), min(w, w - dx)
    out[ys1:ys2, xs1:xs2] = mask[yt1:yt2, xt1:xt2]
    return out


def register(source_mask: np.ndarray, plate_mask: np.ndarray) -> Dict[str, Any]:
    h, w = source_mask.shape
    plate_im = Image.fromarray((plate_mask * 255).astype(np.uint8))
    offsets_y = [int(round(f * h)) for f in np.arange(-OFFSET_LIMIT, OFFSET_LIMIT + 1e-9, OFFSET_STEP)]
    offsets_x = [int(round(f * w)) for f in np.arange(-OFFSET_LIMIT, OFFSET_LIMIT + 1e-9, OFFSET_STEP)]

    best = {"scale": 1.0, "offset_x": 0, "offset_y": 0, "iou": -1.0}
    for scale in SEARCH_SCALES:
        sw, sh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        scaled = np.asarray(plate_im.resize((sw, sh), Image.BILINEAR)) > 96
        # Center the scaled mask on the source canvas.
        canvas = np.zeros((h, w), dtype=bool)
        oy, ox = (h - sh) // 2, (w - sw) // 2
        ys1, xs1 = max(0, oy), max(0, ox)
        ys2, xs2 = min(h, oy + sh), min(w, ox + sw)
        canvas[ys1:ys2, xs1:xs2] = scaled[ys1 - oy : ys2 - oy, xs1 - ox : xs2 - ox]
        for dy in offsets_y:
            for dx in offsets_x:
                iou = _iou(source_mask, _shift(canvas, dy, dx))
                if iou > best["iou"]:
                    best = {"scale": round(float(scale), 3), "offset_x": dx, "offset_y": dy, "iou": round(iou, 4)}
    best["offset_x_frac"] = round(best["offset_x"] / w, 4)
    best["offset_y_frac"] = round(best["offset_y"] / h, 4)
    return best


def _parse_region(text: str) -> Tuple[int, int, int, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    return x, y, w, h


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="original source image")
    parser.add_argument("--region", type=str, required=True, help="x,y,w,h of the source region the plate covers")
    parser.add_argument("--plate", type=Path, required=True, help="generated plate (any size; it is resized to the region)")
    parser.add_argument("--mask-color", type=str, required=True, help="reference structure color shared by source and plate, e.g. road gray '#e0e0e0'")
    parser.add_argument("--tol", type=float, default=22.0, help="color distance tolerance for the structure mask")
    parser.add_argument("--out", type=Path, default=None, help="write JSON report here")
    args = parser.parse_args()

    x, y, w, h = _parse_region(args.region)
    color = parse_color(args.mask_color)

    source_crop = Image.open(args.source).convert("RGB").crop((x, y, x + w, y + h))
    plate = Image.open(args.plate).convert("RGB").resize((w, h), Image.LANCZOS)

    src_mask = _downscale_mask(structure_mask(source_crop, color, args.tol), WORK_SIZE)
    plate_mask_full = structure_mask(plate, color, args.tol)
    plate_mask = _downscale_mask(plate_mask_full, WORK_SIZE)
    if plate_mask.shape != src_mask.shape:
        plate_mask = np.asarray(Image.fromarray((plate_mask * 255).astype(np.uint8)).resize((src_mask.shape[1], src_mask.shape[0]), Image.BILINEAR)) > 96

    report: Dict[str, Any] = {
        "source_mask_fraction": round(float(src_mask.mean()), 4),
        "plate_mask_fraction": round(float(plate_mask.mean()), 4),
    }
    if src_mask.mean() < 0.002 or plate_mask.mean() < 0.002:
        report["status"] = "unusable-mask"
        report["message"] = "structure mask is nearly empty in the source or the plate; pick a different --mask-color or a larger --tol"
    else:
        best = register(src_mask, plate_mask)
        registered = (
            abs(best["scale"] - 1.0) <= PASS_SCALE_TOL
            and abs(best["offset_x_frac"]) <= PASS_OFFSET_TOL
            and abs(best["offset_y_frac"]) <= PASS_OFFSET_TOL
        )
        report["best"] = best
        report["status"] = "registered" if registered else "recomposed"
        if not registered:
            report["message"] = (
                "best alignment is far from identity (scale {} / offset {},{}): the backend re-framed the scene. "
                "Reject this plate and regenerate with the Fixed-Aspect Backends compensation "
                "(stretch the reference to the backend's native canvas, instruct it to copy the stretched geometry, "
                "then squeeze the result back)."
            ).format(best["scale"], best["offset_x_frac"], best["offset_y_frac"])

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    status = report.get("status")
    verdict = {"registered": "通过，可以用这块底板",
               "recomposed": "不通过，底板被重新取景了，按下面的补偿办法重生成",
               "unusable-mask": "掩膜几乎是空的，换 --mask-color 或调大 --tol"}.get(status, status)
    print(f"配准   {status}    {verdict}")
    best = report.get("best")
    if best:
        print(f"缩放 {best['scale']}   偏移 x{best['offset_x_frac']} y{best['offset_y_frac']}   "
              f"（合格线 缩放≈1.00 偏移≈0）")
    print(f"掩膜占比   源 {report['source_mask_fraction']}   底板 {report['plate_mask_fraction']}")
    if report.get("message"):
        print(f"\n{report['message']}")
    if args.out:
        print(f"\n报告 {args.out}")


if __name__ == "__main__":
    main()
