#!/usr/bin/env python3
"""Slice a keyed transparent regeneration sheet into individual asset PNGs.

Elements are found by connected components on the alpha channel, so the sheet
does not need a perfectly regular grid — any layout with clear transparent
gutters between elements works. Each element is cropped to its alpha bounding
box plus padding.

Usage:
  python scripts/slice_grid.py sheet.png out_dir --pad 12 --prefix ic
  python scripts/slice_grid.py sheet_raw.png out_dir --color "#00ff00"   # key first, then slice

Outputs: out_dir/<prefix>_NN.png, out_dir/<prefix>_contact_sheet.png, and a
JSON listing (printed, and written with --report) with each element's bbox on
the sheet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageDraw


def find_elements(sheet: Image.Image, min_area_fraction: float = 0.0003) -> List[Dict[str, int]]:
    import cv2

    alpha = np.asarray(sheet)[:, :, 3]
    mask = (alpha > 128).astype(np.uint8)
    # Bridge small internal gaps so one element stays one component.
    kernel = np.ones((5, 5), dtype=np.uint8)
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    count, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    floor = max(64.0, min_area_fraction * mask.shape[0] * mask.shape[1])
    boxes = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < floor:
            continue
        boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "area": int(area)})
    boxes = _merge_detached_parts(boxes)
    boxes.sort(key=lambda b: (b["y"] // max(1, sheet.height // 8), b["x"]))
    return boxes


def _gap(a: Dict[str, int], b: Dict[str, int]) -> float:
    gx = max(0, max(a["x"], b["x"]) - min(a["x"] + a["w"], b["x"] + b["w"]))
    gy = max(0, max(a["y"], b["y"]) - min(a["y"] + a["h"], b["y"] + b["h"]))
    return max(gx, gy)


def _merge_detached_parts(boxes: List[Dict[str, int]]) -> List[Dict[str, int]]:
    """One element can have small detached parts (a flame's spark, an
    exclamation mark's dot). Geometry alone cannot distinguish a detached part
    from a neighboring element, but size asymmetry can: absorb a component
    only when it is much smaller than its neighbor and sits close to it. Two
    full-size elements are never merged, however close their boxes are."""
    merged = True
    while merged and len(boxes) > 1:
        merged = False
        for i in range(len(boxes)):
            for j in range(len(boxes)):
                if i == j:
                    continue
                big, small = boxes[i], boxes[j]
                if small["area"] > 0.15 * big["area"]:
                    continue
                threshold = max(8.0, 0.15 * max(big["w"], big["h"]))
                if _gap(big, small) <= threshold:
                    x1, y1 = min(big["x"], small["x"]), min(big["y"], small["y"])
                    x2 = max(big["x"] + big["w"], small["x"] + small["w"])
                    y2 = max(big["y"] + big["h"], small["y"] + small["h"])
                    boxes[i] = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1, "area": big["area"] + small["area"]}
                    boxes.pop(j)
                    merged = True
                    break
            if merged:
                break
    return boxes


def _checkerboard(w: int, h: int, cell: int = 12) -> Image.Image:
    tile = np.zeros((h, w), dtype=np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    tile[((yy // cell) + (xx // cell)) % 2 == 0] = 235
    tile[((yy // cell) + (xx // cell)) % 2 == 1] = 210
    return Image.fromarray(np.dstack([tile] * 3), "RGB")


def slice_sheet(sheet: Image.Image, out_dir: Path, pad: int = 12, prefix: str = "el") -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    boxes = find_elements(sheet)
    items = []
    for idx, box in enumerate(boxes):
        x1 = max(0, box["x"] - pad)
        y1 = max(0, box["y"] - pad)
        x2 = min(sheet.width, box["x"] + box["w"] + pad)
        y2 = min(sheet.height, box["y"] + box["h"] + pad)
        crop = sheet.crop((x1, y1, x2, y2))
        name = f"{prefix}_{idx:02d}.png"
        crop.save(out_dir / name)
        items.append({"file": name, "sheet_bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}, "alpha_bbox": box})

    # Contact sheet on a checkerboard so transparency and cut edges are visible.
    cols = min(4, max(1, len(items)))
    thumb_w, thumb_h = 220, 170
    rows = (len(items) + cols - 1) // cols if items else 1
    cell_w, cell_h = thumb_w + 30, thumb_h + 50
    board = _checkerboard(cols * cell_w, rows * cell_h)
    draw = ImageDraw.Draw(board)
    for idx, item in enumerate(items):
        im = Image.open(out_dir / item["file"])
        im.thumbnail((thumb_w, thumb_h))
        x = (idx % cols) * cell_w + 15
        y = (idx // cols) * cell_h + 10
        board.paste(im, (x, y), im)
        draw.text((x, y + thumb_h + 8), item["file"], fill=(0, 0, 0))
    contact_path = out_dir / f"{prefix}_contact_sheet.png"
    board.save(contact_path)

    return {"count": len(items), "elements": items, "contact_sheet": str(contact_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--pad", type=int, default=12)
    parser.add_argument("--prefix", type=str, default="el")
    parser.add_argument("--color", type=str, default=None, help="if the sheet is not keyed yet, key this color first")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    image = Image.open(args.sheet)
    if args.color:
        from chroma_key import key_image, parse_color

        image, key_report = key_image(image, parse_color(args.color))
        if key_report["warnings"]:
            print(json.dumps({"chroma_key_warnings": key_report["warnings"]}, ensure_ascii=False))
    elif image.mode != "RGBA":
        raise SystemExit("Sheet has no alpha channel; pass --color to key it first.")

    result = slice_sheet(image.convert("RGBA"), args.out_dir, pad=args.pad, prefix=args.prefix)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
