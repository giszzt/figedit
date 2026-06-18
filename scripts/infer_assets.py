#!/usr/bin/env python3
"""Infer and crop source-preserved visual asset regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def _overlap_ratio(a: dict[str, float], b: dict[str, float]) -> float:
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["w"], b["x"] + b["w"])
    y2 = min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    return inter / max(1.0, min(a["w"] * a["h"], b["w"] * b["h"]))


def _contains(outer: dict[str, float], inner: dict[str, float], margin: float = 6.0) -> bool:
    return (
        inner["x"] >= outer["x"] - margin
        and inner["y"] >= outer["y"] - margin
        and inner["x"] + inner["w"] <= outer["x"] + outer["w"] + margin
        and inner["y"] + inner["h"] <= outer["y"] + outer["h"] + margin
    )


def _gap(a: dict[str, float], b: dict[str, float]) -> tuple[float, float]:
    ax2 = a["x"] + a["w"]
    ay2 = a["y"] + a["h"]
    bx2 = b["x"] + b["w"]
    by2 = b["y"] + b["h"]
    gx = max(0.0, max(a["x"], b["x"]) - min(ax2, bx2))
    gy = max(0.0, max(a["y"], b["y"]) - min(ay2, by2))
    return gx, gy


def _union_box(items: list[dict[str, Any]]) -> dict[str, float]:
    xs = [float(item.get("x", 0)) for item in items]
    ys = [float(item.get("y", 0)) for item in items]
    x2s = [float(item.get("x", 0)) + float(item.get("w", 0)) for item in items]
    y2s = [float(item.get("y", 0)) + float(item.get("h", 0)) for item in items]
    x1, y1, x2, y2 = min(xs), min(ys), max(x2s), max(y2s)
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}


def _merge_nearby_assets(candidates: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for cand in candidates:
        region = cand.get("source_region", cand)
        placed = False
        for group in groups:
            union = _union_box([g.get("source_region", g) for g in group])
            gx, gy = _gap(union, region)
            if gx <= 95 and gy <= 95 and (union["w"] * union["h"]) < width * height * 0.22:
                group.append(cand)
                placed = True
                break
        if not placed:
            groups.append([cand])

    merged: list[dict[str, Any]] = []
    for group in groups:
        if len(group) < 2:
            merged.extend(group)
            continue
        box = _union_box([g.get("source_region", g) for g in group])
        # Slightly expand spatial clusters so leader lines and labels are not clipped.
        pad = 18
        x = max(0.0, box["x"] - pad)
        y = max(0.0, box["y"] - pad)
        x2 = min(float(width), box["x"] + box["w"] + pad)
        y2 = min(float(height), box["y"] + box["h"] + pad)
        merged.append(
            {
                "id": f"asset-cluster-{len(merged):04d}",
                "file": f"assets/asset_cluster_{len(merged):04d}.png",
                "x": x,
                "y": y,
                "w": x2 - x,
                "h": y2 - y,
                "source_region": {"x": x, "y": y, "w": x2 - x, "h": y2 - y},
                "pad": pad,
                "kind": "merged-complex-visual-cluster",
                "decision": "crop",
                "asset_fidelity": "source-preserve",
                "decision_reason": "nearby dense visual candidates merged to avoid fragmented crops and missing panel content",
                "background_handling": "preserve-background",
                "crop_confidence": 0.66,
                "padding_applied": pad,
                "neighbor_risk": "medium",
                "merged_from": [g.get("id") for g in group],
            }
        )
    return merged


def _edge_check(crop: Image.Image) -> dict[str, Any]:
    arr = np.asarray(crop.convert("L"))
    if arr.size == 0:
        return {"status": "empty", "edge_density": 1.0}
    border = np.concatenate([arr[:2, :].reshape(-1), arr[-2:, :].reshape(-1), arr[:, :2].reshape(-1), arr[:, -2:].reshape(-1)])
    center = arr[max(0, arr.shape[0] // 4) : max(1, arr.shape[0] * 3 // 4), max(0, arr.shape[1] // 4) : max(1, arr.shape[1] * 3 // 4)]
    bg = float(np.median(center)) if center.size else float(np.median(arr))
    density = float(np.mean(np.abs(border.astype(float) - bg) > 30))
    return {"status": "ok" if density < 0.24 else "needs-padding", "edge_density": round(density, 4)}


def _infer_with_cv(image_path: Path, ocr_items: list[dict[str, Any]], primitives: dict[str, Any]) -> list[dict[str, Any]]:
    import cv2  # type: ignore

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    saturation = hsv[:, :, 1]
    edges = cv2.Canny(gray, 60, 150)
    signal = ((saturation > 55).astype("uint8") * 255)
    signal = cv2.bitwise_or(signal, edges)

    # Mask OCR text and detected structural lines so dense pictorial content wins.
    for item in ocr_items:
        box = item.get("bbox", {})
        x, y, w, h = int(box.get("x", 0)), int(box.get("y", 0)), int(box.get("w", 0)), int(box.get("h", 0))
        cv2.rectangle(signal, (x - 2, y - 2), (x + w + 2, y + h + 2), 0, -1)
    for line in primitives.get("lines", []):
        cv2.line(signal, (int(line["x1"]), int(line["y1"])), (int(line["x2"]), int(line["y2"])), 0, 5)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 15))
    merged = cv2.morphologyEx(signal, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[dict[str, Any]] = []
    for idx, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < width * height * 0.002:
            continue
        if w < 40 or h < 30:
            continue
        if area > width * height * 0.65:
            continue
        pad = int(max(6, min(18, round(min(w, h) * 0.04))))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(width, x + w + pad)
        y1 = min(height, y + h + pad)
        box = {"x": float(x0), "y": float(y0), "w": float(x1 - x0), "h": float(y1 - y0)}
        if any(_overlap_ratio(box, c.get("source_region", c)) > 0.55 for c in candidates):
            continue
        candidates.append(
            {
                "id": f"asset-auto-{len(candidates):04d}",
                "file": f"assets/asset_auto_{len(candidates):04d}.png",
                "x": box["x"],
                "y": box["y"],
                "w": box["w"],
                "h": box["h"],
                "source_region": box,
                "pad": pad,
                "kind": "auto-detected-complex-visual",
                "decision": "crop",
                "asset_fidelity": "source-preserve",
                "decision_reason": "dense color/edge region inferred as map, chart, screenshot, thumbnail, or complex visual asset",
                "background_handling": "preserve-background",
                "crop_confidence": 0.58,
                "padding_applied": pad,
                "neighbor_risk": "unknown",
            }
        )

    panel_assets: list[dict[str, Any]] = []
    image_area = width * height
    for rect in primitives.get("rectangles", []):
        x, y, w, h = int(rect.get("x", 0)), int(rect.get("y", 0)), int(rect.get("w", 0)), int(rect.get("h", 0))
        area = w * h
        aspect = w / max(1, h)
        if area < image_area * 0.025 or area > image_area * 0.18:
            continue
        if aspect < 0.55 or aspect > 3.7:
            continue
        # Prefer true panel-like regions: they should contain multiple dense/colored subregions
        # or enough internal edges to be safer as a preserved visual asset.
        sub = signal[max(0, y + 4) : min(height, y + h - 4), max(0, x + 4) : min(width, x + w - 4)]
        if sub.size == 0:
            continue
        density = float(np.mean(sub > 0))
        contained_count = sum(1 for cand in candidates if _contains({"x": x, "y": y, "w": w, "h": h}, cand.get("source_region", cand), margin=10))
        if density < 0.018 and contained_count < 2:
            continue
        box = {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}
        panel_assets.append(
            {
                "id": f"asset-panel-{len(panel_assets):04d}",
                "file": f"assets/asset_panel_{len(panel_assets):04d}.png",
                "x": box["x"],
                "y": box["y"],
                "w": box["w"],
                "h": box["h"],
                "source_region": box,
                "pad": 0,
                "kind": "auto-detected-complex-panel",
                "decision": "crop",
                "asset_fidelity": "source-preserve",
                "decision_reason": "large panel contains dense visual evidence; preserve whole panel to avoid fragmented crops and false vector lines",
                "background_handling": "preserve-background",
                "crop_confidence": 0.7 if rect.get("review_status") == "ok" else 0.6,
                "padding_applied": 0,
                "neighbor_risk": "low",
            }
        )

    candidates = _merge_nearby_assets(candidates, width, height)

    # Large panel assets replace smaller assets fully contained within them.
    filtered = []
    for cand in candidates:
        region = cand.get("source_region", cand)
        if any(_contains(panel.get("source_region", panel), region, margin=14) for panel in panel_assets):
            continue
        filtered.append(cand)
    merged = panel_assets + filtered
    return sorted(merged, key=lambda a: (a["y"], a["x"]))


def infer_assets(image_path: Path, ocr_items: list[dict[str, Any]] | None = None, primitives: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import cv2  # noqa: F401
    except Exception as exc:
        return {"status": "disabled", "error": f"OpenCV import failed: {exc}", "assets": []}
    try:
        assets = _infer_with_cv(image_path, ocr_items or [], primitives or {})
        return {"status": "ok", "assets": assets, "count": len(assets)}
    except Exception as exc:
        return {"status": "failed", "error": repr(exc), "assets": []}


def crop_assets(image_path: Path, assets: list[dict[str, Any]], out_dir: Path) -> None:
    source = Image.open(image_path).convert("RGB")
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        region = asset.get("source_region", asset)
        x = int(round(region["x"]))
        y = int(round(region["y"]))
        w = int(round(region["w"]))
        h = int(round(region["h"]))
        crop = source.crop((x, y, x + w, y + h))
        check = _edge_check(crop)
        asset["edge_check"] = check
        asset["crop_status"] = "verified" if check["status"] == "ok" else "needs-padding"
        crop_path = out_dir / asset["file"]
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(crop_path)


def make_contact_sheet(out_dir: Path, assets: list[dict[str, Any]], path: Path) -> None:
    if not assets:
        Image.new("RGB", (800, 160), "white").save(path)
        return
    cols = 3
    cell_w, cell_h = 310, 230
    rows = (len(assets) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, asset in enumerate(assets):
        im = Image.open(out_dir / asset["file"]).convert("RGB")
        im.thumbnail((260, 145))
        x = (idx % cols) * cell_w + 20
        y = (idx // cols) * cell_h + 20
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + im.width, y + im.height], outline=(80, 80, 80))
        draw.text((x, y + 154), asset["id"], fill=(0, 0, 0))
        draw.text((x, y + 174), str(asset.get("edge_check", {}))[:42], fill=(120, 0, 0) if asset.get("crop_status") != "verified" else (0, 90, 0))
        draw.text((x, y + 194), f"{int(asset['x'])},{int(asset['y'])},{int(asset['w'])},{int(asset['h'])}", fill=(70, 70, 70))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def save_asset_outputs(image_path: Path, ocr_json: Path, primitives_json: Path, out_json: Path, out_dir: Path, overlay_path: Path, contact_sheet: Path) -> dict[str, Any]:
    ocr_items = json.loads(ocr_json.read_text(encoding="utf-8")).get("items", []) if ocr_json.exists() else []
    primitives = json.loads(primitives_json.read_text(encoding="utf-8")) if primitives_json.exists() else {}
    result = infer_assets(image_path, ocr_items, primitives)
    assets = result.get("assets", [])
    crop_assets(image_path, assets, out_dir)
    make_contact_sheet(out_dir, assets, contact_sheet)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for asset in assets:
        x, y, w, h = asset["x"], asset["y"], asset["w"], asset["h"]
        color = (0, 170, 80, 210) if asset.get("crop_status") == "verified" else (255, 120, 0, 230)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x, y), asset["id"], fill=color)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(overlay_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--ocr", type=Path, default=Path("ocr_results.json"))
    parser.add_argument("--primitives", type=Path, default=Path("detected_primitives.json"))
    parser.add_argument("--out", type=Path, default=Path("asset_candidates.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--overlay", type=Path, default=Path("diagnostics/crop_overlay.png"))
    parser.add_argument("--contact-sheet", type=Path, default=Path("contact_sheet.png"))
    args = parser.parse_args()
    result = save_asset_outputs(args.image, args.ocr, args.primitives, args.out, args.out_dir, args.overlay, args.contact_sheet)
    print(json.dumps({"status": result.get("status"), "count": len(result.get("assets", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
