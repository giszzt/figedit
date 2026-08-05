#!/usr/bin/env python3
"""Create 1:1 exception sheets and measurements for selected image regions."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _load_boxes(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("boxes"), list):
        boxes = data["boxes"]
    elif isinstance(data, dict) and all(isinstance(value, dict) for value in data.values()):
        # Reuse common FigEdit maps such as {"asset-id": {x, y, w, h}}
        # instead of requiring a one-off conversion script.
        boxes = [{"id": key, **value} for key, value in data.items()]
    else:
        boxes = data
    if not isinstance(boxes, list):
        raise ValueError("boxes JSON must be an array or an object with a boxes array")
    return [box for box in boxes if isinstance(box, dict)]


def _measure(crop: Image.Image) -> dict[str, Any]:
    arr = np.asarray(crop.convert("RGB"), dtype=np.int16)
    if arr.size == 0:
        return {"tight_bbox": None, "dominant_color": None, "non_background_ratio": 0.0}
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0)
    quantized = (border // 16) * 16
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    mode_idx = int(np.argmax(counts))
    bucket = colors[mode_idx]
    selected = (quantized == bucket).all(axis=1)
    dominant = border[selected].mean(axis=0)
    distance = np.sqrt(((arr.astype(float) - dominant.astype(float)) ** 2).sum(axis=2))
    ink = distance > 40.0
    ys, xs = np.where(ink)
    tight = None if len(xs) == 0 else [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
    return {
        "tight_bbox": tight,
        "dominant_color": "#{:02x}{:02x}{:02x}".format(*[int(value) for value in dominant]),
        "border_dominant_share": round(float(counts[mode_idx]) / float(len(quantized)), 4),
        "non_background_ratio": round(float(ink.mean()), 4),
        "edge_ink_occupancy": {
            "top": round(float(ink[0].mean()), 4),
            "bottom": round(float(ink[-1].mean()), 4),
            "left": round(float(ink[:, 0].mean()), 4),
            "right": round(float(ink[:, -1].mean()), 4),
        },
    }


def _sheet_page(items: list[dict[str, Any]], page_path: Path) -> None:
    label_h = 32
    gap = 12
    columns = 2 if len(items) > 1 else 1
    rows = math.ceil(len(items) / columns)
    col_widths = []
    for col in range(columns):
        col_widths.append(max((item["image"].width for item in items[col::columns]), default=1))
    row_heights = []
    for row in range(rows):
        row_items = items[row * columns : (row + 1) * columns]
        row_heights.append(max((item["image"].height + label_h for item in row_items), default=1))
    width = sum(col_widths) + gap * (columns + 1)
    height = sum(row_heights) + gap * (rows + 1)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    y = gap
    for row in range(rows):
        x = gap
        for col in range(columns):
            index = row * columns + col
            if index >= len(items):
                break
            item = items[index]
            label = f"{item['id']}  [{item['x']},{item['y']},{item['w']},{item['h']}]  scale={item['scale']:g}x"
            draw.text((x, y + 8), label, fill="black", font=font)
            sheet.paste(item["image"], (x, y + label_h))
            draw.rectangle(
                [x, y + label_h, x + item["image"].width - 1, y + label_h + item["image"].height - 1],
                outline="#d00000",
                width=2,
            )
            x += col_widths[col] + gap
        y += row_heights[row] + gap
    page_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(page_path)


def inspect(image_path: Path, boxes_path: Path, out_path: Path, report_path: Path) -> dict[str, Any]:
    source = Image.open(image_path).convert("RGB")
    boxes = _load_boxes(boxes_path)
    if not boxes:
        raise ValueError("no exception boxes were provided")
    prepared: list[dict[str, Any]] = []
    report_items: list[dict[str, Any]] = []
    for index, box in enumerate(boxes, start=1):
        x = max(0, int(round(float(box.get("x", 0)))))
        y = max(0, int(round(float(box.get("y", 0)))))
        w = max(1, int(round(float(box.get("w", 1)))))
        h = max(1, int(round(float(box.get("h", 1)))))
        x2, y2 = min(source.width, x + w), min(source.height, y + h)
        if x2 <= x or y2 <= y:
            continue
        scale = max(1.0, float(box.get("scale", 1)))
        crop = source.crop((x, y, x2, y2))
        shown = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.Resampling.NEAREST if scale >= 3 else Image.Resampling.LANCZOS)
        item_id = str(box.get("id") or f"exception-{index}")
        measured = _measure(crop)
        prepared.append({"id": item_id, "x": x, "y": y, "w": x2 - x, "h": y2 - y, "scale": scale, "image": shown})
        report_items.append({"id": item_id, "source_region": {"x": x, "y": y, "w": x2 - x, "h": y2 - y}, "scale": scale, **measured})

    outputs: list[str] = []
    for page_index in range(0, len(prepared), 6):
        page_items = prepared[page_index : page_index + 6]
        if len(prepared) <= 6:
            page = out_path
        else:
            page = out_path.with_name(f"{out_path.stem}-{page_index // 6 + 1}{out_path.suffix or '.png'}")
        _sheet_page(page_items, page)
        outputs.append(str(page))
    report = {"source": str(image_path), "outputs": outputs, "count": len(report_items), "items": report_items}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--boxes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.image.resolve(), args.boxes.resolve(), args.out.resolve(), args.report.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
