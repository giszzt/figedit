#!/usr/bin/env python3
"""Validate basic reconstruction manifest structure and coordinate bounds.

Usage:
  python scripts/validate_manifest.py manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


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
    width = float(canvas.get("width", 0))
    height = float(canvas.get("height", 0))
    if width <= 0 or height <= 0:
        error("Canvas width/height must be positive.")
        ok = False

    ids = set()
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
        x = float(asset.get("x", 0))
        y = float(asset.get("y", 0))
        w = float(asset.get("w", 0))
        h = float(asset.get("h", 0))
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

    for optional_object in ["style_tokens", "diagnostics", "quality_gates"]:
        if optional_object in manifest and not isinstance(manifest[optional_object], dict):
            error(f"{optional_object} must be an object when present.")
            ok = False

    if ok:
        print("Manifest validation passed.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
