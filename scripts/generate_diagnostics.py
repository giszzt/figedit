#!/usr/bin/env python3
"""Generate consolidated diagnostic overlays for reconstruction runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def generate_rejected_candidates_overlay(image_path: Path, primitives_path: Path, manifest_path: Path, out_path: Path) -> None:
    primitives = load_json(primitives_path)
    manifest = load_json(manifest_path)
    used_ids = {el.get("source_id") for el in manifest.get("elements", []) if el.get("source_id")}
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    for line in primitives.get("lines", []):
        if line.get("id") in used_ids:
            continue
        if line.get("length", 0) < 80 and not line.get("arrow_end") and not line.get("arrow_start"):
            continue
        draw.line([line["x1"], line["y1"], line["x2"], line["y2"]], fill=(255, 0, 0, 170), width=2)
    for rect in primitives.get("rectangles", []):
        if rect.get("id") in used_ids:
            continue
        if rect.get("w", 0) * rect.get("h", 0) < 2500:
            continue
        x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
        draw.rectangle([x, y, x + w, y + h], outline=(255, 120, 0, 190), width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--primitives", type=Path, default=Path("detected_primitives.json"))
    parser.add_argument("--manifest", type=Path, default=Path("manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("diagnostics/rejected_candidates.png"))
    args = parser.parse_args()
    generate_rejected_candidates_overlay(args.image, args.primitives, args.manifest, args.out)
    print(f"Diagnostics written to: {args.out}")


if __name__ == "__main__":
    main()
