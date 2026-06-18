#!/usr/bin/env python3
"""OpenCV structural primitive detector for editable SVG reconstruction."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def _bbox_intersects(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (a["x"] + a["w"] < b["x"] or b["x"] + b["w"] < a["x"] or a["y"] + a["h"] < b["y"] or b["y"] + b["h"] < a["y"])


def _line_bbox(line: dict[str, Any]) -> dict[str, float]:
    x1, y1, x2, y2 = line["x1"], line["y1"], line["x2"], line["y2"]
    return {"x": min(x1, x2), "y": min(y1, y2), "w": abs(x2 - x1), "h": abs(y2 - y1)}


def _orientation(x1: float, y1: float, x2: float, y2: float) -> str:
    dx = x2 - x1
    dy = y2 - y1
    if abs(dy) <= max(3, abs(dx) * 0.08):
        return "horizontal"
    if abs(dx) <= max(3, abs(dy) * 0.08):
        return "vertical"
    return "diagonal"


def _mask_ocr_regions(gray: np.ndarray, ocr_items: list[dict[str, Any]]) -> np.ndarray:
    try:
        import cv2  # type: ignore
    except Exception:
        return gray
    masked = gray.copy()
    for item in ocr_items:
        box = item.get("bbox", {})
        x = max(0, int(box.get("x", 0)) - 2)
        y = max(0, int(box.get("y", 0)) - 2)
        w = int(box.get("w", 0)) + 4
        h = int(box.get("h", 0)) + 4
        cv2.rectangle(masked, (x, y), (x + w, y + h), 255, -1)
    return masked


def _detect_with_cv(image_path: Path, ocr_items: list[dict[str, Any]]) -> dict[str, Any]:
    import cv2  # type: ignore

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    masked = _mask_ocr_regions(gray, ocr_items)
    blur = cv2.GaussianBlur(masked, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)

    min_len = max(24, int(min(width, height) * 0.018))
    raw_lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=min_len, maxLineGap=8)
    lines: list[dict[str, Any]] = []
    if raw_lines is not None:
        for idx, item in enumerate(raw_lines[:, 0, :]):
            x1, y1, x2, y2 = [int(v) for v in item]
            length = math.hypot(x2 - x1, y2 - y1)
            if length < min_len:
                continue
            lines.append(
                {
                    "id": f"cv-line-{idx:04d}",
                    "type": "line",
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "length": round(length, 2),
                    "orientation": _orientation(x1, y1, x2, y2),
                    "confidence": 0.72,
                    "detector": "opencv-hough",
                    "review_status": "ok",
                }
            )

    binary = cv2.adaptiveThreshold(masked, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    rectangles: list[dict[str, Any]] = []
    for idx, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < max(500, width * height * 0.00025):
            continue
        if w < 18 or h < 12:
            continue
        bbox = {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}
        if any(_bbox_intersects(bbox, item.get("bbox", {"x": -1, "y": -1, "w": 0, "h": 0})) and area < 5000 for item in ocr_items):
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        rectangles.append(
            {
                "id": f"cv-rect-{idx:04d}",
                "type": "rect",
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
                "vertices": int(len(approx)),
                "confidence": 0.62 if len(approx) == 4 else 0.48,
                "detector": "opencv-contour",
                "review_status": "ok" if len(approx) == 4 else "needs-check",
            }
        )

    arrowheads: list[dict[str, Any]] = []
    for idx, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if area < 25 or area > 3500:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
        if len(approx) != 3:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        arrowheads.append(
            {
                "id": f"cv-arrowhead-{idx:04d}",
                "type": "arrowhead",
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
                "confidence": 0.58,
                "detector": "opencv-contour-triangle",
                "review_status": "needs-check",
            }
        )

    # Mark lines likely to have arrowheads by endpoint proximity.
    for line in lines:
        endpoints = [(line["x1"], line["y1"]), (line["x2"], line["y2"])]
        for ah in arrowheads:
            cx = ah["x"] + ah["w"] / 2
            cy = ah["y"] + ah["h"] / 2
            d0 = math.hypot(endpoints[0][0] - cx, endpoints[0][1] - cy)
            d1 = math.hypot(endpoints[1][0] - cx, endpoints[1][1] - cy)
            if min(d0, d1) <= max(16, max(ah["w"], ah["h"]) * 1.8):
                line["arrow_start" if d0 < d1 else "arrow_end"] = True
                line["confidence"] = max(line["confidence"], 0.78)

    short_by_axis: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for line in lines:
        if line["length"] > 80:
            continue
        if line["orientation"] == "horizontal":
            key = ("h", int(round(line["y1"] / 8)))
        elif line["orientation"] == "vertical":
            key = ("v", int(round(line["x1"] / 8)))
        else:
            continue
        short_by_axis.setdefault(key, []).append(line)
    dashed_groups = []
    for idx, group in enumerate(short_by_axis.values()):
        if len(group) >= 4:
            dashed_groups.append({"id": f"cv-dash-group-{idx:04d}", "line_ids": [g["id"] for g in group], "count": len(group), "confidence": 0.52})
            for g in group:
                g["dasharray"] = "8 5"
                g["review_status"] = "needs-check"

    return {
        "engine": "opencv",
        "status": "ok",
        "canvas": {"width": width, "height": height},
        "lines": lines,
        "rectangles": rectangles,
        "arrowheads": arrowheads,
        "dashed_groups": dashed_groups,
        "counts": {"lines": len(lines), "rectangles": len(rectangles), "arrowheads": len(arrowheads), "dashed_groups": len(dashed_groups)},
    }


def detect_primitives(image_path: Path, ocr_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        import cv2  # noqa: F401
    except Exception as exc:
        return {"engine": "opencv", "status": "disabled", "error": f"OpenCV import failed: {exc}", "lines": [], "rectangles": [], "arrowheads": [], "dashed_groups": []}
    try:
        return _detect_with_cv(image_path, ocr_items or [])
    except Exception as exc:
        return {"engine": "opencv", "status": "failed", "error": repr(exc), "lines": [], "rectangles": [], "arrowheads": [], "dashed_groups": []}


def save_primitives_outputs(image_path: Path, ocr_json: Path, out_json: Path, overlay_path: Path) -> dict[str, Any]:
    ocr_items = []
    if ocr_json.exists():
        ocr_items = json.loads(ocr_json.read_text(encoding="utf-8")).get("items", [])
    result = detect_primitives(image_path, ocr_items)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for rect in result.get("rectangles", []):
        x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
        color = (0, 220, 110, 190) if rect.get("review_status") == "ok" else (255, 160, 0, 180)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=2)
    for line in result.get("lines", []):
        color = (255, 40, 40, 210) if line.get("arrow_end") or line.get("arrow_start") else (40, 90, 255, 180)
        draw.line([line["x1"], line["y1"], line["x2"], line["y2"]], fill=color, width=2)
    for ah in result.get("arrowheads", []):
        x, y, w, h = ah["x"], ah["y"], ah["w"], ah["h"]
        draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 180, 220), width=2)
    image.save(overlay_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--ocr", type=Path, default=Path("ocr_results.json"))
    parser.add_argument("--out", type=Path, default=Path("detected_primitives.json"))
    parser.add_argument("--overlay", type=Path, default=Path("diagnostics/structure_overlay.png"))
    args = parser.parse_args()
    result = save_primitives_outputs(args.image, args.ocr, args.out, args.overlay)
    print(json.dumps({"status": result.get("status"), "counts": result.get("counts", {})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
