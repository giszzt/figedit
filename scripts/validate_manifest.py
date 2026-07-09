#!/usr/bin/env python3
"""Validate basic reconstruction manifest structure and route-specific invariants.

Usage:
  python scripts/validate_manifest.py manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_background_plan(manifest: dict[str, Any], width: float, height: float) -> bool:
    """Validate only the minimal AI clean-plate contract.

    Conventional FigEdit manifests should not include background_plan. When the
    field is present, it exists only for the ai-clean-plate route.
    """

    plan = manifest.get("background_plan")
    if plan is None:
        return True
    if not isinstance(plan, dict):
        error("background_plan must be an object when present.")
        return False

    ok = True
    strategy = plan.get("strategy")
    if strategy != "ai-clean-plate":
        error("background_plan is only for strategy 'ai-clean-plate'. Conventional routes should omit background_plan.")
        ok = False

    route_decision = plan.get("route_decision")
    if not isinstance(route_decision, dict):
        error("ai-clean-plate requires background_plan.route_decision.")
        ok = False
    else:
        reason = route_decision.get("reason") or route_decision.get("notes")
        if not _nonempty(reason):
            error("background_plan.route_decision must explain why crop + SVG cannot reconstruct the background.")
            ok = False

    plate_asset_id = plan.get("plate_asset_id")
    if not _nonempty(plate_asset_id):
        error("ai-clean-plate requires background_plan.plate_asset_id.")
        ok = False
        plate_asset = None
    else:
        plate_asset = next((asset for asset in manifest.get("assets", []) if asset.get("id") == plate_asset_id), None)
        if not isinstance(plate_asset, dict):
            error("background_plan.plate_asset_id must reference an asset.")
            ok = False

    if isinstance(plate_asset, dict):
        if not _nonempty(plate_asset.get("file")):
            error("ai-clean-plate plate asset must declare a file.")
            ok = False
        if plate_asset.get("kind") != "background-plate":
            error("ai-clean-plate plate asset should use kind='background-plate'.")
            ok = False
        px = _num(plate_asset.get("x"))
        py = _num(plate_asset.get("y"))
        pw = _num(plate_asset.get("w"))
        ph = _num(plate_asset.get("h"))
        if abs(px) > 1 or abs(py) > 1 or abs(pw - width) > max(1.0, width * 0.01) or abs(ph - height) > max(1.0, height * 0.01):
            error("ai-clean-plate plate asset should align to the full canvas.")
            ok = False

    provenance = plan.get("generation_provenance")
    if not isinstance(provenance, dict):
        error("ai-clean-plate requires background_plan.generation_provenance.")
        ok = False
    else:
        if not _nonempty(provenance.get("backend")) and not _nonempty(provenance.get("tool")) and not _nonempty(provenance.get("skill")):
            error("generation_provenance must name the backend, tool, or skill used.")
            ok = False
        if not _nonempty(provenance.get("output")):
            error("generation_provenance.output must point to the accepted clean plate.")
            ok = False
        if _nonempty(plate_asset.get("file") if isinstance(plate_asset, dict) else None) and _nonempty(provenance.get("output")):
            plate_name = Path(str(plate_asset.get("file"))).name.lower() if isinstance(plate_asset, dict) else ""
            output_name = Path(str(provenance.get("output"))).name.lower()
            if plate_name and output_name and plate_name != output_name:
                # The composer may later copy the generated plate into the out/assets
                # folder, but the manifest should not obscure which generated bitmap
                # was accepted. Treat a basename mismatch as an error because it often
                # indicates a stale or unrelated plate asset.
                error("plate asset file basename must match generation_provenance.output basename.")
                ok = False

    review = plan.get("candidate_review")
    if not isinstance(review, dict):
        error("ai-clean-plate requires background_plan.candidate_review.")
        ok = False
    elif review.get("accepted") is not True:
        error("ai-clean-plate candidate_review.accepted must be true for a deliverable manifest.")
        ok = False

    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    ok = True

    for key in ["project", "source_image", "canvas", "classification", "assets", "elements"]:
        if key not in manifest:
            error(f"Missing required key: {key}")
            ok = False

    canvas = manifest.get("canvas", {})
    width = _num(canvas.get("width"))
    height = _num(canvas.get("height"))
    if width <= 0 or height <= 0:
        error("Canvas width/height must be positive.")
        ok = False

    ids: set[str] = set()
    for group_name in ["panels", "assets", "elements"]:
        for item in manifest.get(group_name, []):
            item_id = item.get("id")
            if item_id:
                if item_id in ids:
                    error(f"Duplicate id: {item_id}")
                    ok = False
                ids.add(item_id)

    for asset in manifest.get("assets", []):
        for k in ["x", "y", "w", "h"]:
            if k not in asset:
                error(f"Asset {asset.get('id')} missing {k}")
                ok = False
        x = _num(asset.get("x"))
        y = _num(asset.get("y"))
        w = _num(asset.get("w"))
        h = _num(asset.get("h"))
        if w <= 0 or h <= 0:
            error(f"Asset {asset.get('id')} has non-positive size.")
            ok = False
        if x > width or y > height or x + w < 0 or y + h < 0:
            error(f"Asset {asset.get('id')} is outside canvas.")
            ok = False
        source_region = asset.get("source_region")
        if source_region:
            for k in ["x", "y", "w", "h"]:
                if k not in source_region:
                    error(f"Asset {asset.get('id')} source_region missing {k}")
                    ok = False
        if "edge_check" in asset and not isinstance(asset["edge_check"], dict):
            error(f"Asset {asset.get('id')} edge_check must be an object.")
            ok = False
        source_mode = asset.get("source_mode")
        if source_mode and source_mode not in {"source-crop", "external", "generated", "embedded", "manual"}:
            error(f"Asset {asset.get('id')} has unsupported source_mode: {source_mode}")
            ok = False

    for element in manifest.get("elements", []):
        typ = element.get("type")
        if typ == "image":
            href = element.get("href")
            asset_id = element.get("asset_id")
            if not href and not asset_id:
                error(f"Image element {element.get('id')} missing href or asset_id.")
                ok = False
        if "confidence" in element:
            try:
                confidence = float(element["confidence"])
                if confidence < 0 or confidence > 1:
                    error(f"Element {element.get('id')} confidence must be between 0 and 1.")
                    ok = False
            except Exception:
                error(f"Element {element.get('id')} confidence must be numeric.")
                ok = False
        source_bbox = element.get("source_bbox")
        if source_bbox:
            for k in ["x", "y", "w", "h"]:
                if k not in source_bbox:
                    error(f"Element {element.get('id')} source_bbox missing {k}")
                    ok = False

    for optional_object in ["style_tokens", "diagnostics", "quality_gates", "recognition_summary", "asset_decision_policy"]:
        if optional_object in manifest and not isinstance(manifest[optional_object], dict):
            error(f"{optional_object} must be an object when present.")
            ok = False

    if not _validate_background_plan(manifest, width, height):
        ok = False

    if ok:
        print("Manifest validation passed.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
