#!/usr/bin/env python3
"""Pick safe chroma-key colors for regenerating assets from a source figure.

Two safety checks, matching what chroma_key.py actually removes:

1. Whole-image Euclidean check (always): the chosen color must be far from
   every color that appears in the source image (or in the given regions), so
   the alpha ramp cannot eat real content. Candidates are the classic screen
   colors; the one with the largest minimum distance wins.
2. Per-element hue-collision check (with --boxes): chroma_key.py also removes
   or desaturates any pixel whose *hue direction* matches the key (its global
   hue sweep uses cosine > 0.90), so an element whose own dominant color sits
   on the key's hue axis is silently damaged even when it is Euclidean-far
   from the key. This check finds those elements and plans the minimum number
   of sheets so no element shares a hue with its sheet's key.

`safe: true` from the whole-image check alone only guarantees background
separability. For regeneration sheets, always run with --boxes before the
first generation call.

Usage:
  python scripts/probe_palette.py source.png
  python scripts/probe_palette.py source.png --out figure-task/work/chroma_probe.json
  python scripts/probe_palette.py source.png --region 120,80,300,180 --region 500,40,200,200
  python scripts/probe_palette.py source.png --boxes icon_boxes.json --out sheet_plan.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

CANDIDATES = {
    "green": (0, 255, 0),
    "magenta": (255, 0, 255),
    "cyan": (0, 255, 255),
    "purple": (128, 0, 255),
}

# Pixels closer than this to a candidate count as "collisions" that keying
# would misclassify. Matches the default keying tolerance in chroma_key.py.
NEAR_DISTANCE = 90.0

# Hue-collision threshold for per-element checks. chroma_key.py's global hue
# sweep triggers at cosine 0.90; we plan sheets with a stricter 0.85 to leave
# a safety margin.
HUE_COS_LIMIT = 0.85

# Saturated-pixel definition shared with the drift report in chroma_key.py.
SATURATION_SPREAD = 40
MIN_SATURATED_PIXELS = 30
MIN_CHROMA_NORM = 20.0


def probe(image: Image.Image, regions: List[Dict[str, int]] | None = None) -> Dict[str, Any]:
    rgb = image.convert("RGB")
    if regions:
        parts = []
        for r in regions:
            parts.append(np.asarray(rgb.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])), dtype=np.float64).reshape(-1, 3))
        pixels = np.concatenate(parts)
    else:
        # Downsample for speed; palette coverage matters, not pixel count.
        thumb = rgb.copy()
        thumb.thumbnail((512, 512))
        pixels = np.asarray(thumb, dtype=np.float64).reshape(-1, 3)

    report: Dict[str, Any] = {"candidates": {}}
    best_name, best_min = None, -1.0
    for name, color in CANDIDATES.items():
        dist = np.sqrt(((pixels - np.array(color, dtype=np.float64)) ** 2).sum(axis=1))
        min_dist = float(dist.min())
        near_fraction = float((dist < NEAR_DISTANCE).mean())
        report["candidates"][name] = {
            "rgb": list(color),
            "hex": "#{:02x}{:02x}{:02x}".format(*color),
            "min_distance": round(min_dist, 1),
            "near_fraction": round(near_fraction, 6),
        }
        if min_dist > best_min:
            best_name, best_min = name, min_dist

    chosen = report["candidates"][best_name]
    report["recommended"] = {"name": best_name, **chosen}
    report["safe"] = bool(chosen["near_fraction"] == 0.0 and chosen["min_distance"] >= NEAR_DISTANCE)
    if not report["safe"]:
        report["warning"] = (
            "No candidate is fully clear of the observed palette; keying may clip "
            "content near the key color. Review the regenerated sheet carefully or "
            "restrict probing to the asset regions."
        )
    return report


def _dominant_saturated_color(pixels: np.ndarray) -> np.ndarray | None:
    """Dominant color among saturated pixels, or None when the region is
    effectively grayscale (no hue to collide with)."""
    spread = pixels.max(axis=1) - pixels.min(axis=1)
    saturated = pixels[spread > SATURATION_SPREAD]
    if len(saturated) < MIN_SATURATED_PIXELS:
        return None
    quantized = (saturated // 32) * 32
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    return colors[int(np.argmax(counts))].astype(np.float64)


def _hue_cos(color: np.ndarray, key: Tuple[int, int, int]) -> float:
    """Cosine between the chroma (hue-direction) vectors of a color and a key.
    Mirrors the chroma-space test in chroma_key.py's global hue sweep."""
    c = color - color.mean()
    k = np.array(key, dtype=np.float64)
    k = k - k.mean()
    cn = float(np.sqrt((c ** 2).sum()))
    kn = float(np.sqrt((k ** 2).sum()))
    if cn < MIN_CHROMA_NORM or kn < 1e-6:
        return 0.0
    return float((c @ k) / (cn * kn))


def plan_sheets(image: Image.Image, boxes: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Partition elements into the minimum number of sheets so that no element's
    dominant hue collides with its sheet's key color."""
    rgb = image.convert("RGB")
    element_cos: Dict[str, Dict[str, float]] = {}
    dominants: Dict[str, List[int] | None] = {}

    for element_id, box in boxes.items():
        crop = rgb.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
        pixels = np.asarray(crop, dtype=np.float64).reshape(-1, 3)
        dominant = _dominant_saturated_color(pixels)
        dominants[element_id] = [int(v) for v in dominant] if dominant is not None else None
        element_cos[element_id] = {}
        if dominant is not None:
            for name, key in CANDIDATES.items():
                element_cos[element_id][name] = round(_hue_cos(dominant, key), 4)

    def colliding(name: str) -> List[str]:
        return [eid for eid, cosmap in element_cos.items() if cosmap.get(name, 0.0) > HUE_COS_LIMIT]

    # Single sheet if any candidate collides with nothing.
    order = list(CANDIDATES.keys())
    clean_keys = [name for name in order if not colliding(name)]
    if clean_keys:
        name = clean_keys[0]
        sheets = [{"name": name, "key": "#{:02x}{:02x}{:02x}".format(*CANDIDATES[name]), "assets": sorted(boxes.keys())}]
    else:
        # Primary sheet: the key with the fewest collisions; every colliding
        # element moves to the first candidate it does not collide with.
        primary = min(order, key=lambda n: len(colliding(n)))
        moved: Dict[str, List[str]] = {}
        unresolvable: List[str] = []
        primary_assets = []
        for eid in sorted(boxes.keys()):
            if element_cos[eid].get(primary, 0.0) <= HUE_COS_LIMIT:
                primary_assets.append(eid)
                continue
            alternates = [n for n in order if n != primary and element_cos[eid].get(n, 0.0) <= HUE_COS_LIMIT]
            if alternates:
                moved.setdefault(alternates[0], []).append(eid)
            else:
                unresolvable.append(eid)
        sheets = [{"name": primary, "key": "#{:02x}{:02x}{:02x}".format(*CANDIDATES[primary]), "assets": primary_assets}]
        for name, assets in moved.items():
            sheets.append({"name": name, "key": "#{:02x}{:02x}{:02x}".format(*CANDIDATES[name]), "assets": assets})
        if unresolvable:
            least_bad = min(order, key=lambda n: max(element_cos[eid].get(n, 0.0) for eid in unresolvable))
            sheets.append({
                "name": least_bad,
                "key": "#{:02x}{:02x}{:02x}".format(*CANDIDATES[least_bad]),
                "assets": unresolvable,
                "warning": "these elements collide with every candidate key; expect drift, review component_hue_drift closely",
            })

    collisions = {
        eid: {"dominant": dominants[eid], "cos": cosmap}
        for eid, cosmap in element_cos.items()
        if any(v > HUE_COS_LIMIT for v in cosmap.values())
    }
    return {"sheets": sheets, "collisions": collisions, "hue_cos_limit": HUE_COS_LIMIT}


def _parse_region(text: str) -> Dict[str, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    return {"x": x, "y": y, "w": w, "h": h}


def _load_boxes(path: Path) -> Dict[str, Dict[str, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    boxes: Dict[str, Dict[str, int]] = {}
    if isinstance(data, dict):
        items = data.get("elements") if isinstance(data.get("elements"), list) else None
        if items is None:
            for key, value in data.items():
                if isinstance(value, dict) and {"x", "y", "w", "h"} <= set(value):
                    boxes[str(key)] = {k: int(value[k]) for k in ("x", "y", "w", "h")}
            return boxes
        data = items
    for idx, item in enumerate(data):
        box = item.get("source_region") if isinstance(item.get("source_region"), dict) else item
        if not {"x", "y", "w", "h"} <= set(box):
            continue
        boxes[str(item.get("id") or f"el_{idx:02d}")] = {k: int(box[k]) for k in ("x", "y", "w", "h")}
    return boxes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--region", action="append", default=None, help="x,y,w,h region to probe (repeatable); default whole image")
    parser.add_argument("--boxes", type=Path, default=None, help="per-element boxes JSON ({id:{x,y,w,h}} or a list of boxes); enables the hue-collision check and sheet partition")
    parser.add_argument("--out", type=Path, default=None, help="write JSON report here")
    args = parser.parse_args()
    regions = [_parse_region(r) for r in args.region] if args.region else None
    image = Image.open(args.image)
    report = probe(image, regions)
    if args.boxes:
        boxes = _load_boxes(args.boxes)
        if not boxes:
            raise SystemExit(f"No usable boxes found in {args.boxes}")
        report["sheet_plan"] = plan_sheets(image, boxes)
        if report["sheet_plan"]["collisions"]:
            report["safe"] = False
            report["warning"] = (
                "Some elements share a hue direction with a candidate key; use the "
                "sheet partition in sheet_plan (one key per sheet) so no element "
                "collides with its own sheet's key."
            )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
