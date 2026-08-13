#!/usr/bin/env python3
"""Turn geometry.json + ocr_results.json into adoptable manifest element drafts.

A large manifest needs hundreds of hand-written JSON objects with exact
coordinates. Drafts close that gap for the two element types that can be
measured mechanically.

  text_slot   -> {"type": "text", ...}  position and string come from OCR and
                 are reliable; font_size and fill are ESTIMATES, meant to be
                 corrected by fit_text.py and the visual compare loop exactly
                 as hand-written values would be.
  fill_region -> {"type": "rect", ...}  outlined boxes carry stroke + fill,
                 solid blobs carry fill only. Check them against the overlay.

Three rules, none of them optional:

  1. Drafts land in their own file. They never touch manifest.json. Adoption
     goes through `manifest_edit.py --adopt`, and adopting means owning them.
  2. Every draft carries `provenance` and `confidence`. The raw_detector_import
     quality gate reads provenance to catch drafts that reached delivery
     without review.
  3. After adopting, run `--stage svg` and look at the visual diff before
     doing anything else. Reading drafts as JSON is slower than writing them;
     looking at one composed image is not.

Drafts are evidence promoted one step, not conclusions. Routing is already
locked by the survey before this script runs, and nothing here may change it.

Usage:
  python scripts/draft_elements.py work/geometry.json --out work/draft_elements.json
  python scripts/draft_elements.py work/geometry.json --out work/draft_elements.json \
      --min-confidence 0.85 --no-rects
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_FONT_FAMILY = "Arial, Helvetica, sans-serif"


def _text_element(slot: dict[str, Any], index: int) -> dict[str, Any]:
    x, y, w, h = slot["bbox"]
    return {
        "type": "text",
        "id": f"draft-text-{index:03d}",
        "layer": "texts",
        "decision": "retype",
        "x": x,
        "y": slot.get("baseline_y_est", int(y + h * 0.8)),
        "text": slot.get("text", ""),
        "font_size": slot.get("font_size_est"),
        "font_family": DEFAULT_FONT_FAMILY,
        "font_weight": "400",
        "fill": slot.get("fill"),
        "text_anchor": "start",
        "source_region": {"x": x, "y": y, "w": w, "h": h},
        "provenance": "draft-ocr",
        "confidence": slot.get("ocr_confidence", 0.0),
        "review_notes": "font_size and fill are estimates; verify against the composed SVG",
    }


def _rect_element(region: dict[str, Any], index: int) -> dict[str, Any]:
    x, y, w, h = region["bbox"]
    element: dict[str, Any] = {
        "type": "rect",
        "id": f"draft-rect-{index:03d}",
        "layer": "panels",
        "decision": "redraw",
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "fill": region.get("color") or "none",
        "provenance": "draft-geometry",
        "confidence": region.get("confidence", 0.0),
    }
    if region.get("stroke"):
        element["stroke"] = region["stroke"]
        element["stroke_width"] = region.get("stroke_width", 1)
    if region.get("corner_radius_est"):
        element["rx"] = region["corner_radius_est"]
    if region.get("parent"):
        element["parent_hint"] = region["parent"]
    return element


def build(geometry: dict[str, Any], min_confidence: float, want_rects: bool, want_text: bool) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    skipped = {"low_confidence": 0, "empty_text": 0}

    if want_rects:
        for index, region in enumerate(geometry.get("fill_regions", [])):
            if region.get("confidence", 0.0) < min_confidence:
                skipped["low_confidence"] += 1
                continue
            elements.append(_rect_element(region, index))

    if want_text:
        for index, slot in enumerate(geometry.get("text_slots", [])):
            if not str(slot.get("text", "")).strip():
                skipped["empty_text"] += 1
                continue
            if slot.get("ocr_confidence", 1.0) < min_confidence:
                skipped["low_confidence"] += 1
                continue
            elements.append(_text_element(slot, index))

    profile = geometry.get("image_profile", {})
    return {
        "source_geometry": geometry.get("source_image"),
        "canvas": geometry.get("canvas"),
        "abstained": profile.get("abstained", False),
        "min_confidence": min_confidence,
        "counts": {
            "rect": sum(1 for e in elements if e["type"] == "rect"),
            "text": sum(1 for e in elements if e["type"] == "text"),
        },
        "skipped": skipped,
        "contract": (
            "Drafts, not elements. Adopt with: python scripts/manifest_edit.py manifest.json "
            "--adopt work/draft_elements.json [--ids ...] [--min-confidence x]. "
            "Adopting means owning. Compose --stage svg and look at the result before continuing."
        ),
        "elements": elements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-confidence", type=float, default=0.60)
    parser.add_argument("--no-rects", action="store_true")
    parser.add_argument("--no-text", action="store_true")
    args = parser.parse_args()

    geometry = json.loads(args.geometry.resolve().read_text(encoding="utf-8"))
    payload = build(geometry, args.min_confidence, not args.no_rects, not args.no_text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {"out": str(args.out), "counts": payload["counts"], "skipped": payload["skipped"],
             "abstained": payload["abstained"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
