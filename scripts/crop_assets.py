#!/usr/bin/env python3
"""Crop raster assets from a source image according to a reconstruction manifest.

Usage:
  python scripts/crop_assets.py manifest.json --out figure-task/out
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple
import shutil

from PIL import Image, ImageDraw, ImageFont


def _box(asset: Dict[str, Any]) -> Tuple[int, int, int, int]:
    region = asset.get("source_region") or asset
    x = int(round(region["x"]))
    y = int(round(region["y"]))
    w = int(round(region["w"]))
    h = int(round(region["h"]))
    pad = int(round(asset.get("pad", 0)))
    return x - pad, y - pad, x + w + pad, y + h + pad


def _clamp(box: Tuple[int, int, int, int], width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    return max(0, x1), max(0, y1), min(width, x2), min(height, y2)


def _edge_check(
    crop: Image.Image,
    source: Image.Image | None = None,
    box: Tuple[int, int, int, int] | None = None,
) -> Dict[str, Any]:
    import numpy as np

    arr = np.asarray(crop.convert("L"))
    if arr.size == 0:
        return {"status": "empty", "edge_density": 1.0}
    band = max(1, min(3, arr.shape[0] // 8 or 1, arr.shape[1] // 8 or 1))
    center = arr[max(0, arr.shape[0] // 4) : max(1, arr.shape[0] * 3 // 4), max(0, arr.shape[1] // 4) : max(1, arr.shape[1] * 3 // 4)]
    bg = float(np.median(center)) if center.size else float(np.median(arr))
    sides = {
        "top": arr[:band, :],
        "bottom": arr[-band:, :],
        "left": arr[:, :band],
        "right": arr[:, -band:],
    }
    side_density = {
        side: float(np.mean(np.abs(values.astype(float) - bg) > 30)) if values.size else 0.0
        for side, values in sides.items()
    }
    border = np.concatenate([values.reshape(-1) for values in sides.values() if values.size])
    density = float(np.mean(np.abs(border.astype(float) - bg) > 30)) if border.size else 0.0
    needs_padding = [side for side, value in side_density.items() if value >= 0.24]
    continuation: Dict[str, float] = {}
    continuation_risk: list[str] = []
    if source is not None and box is not None:
        src = np.asarray(source.convert("L"))
        x1, y1, x2, y2 = box
        checks = {
            "top": (
                src[max(0, y1) : min(src.shape[0], y1 + band), max(0, x1) : min(src.shape[1], x2)],
                src[max(0, y1 - band) : max(0, y1), max(0, x1) : min(src.shape[1], x2)],
            ),
            "bottom": (
                src[max(0, y2 - band) : min(src.shape[0], y2), max(0, x1) : min(src.shape[1], x2)],
                src[min(src.shape[0], y2) : min(src.shape[0], y2 + band), max(0, x1) : min(src.shape[1], x2)],
            ),
            "left": (
                src[max(0, y1) : min(src.shape[0], y2), max(0, x1) : min(src.shape[1], x1 + band)],
                src[max(0, y1) : min(src.shape[0], y2), max(0, x1 - band) : max(0, x1)],
            ),
            "right": (
                src[max(0, y1) : min(src.shape[0], y2), max(0, x2 - band) : min(src.shape[1], x2)],
                src[max(0, y1) : min(src.shape[0], y2), min(src.shape[1], x2) : min(src.shape[1], x2 + band)],
            ),
        }
        for side, (inside, outside) in checks.items():
            if inside.size == 0 or outside.size == 0 or inside.shape != outside.shape:
                continue
            ratio = float(np.mean(np.abs(inside.astype(float) - outside.astype(float)) <= 18))
            continuation[side] = round(ratio, 4)
            if ratio >= 0.72:
                continuation_risk.append(side)
    return {
        "status": "ok" if not needs_padding else "needs-padding",
        "edge_density": round(density, 4),
        "edge_density_by_side": {side: round(value, 4) for side, value in side_density.items()},
        "needs_padding_sides": needs_padding,
        "continuation_risk_sides": continuation_risk,
        "continuation_by_side": continuation,
    }


def crop_assets(manifest_path: Path, out_dir: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_path = (manifest_path.parent / manifest["source_image"]).resolve()
    if not source_path.exists():
        source_path = Path(manifest["source_image"]).resolve()
    image = Image.open(source_path).convert("RGBA")
    width, height = image.size

    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    thumbs = []
    for asset in manifest.get("assets", []):
        source_mode = asset.get("source_mode", "source-crop")
        if source_mode == "external":
            rel_file = Path(asset["file"])
            external = rel_file if rel_file.is_absolute() else (manifest_path.parent / rel_file).resolve()
            if not external.exists():
                raise FileNotFoundError(f"External asset not found: {asset['file']}")
            file_path = out_dir / "assets" / rel_file.name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if external.resolve() != file_path.resolve():
                shutil.copy2(external, file_path)
            asset["file"] = f"assets/{file_path.name}"
            asset["edge_check"] = {"status": "ok", "note": "external or generated asset; source crop check not applicable"}
            asset["crop_status"] = "verified"
            asset["padding_applied"] = 0
            thumbs.append((asset.get("id", file_path.stem), file_path, ("external",), ("external",), asset["edge_check"]))
            continue

        raw_box = _box(asset)
        box = _clamp(raw_box, width, height)
        crop = image.crop(box)
        check = _edge_check(crop, image, box)
        if asset.get("edge_policy") == "allow-border-touch":
            check = {"status": "ok", "edge_density": check.get("edge_density"), "note": "border-touch allowed by model-led crop policy"}
        asset["edge_check"] = check
        asset["crop_status"] = "verified" if check["status"] == "ok" else "needs-padding"
        asset["padding_applied"] = asset.get("pad", 0)

        rel_file = Path(asset["file"])
        if rel_file.parts and rel_file.parts[0] == "assets":
            file_path = out_dir / rel_file
        else:
            file_path = assets_dir / rel_file.name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(file_path)

        thumbs.append((asset.get("id", file_path.stem), file_path, raw_box, box, check))

    contact = make_contact_sheet(thumbs)
    contact_path = out_dir / "contact_sheet.png"
    contact.save(contact_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return contact_path


def make_contact_sheet(items, thumb_w=220, thumb_h=160, cols=4) -> Image.Image:
    if not items:
        return Image.new("RGB", (800, 120), "white")

    rows = (len(items) + cols - 1) // cols
    cell_w = thumb_w + 40
    cell_h = thumb_h + 90
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)

    for idx, (asset_id, path, raw_box, box, check) in enumerate(items):
        col = idx % cols
        row = idx // cols
        x = col * cell_w + 20
        y = row * cell_h + 20
        thumb = Image.open(path).convert("RGB")
        thumb.thumbnail((thumb_w, thumb_h))
        sheet.paste(thumb, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline=(180, 180, 180))
        draw.text((x, y + thumb_h + 8), str(asset_id)[:32], fill=(0, 0, 0))
        draw.text((x, y + thumb_h + 28), f"box={box}", fill=(80, 80, 80))
        if raw_box != box:
            draw.text((x, y + thumb_h + 48), f"clamped from {raw_box}", fill=(160, 0, 0))
        draw.text((x, y + thumb_h + 68), f"edge={check.get('status')}", fill=(120, 0, 0) if check.get("status") != "ok" else (0, 100, 0))
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args()
    contact = crop_assets(args.manifest, args.out)
    print(f"Contact sheet written to: {contact}")


if __name__ == "__main__":
    main()
