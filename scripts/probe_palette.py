#!/usr/bin/env python3
"""Pick a safe chroma-key color for regenerating assets from a source figure.

The chosen color must be far from every color that appears in the source
image (or in the given regions), so that keying it out later cannot eat real
content. Candidates are the classic screen colors; the one with the largest
minimum distance to the observed palette wins.

Usage:
  python scripts/probe_palette.py source.png
  python scripts/probe_palette.py source.png --out figure-task/work/chroma_probe.json
  python scripts/probe_palette.py source.png --region 120,80,300,180 --region 500,40,200,200
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

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


def _parse_region(text: str) -> Dict[str, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    return {"x": x, "y": y, "w": w, "h": h}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--region", action="append", default=None, help="x,y,w,h region to probe (repeatable); default whole image")
    parser.add_argument("--out", type=Path, default=None, help="write JSON report here")
    args = parser.parse_args()
    regions = [_parse_region(r) for r in args.region] if args.region else None
    report = probe(Image.open(args.image), regions)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
