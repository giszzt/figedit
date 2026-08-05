#!/usr/bin/env python3
"""Prepare removal-mask diagnostics for AI clean-plate generation.

This script reads one regional `background_plans[].removal_regions` entry (or
the legacy `background_plan.removal_regions`) from a FigEdit manifest and
writes only:

- `background_mask.png`
- `background_mask_overlay.png`
- `background_preparation.json`

It never repairs pixels, paints a plate, runs local inpainting, or creates a
background image that can be used as `plate_asset_id`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def _resolve_source(manifest_path: Path, source_value: str) -> Path:
    source = Path(source_value)
    if not source.exists():
        source = (manifest_path.parent / source_value).resolve()
    if not source.exists():
        raise FileNotFoundError(f"source_image not found: {source_value}")
    return source


def _draw_region(draw: ImageDraw.ImageDraw, region: dict[str, Any], fill: int) -> None:
    shape = region.get("shape", "rect")
    pad = int(round(float(region.get("pad", 0))))
    if shape == "polygon":
        points = region.get("points") or []
        if len(points) < 3:
            raise ValueError(f"Polygon removal region needs at least 3 points: {region.get('id')}")
        draw.polygon([(float(p[0]), float(p[1])) for p in points], fill=fill)
        return
    x = float(region["x"]) - pad
    y = float(region["y"]) - pad
    w = float(region["w"]) + 2 * pad
    h = float(region["h"]) + 2 * pad
    draw.rectangle([x, y, x + w, y + h], fill=fill)


def _select_plan(manifest: dict[str, Any], scope_id: str | None) -> dict[str, Any]:
    plans = manifest.get("background_plans")
    if isinstance(plans, list):
        candidates = [plan for plan in plans if isinstance(plan, dict) and plan.get("strategy") == "ai-clean-plate"]
        if scope_id:
            plan = next((item for item in candidates if item.get("scope_id") == scope_id), None)
            if plan is None:
                raise ValueError(f"No AI background plan found for scope_id={scope_id}")
            return plan
        if len(candidates) != 1:
            raise ValueError("Manifest has multiple AI background plans; pass --scope with a scope_id.")
        return candidates[0]
    legacy = manifest.get("background_plan")
    if isinstance(legacy, dict):
        return legacy
    raise ValueError("No AI background plan found.")


def prepare(manifest_path: Path, out_dir: Path, scope_id: str | None = None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = _select_plan(manifest, scope_id)
    regions = plan.get("removal_regions") or []
    if not regions:
        raise ValueError("Selected background plan removal_regions is empty.")

    source_path = _resolve_source(manifest_path, manifest["source_image"])
    source = Image.open(source_path).convert("RGB")
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    for region in regions:
        if region.get("intent") != "protect":
            _draw_region(draw, region, 255)
    for region in regions:
        if region.get("intent") == "protect":
            _draw_region(draw, region, 0)

    out_dir.mkdir(parents=True, exist_ok=True)
    mask_path = out_dir / "background_mask.png"
    mask.save(mask_path)

    overlay = source.convert("RGBA")
    tint = Image.new("RGBA", source.size, (255, 0, 80, 0))
    tint.putalpha(mask.point(lambda value: 120 if value else 0))
    overlay.alpha_composite(tint)
    overlay_path = out_dir / "background_mask_overlay.png"
    overlay.save(overlay_path)

    result: dict[str, Any] = {
        "source": str(source_path),
        "mask": str(mask_path),
        "overlay": str(overlay_path),
        "region_count": len(regions),
        "coordinate_policy": plan.get("coordinate_policy", "layout-locked"),
        "strategy": plan.get("strategy"),
        "scope_id": plan.get("scope_id"),
        "source_region": plan.get("source_region"),
        "plate_generation": {
            "status": "not-run",
            "reason": "mask diagnostics only; invoke image_gen/image-gen for the clean plate",
        },
    }

    report_path = out_dir / "background_preparation.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scope", help="background_plans[].scope_id; required when more than one AI scope exists")
    args = parser.parse_args()
    result = prepare(args.manifest.resolve(), args.out.resolve(), args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
