#!/usr/bin/env python3
"""Audit editable SVG reconstruction granularity.

This audit is intentionally about editability, not just render correctness.
It checks whether readable OCR text was lifted into SVG text and whether
raster assets still contain likely-editable labels.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from formula_text_detection import find_formula_text_leaks  # type: ignore


def _norm_text(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _bbox_overlap_ratio(a: dict[str, float], b: dict[str, float]) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(a["x"], b["x"]), max(a["y"], b["y"])
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    return inter / max(1.0, min(a["w"] * a["h"], b["w"] * b["h"]))


def _center_distance(a: dict[str, float], b: dict[str, float]) -> float:
    ax, ay = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    bx, by = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    return math.hypot(ax - bx, ay - by)


def _element_bbox(el: dict[str, Any]) -> dict[str, float] | None:
    if el.get("source_bbox"):
        sb = el["source_bbox"]
        return {"x": float(sb.get("x", 0)), "y": float(sb.get("y", 0)), "w": float(sb.get("w", 0)), "h": float(sb.get("h", 0))}
    if all(k in el for k in ("x", "y", "w", "h")):
        return {"x": float(el["x"]), "y": float(el["y"]), "w": float(el["w"]), "h": float(el["h"])}
    if el.get("type") == "text" and "x" in el and "y" in el:
        text = str(el.get("text") or " ".join(el.get("lines", [])))
        fs = float(el.get("font_size", 16))
        return {"x": float(el["x"]) - len(text) * fs * 0.24, "y": float(el["y"]) - fs, "w": max(1, len(text) * fs * 0.48), "h": fs * 1.3}
    return None


def _is_readable_ocr(item: dict[str, Any]) -> bool:
    text = str(item.get("text", "")).strip()
    bbox = item.get("bbox") or {}
    if len(_norm_text(text)) < 2:
        return False
    if float(item.get("confidence", 0)) < 0.55:
        return False
    if float(bbox.get("h", 0)) < 8:
        return False
    return True


def audit(manifest_path: Path, ocr_path: Path | None = None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = manifest_path.parent
    if ocr_path is None:
        candidate = out_dir / "ocr_results.json"
        ocr_path = candidate if candidate.exists() else None
    ocr_items = []
    if ocr_path and ocr_path.exists():
        ocr_items = json.loads(ocr_path.read_text(encoding="utf-8")).get("items", [])

    elements = manifest.get("elements", [])
    text_elements = [el for el in elements if el.get("type") == "text"]
    math_elements = [el for el in elements if el.get("type") in {"math", "formula"}]
    formula_text_leaks = find_formula_text_leaks(manifest)
    structural_elements = [el for el in elements if el.get("type") in {"rect", "line", "path", "polyline", "polygon", "circle", "ellipse"}]
    image_elements = [el for el in elements if el.get("type") == "image"]
    svg_text_records = []
    for el in text_elements:
        value = str(el.get("text") or " ".join(el.get("lines", []))).strip()
        bbox = _element_bbox(el)
        if value and bbox:
            svg_text_records.append({"text": value, "norm": _norm_text(value), "bbox": bbox, "id": el.get("id")})
    for el in math_elements:
        value = str(el.get("latex") or el.get("text") or "").strip()
        bbox = _element_bbox(el)
        if value and bbox:
            svg_text_records.append({"text": value, "norm": _norm_text(value), "bbox": bbox, "id": el.get("id")})

    readable = [item for item in ocr_items if _is_readable_ocr(item)]
    lifted = []
    missed = []
    for item in readable:
        text_norm = _norm_text(str(item.get("text", "")))
        bbox = item.get("bbox") or {"x": 0, "y": 0, "w": 1, "h": 1}
        match = None
        for svg_text in svg_text_records:
            if text_norm and (text_norm in svg_text["norm"] or svg_text["norm"] in text_norm):
                if _center_distance(bbox, svg_text["bbox"]) <= max(40, bbox.get("w", 1) * 0.8):
                    match = svg_text
                    break
        if match:
            lifted.append({"ocr": item.get("id"), "text": item.get("text"), "element": match["id"]})
        else:
            missed.append({"ocr": item.get("id"), "text": item.get("text"), "bbox": bbox, "confidence": item.get("confidence")})

    asset_regions = []
    for asset in manifest.get("assets", []):
        region = asset.get("source_region") or asset
        asset_regions.append(
            {
                "id": asset.get("id"),
                "bbox": {"x": float(region.get("x", 0)), "y": float(region.get("y", 0)), "w": float(region.get("w", 0)), "h": float(region.get("h", 0))},
                "text_policy": asset.get("text_policy", "review"),
                "kind": asset.get("kind"),
            }
        )

    asset_text_risks = []
    for item in readable:
        bbox = item.get("bbox") or {"x": 0, "y": 0, "w": 1, "h": 1}
        for asset in asset_regions:
            if asset["text_policy"] in {"preserve-raster", "allow-embedded-text"}:
                continue
            if _bbox_overlap_ratio(bbox, asset["bbox"]) >= 0.72:
                if not any(match["ocr"] == item.get("id") for match in lifted):
                    asset_text_risks.append({"asset": asset["id"], "text": item.get("text"), "bbox": bbox, "confidence": item.get("confidence")})
                break

    text_lift_ratio = len(lifted) / len(readable) if readable else None
    risk_status = "ok"
    if text_lift_ratio is not None and text_lift_ratio < 0.45:
        risk_status = "review"
    if len(asset_text_risks) > 12:
        risk_status = "review"
    if formula_text_leaks:
        risk_status = "review"

    return {
        "status": risk_status,
        "readable_ocr_count": len(readable),
        "svg_text_count": len(text_elements),
        "math_element_count": len(math_elements),
        "formula_text_leak_count": len(formula_text_leaks),
        "lifted_text_count": len(lifted),
        "text_lift_ratio": round(text_lift_ratio, 4) if text_lift_ratio is not None else None,
        "structural_element_count": len(structural_elements),
        "image_element_count": len(image_elements),
        "asset_text_risk_count": len(asset_text_risks),
        "missed_text_samples": missed[:40],
        "asset_text_risk_samples": asset_text_risks[:40],
        "formula_text_leak_samples": formula_text_leaks[:40],
    }


def write_report(out_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Editability Audit",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Readable OCR candidates: {result.get('readable_ocr_count')}",
        f"- SVG text elements: {result.get('svg_text_count')}",
        f"- SVG math elements: {result.get('math_element_count')}",
        f"- Formula-like text leaks: {result.get('formula_text_leak_count')}",
        f"- Lifted OCR text count: {result.get('lifted_text_count')}",
        f"- Text lift ratio: {result.get('text_lift_ratio')}",
        f"- Structural SVG elements: {result.get('structural_element_count')}",
        f"- Image elements: {result.get('image_element_count')}",
        f"- Asset text risk count: {result.get('asset_text_risk_count')}",
        "",
        "## Missed Readable Text Samples",
        "",
    ]
    missed = result.get("missed_text_samples", [])
    if not missed:
        lines.append("- None detected.")
    else:
        for item in missed:
            lines.append(f"- `{item.get('text')}` confidence={item.get('confidence')} bbox={item.get('bbox')}")
    lines.extend(["", "## Asset Text Risk Samples", ""])
    risks = result.get("asset_text_risk_samples", [])
    if not risks:
        lines.append("- None detected.")
    else:
        for item in risks:
            lines.append(f"- asset `{item.get('asset')}` contains likely editable text `{item.get('text')}` bbox={item.get('bbox')}")
    lines.extend(["", "## Formula-Like Text Leaks", ""])
    leaks = result.get("formula_text_leak_samples", [])
    if not leaks:
        lines.append("- None detected.")
    else:
        for item in leaks:
            reasons = ", ".join(item.get("reasons", []))
            lines.append(f"- Element `{item.get('id')}` contains `{item.get('text')}` reasons={reasons}")
    (out_dir / "editability_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--ocr", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest, args.ocr)
    write_report(args.manifest.parent, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
