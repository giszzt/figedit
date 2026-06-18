#!/usr/bin/env python3
"""One-command editable SVG reconstruction pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_svg_from_manifest import build_svg  # type: ignore
from embed_svg_assets import embed  # type: ignore
from detect_ocr_paddle import save_ocr_outputs  # type: ignore
from detect_primitives_cv import save_primitives_outputs  # type: ignore
from generate_diagnostics import generate_rejected_candidates_overlay  # type: ignore
from infer_assets import crop_assets, infer_assets, make_contact_sheet  # type: ignore
from quality_audit import audit_and_write  # type: ignore
from sample_styles import save_style_outputs  # type: ignore


def _bbox_from_ocr(item: dict[str, Any]) -> dict[str, float]:
    box = item.get("bbox", {})
    return {"x": float(box.get("x", 0)), "y": float(box.get("y", 0)), "w": float(box.get("w", 0)), "h": float(box.get("h", 0))}


def _bbox_overlap_ratio(a: dict[str, float], b: dict[str, float]) -> float:
    ax2 = a["x"] + a["w"]
    ay2 = a["y"] + a["h"]
    bx2 = b["x"] + b["w"]
    by2 = b["y"] + b["h"]
    ix1 = max(a["x"], b["x"])
    iy1 = max(a["y"], b["y"])
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    return inter / max(1.0, a["w"] * a["h"])


def _line_source_bbox(line: dict[str, Any]) -> dict[str, float]:
    return {
        "x": float(min(line.get("x1", 0), line.get("x2", 0))),
        "y": float(min(line.get("y1", 0), line.get("y2", 0))),
        "w": float(max(1, abs(line.get("x2", 0) - line.get("x1", 0)))),
        "h": float(max(1, abs(line.get("y2", 0) - line.get("y1", 0)))),
    }


def _inside_asset(bbox: dict[str, float], asset_regions: list[dict[str, float]], threshold: float) -> bool:
    return any(_bbox_overlap_ratio(bbox, region) >= threshold for region in asset_regions)


def _line_element(line: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "line",
        "id": f"element-{line.get('id')}",
        "source_id": line.get("id"),
        "x1": line.get("x1", 0),
        "y1": line.get("y1", 0),
        "x2": line.get("x2", 0),
        "y2": line.get("y2", 0),
        "stroke": "#111111",
        "stroke_width": 2,
        "dasharray": line.get("dasharray"),
        "arrow_start": bool(line.get("arrow_start")),
        "arrow_end": bool(line.get("arrow_end")),
        "decision": "redraw",
        "detector": line.get("detector", "opencv"),
        "confidence": line.get("confidence", 0.0),
        "review_status": line.get("review_status", "needs-check"),
        "source_bbox": _line_source_bbox(line),
        "decision_reason": "OpenCV line/connector candidate redrawn as editable SVG structure",
    }


def _rect_element(rect: dict[str, Any], style_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    style = style_by_id.get(rect.get("id"), {})
    return {
        "type": "rect",
        "id": f"element-{rect.get('id')}",
        "source_id": rect.get("id"),
        "class": "panel" if rect.get("w", 0) * rect.get("h", 0) > 20000 else "box",
        "x": rect.get("x", 0),
        "y": rect.get("y", 0),
        "w": rect.get("w", 0),
        "h": rect.get("h", 0),
        "fill": "none",
        "stroke": style.get("stroke", "#111111"),
        "stroke_width": style.get("stroke_width", 2),
        "decision": "redraw",
        "detector": rect.get("detector", "opencv"),
        "confidence": rect.get("confidence", 0.0),
        "review_status": rect.get("review_status", "needs-check"),
        "source_bbox": {"x": rect.get("x", 0), "y": rect.get("y", 0), "w": rect.get("w", 0), "h": rect.get("h", 0)},
        "style_source": "sampled" if style else "default",
        "decision_reason": "OpenCV rectangle/frame candidate redrawn as editable SVG structure",
    }


def _text_element(item: dict[str, Any]) -> dict[str, Any]:
    box = _bbox_from_ocr(item)
    fs = max(8, min(42, round(box["h"] * 0.72, 1)))
    return {
        "type": "text",
        "id": f"element-{item.get('id')}",
        "source_id": item.get("id"),
        "x": round(box["x"] + box["w"] / 2, 2),
        "y": round(box["y"] + box["h"] * 0.82, 2),
        "text": item.get("text", ""),
        "font_size": fs,
        "font_weight": "700",
        "font_family": "var(--font-serif)",
        "fill": "#111111",
        "text_anchor": "middle",
        "decision": "retype",
        "detector": "paddleocr",
        "confidence": item.get("confidence", 0.0),
        "review_status": item.get("review_status", "needs-check"),
        "source_bbox": box,
        "decision_reason": "PaddleOCR text candidate retyped as editable SVG text",
    }


def _asset_element(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "image",
        "id": f"element-{asset.get('id')}",
        "asset_id": asset.get("id"),
        "href": asset.get("file"),
        "x": asset.get("x", 0),
        "y": asset.get("y", 0),
        "w": asset.get("w", 0),
        "h": asset.get("h", 0),
        "decision": "embed",
        "detector": "opencv-asset-inference",
        "confidence": asset.get("crop_confidence", 0.0),
        "review_status": "ok" if asset.get("crop_status") == "verified" else "needs-check",
        "source_bbox": asset.get("source_region", {}),
        "decision_reason": "Source-specific visual region preserved as raster asset",
    }


def build_manifest(source_image: Path, out_dir: Path, ocr: dict[str, Any], primitives: dict[str, Any], styles: dict[str, Any], asset_result: dict[str, Any]) -> dict[str, Any]:
    with Image.open(source_image) as im:
        width, height = im.size

    style_by_id = {item.get("element_id"): item for item in styles.get("rect_styles", [])}
    elements: list[dict[str, Any]] = []

    # Assets first so source evidence appears below editable structure/text in SVG.
    assets = asset_result.get("assets", [])
    asset_regions = [
        {
            "x": float(asset.get("x", 0)),
            "y": float(asset.get("y", 0)),
            "w": float(asset.get("w", 0)),
            "h": float(asset.get("h", 0)),
        }
        for asset in assets
        if asset.get("w", 0) and asset.get("h", 0)
    ]
    elements.extend(_asset_element(asset) for asset in assets)

    # Use larger rectangles first; skip tiny noisy detections.
    rects = sorted(primitives.get("rectangles", []), key=lambda r: r.get("w", 0) * r.get("h", 0), reverse=True)
    for rect in rects[:100]:
        if rect.get("w", 0) < 12 or rect.get("h", 0) < 10:
            continue
        rect_bbox = {"x": float(rect.get("x", 0)), "y": float(rect.get("y", 0)), "w": float(rect.get("w", 0)), "h": float(rect.get("h", 0))}
        if _inside_asset(rect_bbox, asset_regions, 0.45):
            continue
        if rect.get("review_status") != "ok" and rect.get("w", 0) * rect.get("h", 0) < 120000:
            continue
        elements.append(_rect_element(rect, style_by_id))

    line_candidates = sorted(
        primitives.get("lines", []),
        key=lambda l: (1 if l.get("arrow_start") or l.get("arrow_end") else 0, l.get("length", 0)),
        reverse=True,
    )
    kept_lines = 0
    for line in line_candidates:
        line_length = float(line.get("length", 0))
        has_arrow = bool(line.get("arrow_start") or line.get("arrow_end"))
        orientation = line.get("orientation")
        if line_length < 70:
            continue
        line_bbox = _line_source_bbox(line)
        if _inside_asset(line_bbox, asset_regions, 0.32):
            continue
        if line.get("dasharray") and line_length < 160:
            continue
        if has_arrow:
            keep = line_length >= 90
        elif orientation in {"horizontal", "vertical"}:
            keep = line_length >= 180
        else:
            keep = False
        if not keep:
            continue
        elements.append(_line_element(line))
        kept_lines += 1
        if kept_lines >= 140:
            break

    for item in ocr.get("items", [])[:500]:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        text_bbox = _bbox_from_ocr(item)
        if _inside_asset(text_bbox, asset_regions, 0.72):
            continue
        elements.append(_text_element(item))

    if not assets and not primitives.get("lines") and not primitives.get("rectangles") and not ocr.get("items"):
        # Explicit fallback: keep the source visible and report that dependencies are needed.
        fallback_asset = {
            "id": "asset-source-fallback",
            "file": "assets/source_fallback.png",
            "x": 0,
            "y": 0,
            "w": width,
            "h": height,
            "source_region": {"x": 0, "y": 0, "w": width, "h": height},
            "kind": "fallback-full-source",
            "decision": "crop",
            "asset_fidelity": "source-preserve",
            "decision_reason": "No OCR/OpenCV detections available; full source retained as explicit fallback",
            "crop_status": "needs-review",
            "edge_check": {"status": "fallback"},
            "padding_applied": 0,
            "neighbor_risk": "none",
        }
        Image.open(source_image).convert("RGB").save(out_dir / fallback_asset["file"])
        assets = [fallback_asset]
        elements.append(_asset_element(fallback_asset))

    return {
        "project": out_dir.name,
        "source_image": str(source_image),
        "canvas": {"width": width, "height": height, "background": styles.get("background", "#ffffff")},
        "classification": {
            "layout_topology": "auto-detected",
            "complexity": "unknown",
            "style_type": "image-derived",
            "reconstruction_mode": "auto-hybrid",
            "reconstruction_intent": "editable structure plus source-preserved visual assets",
            "notes": "Generated by FigEdit using PaddleOCR/OpenCV when available.",
        },
        "assets": assets,
        "elements": elements,
        "style_tokens": styles,
        "diagnostics": {
            "ocr_overlay": "diagnostics/ocr_overlay.png",
            "structure_overlay": "diagnostics/structure_overlay.png",
            "crop_overlay": "diagnostics/crop_overlay.png",
            "style_overlay": "diagnostics/style_overlay.png",
            "rejected_candidates": "diagnostics/rejected_candidates.png",
            "ocr_status": ocr.get("status"),
            "opencv_status": primitives.get("status"),
            "asset_inference_status": asset_result.get("status"),
        },
        "quality_gates": {},
    }


def write_readme(out_dir: Path) -> None:
    text = """# FigEdit output

This package was generated by the automatic reconstruction pipeline.

Key files:

- `editable.svg`: editable SVG using external assets.
- `editable_embedded.svg`: self-contained SVG with embedded assets.
- `preview.png`: browser-rendered preview when Chrome/Edge is available.
- `manifest.json`: enhanced reconstruction manifest.
- `quality_report.md`: automated quality gates and review items.
- `diagnostics/`: OCR, structure, crop, style, and rejected-candidate overlays.
- `assets/`: cropped visual assets.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def reconstruct(image_path: Path, out_dir: Path, lang: str = "ch", gpu: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = out_dir / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    source_copy = assets_dir / f"source{image_path.suffix.lower() or '.png'}"
    shutil.copy2(image_path, source_copy)

    # PaddleOCR/OpenCV can fail on non-ASCII Windows paths. Process the ASCII copy,
    # while preserving the original source path in the manifest for provenance.
    work_image = source_copy

    ocr = save_ocr_outputs(work_image, out_dir / "ocr_results.json", diagnostics / "ocr_overlay.png", lang=lang, use_gpu=gpu)
    primitives = save_primitives_outputs(work_image, out_dir / "ocr_results.json", out_dir / "detected_primitives.json", diagnostics / "structure_overlay.png")
    styles = save_style_outputs(work_image, out_dir / "detected_primitives.json", out_dir / "style_tokens.json", diagnostics / "style_overlay.png")

    asset_result = infer_assets(work_image, ocr.get("items", []), primitives)
    crop_assets(work_image, asset_result.get("assets", []), out_dir)
    make_contact_sheet(out_dir, asset_result.get("assets", []), out_dir / "contact_sheet.png")
    (out_dir / "asset_candidates.json").write_text(json.dumps(asset_result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Crop overlay is generated by the infer_assets module entrypoint; draw it here for the one-command path.
    from infer_assets import save_asset_outputs  # type: ignore

    save_asset_outputs(work_image, out_dir / "ocr_results.json", out_dir / "detected_primitives.json", out_dir / "asset_candidates.json", out_dir, diagnostics / "crop_overlay.png", out_dir / "contact_sheet.png")
    asset_result = json.loads((out_dir / "asset_candidates.json").read_text(encoding="utf-8"))

    manifest = build_manifest(image_path, out_dir, ocr, primitives, styles, asset_result)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    svg = build_svg(manifest)
    (out_dir / "editable.svg").write_text(svg, encoding="utf-8")
    embed(out_dir / "editable.svg", out_dir, out_dir / "editable_embedded.svg")

    generate_rejected_candidates_overlay(work_image, out_dir / "detected_primitives.json", manifest_path, diagnostics / "rejected_candidates.png")
    gates = audit_and_write(out_dir)
    write_readme(out_dir)
    return {"out_dir": str(out_dir), "quality_gates": gates}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    result = reconstruct(args.image.resolve(), args.out.resolve(), lang=args.lang, gpu=args.gpu)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
