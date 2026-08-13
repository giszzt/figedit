#!/usr/bin/env python3
"""Slice a keyed transparent regeneration sheet into individual asset PNGs.

Default mode finds elements by connected components on the alpha channel, so
the sheet does not need a perfectly regular grid — any layout with clear
transparent gutters between elements works. Each element is cropped to its
alpha bounding box plus padding.

Connected components assume "one element = one component". Multi-part icons
whose parts are separated by keyed-out gaps (a terminal window plus detached
refresh arrows, a gavel head plus its base) break that assumption and get cut
into fragments. For those sheets use --cells: the sheet layout was authored,
so the cell boxes are known — each cell is region-cropped and alpha-trimmed,
bypassing component analysis entirely.

Usage:
  python scripts/slice_grid.py sheet.png out_dir --pad 12 --prefix ic
  python scripts/slice_grid.py sheet_raw.png out_dir --color "#00ff00"   # key first, then slice
  python scripts/slice_grid.py sheet.png out_dir --cells cells.json      # slice by known cell boxes

Outputs: out_dir/<prefix>_NN.png (or <id>.png in --cells mode with named
cells), out_dir/<prefix>_contact_sheet.png, and a JSON listing (printed, and
written with --report) with each element's bbox on the sheet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image, ImageDraw


def find_elements(sheet: Image.Image, min_area_fraction: float = 0.0003) -> List[Dict[str, int]]:
    from scipy import ndimage

    alpha = np.asarray(sheet)[:, :, 3]
    mask = alpha > 128
    # Bridge small internal gaps so one element stays one component.
    closed = ndimage.binary_closing(mask, structure=np.ones((5, 5), bool), iterations=2)
    labels, count = ndimage.label(closed, structure=np.ones((3, 3), bool))
    floor = max(64.0, min_area_fraction * mask.shape[0] * mask.shape[1])
    boxes = []
    if count:
        areas = np.bincount(labels.ravel())
        for index, slc in enumerate(ndimage.find_objects(labels), start=1):
            if slc is None:
                continue
            area = int(areas[index])
            if area < floor:
                continue
            y0, x0 = slc[0].start, slc[1].start
            boxes.append({"x": int(x0), "y": int(y0), "w": int(slc[1].stop - x0), "h": int(slc[0].stop - y0), "area": area})
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
    full-size elements are never merged, however close their boxes are.
    Multi-part icons whose parts exceed this asymmetry are out of scope here —
    slice those sheets with --cells instead."""
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


def _save_contact_sheet(items: List[Dict[str, Any]], out_dir: Path, prefix: str) -> Path:
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
    return contact_path


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

    contact_path = _save_contact_sheet(items, out_dir, prefix)
    return {"count": len(items), "elements": items, "contact_sheet": str(contact_path)}


def slice_cells(sheet: Image.Image, cells: Dict[str, Dict[str, int]], out_dir: Path, pad: int = 12, prefix: str = "el") -> Dict[str, Any]:
    """Slice by known cell boxes: crop each cell, trim to its alpha bounding
    box, pad, save. One cell = one output file, whatever the component count —
    this is the rescue path for multi-part icons that connected-component
    slicing would cut into fragments."""
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    arr = np.asarray(sheet)
    for cell_id, box in cells.items():
        cx1 = max(0, int(box["x"]))
        cy1 = max(0, int(box["y"]))
        cx2 = min(sheet.width, int(box["x"] + box["w"]))
        cy2 = min(sheet.height, int(box["y"] + box["h"]))
        cell_alpha = arr[cy1:cy2, cx1:cx2, 3]
        ys, xs = np.where(cell_alpha > 16)
        if len(xs) == 0:
            items.append({"file": None, "id": cell_id, "warning": "cell contains no visible content"})
            continue
        x1 = max(0, cx1 + int(xs.min()) - pad)
        y1 = max(0, cy1 + int(ys.min()) - pad)
        x2 = min(sheet.width, cx1 + int(xs.max()) + 1 + pad)
        y2 = min(sheet.height, cy1 + int(ys.max()) + 1 + pad)
        crop = sheet.crop((x1, y1, x2, y2))
        name = f"{cell_id}.png"
        crop.save(out_dir / name)
        items.append({"file": name, "id": cell_id, "sheet_bbox": {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}, "cell": {"x": cx1, "y": cy1, "w": cx2 - cx1, "h": cy2 - cy1}})

    contact_items = [item for item in items if item.get("file")]
    contact_path = _save_contact_sheet(contact_items, out_dir, prefix)
    return {"count": len(contact_items), "elements": items, "contact_sheet": str(contact_path), "mode": "cells"}


def _load_cells(path: Path) -> Dict[str, Dict[str, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cells: Dict[str, Dict[str, int]] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and {"x", "y", "w", "h"} <= set(value):
                cells[str(key)] = {k: int(value[k]) for k in ("x", "y", "w", "h")}
        return cells
    for idx, item in enumerate(data):
        if not {"x", "y", "w", "h"} <= set(item):
            continue
        cells[str(item.get("id") or f"cell_{idx:02d}")] = {k: int(item[k]) for k in ("x", "y", "w", "h")}
    return cells


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--pad", type=int, default=12)
    parser.add_argument("--prefix", type=str, default="el")
    parser.add_argument("--color", type=str, default=None, help="if the sheet is not keyed yet, key this color first")
    parser.add_argument("--cells", type=Path, default=None, help="cell boxes JSON ({id:{x,y,w,h}} or a list); slice by region-crop + alpha-trim instead of connected components")
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

    if args.cells:
        cells = _load_cells(args.cells)
        if not cells:
            raise SystemExit(f"No usable cell boxes found in {args.cells}")
        result = slice_cells(image.convert("RGBA"), cells, args.out_dir, pad=args.pad, prefix=args.prefix)
    else:
        result = slice_sheet(image.convert("RGBA"), args.out_dir, pad=args.pad, prefix=args.prefix)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
