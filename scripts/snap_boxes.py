#!/usr/bin/env python3
"""Snap rough survey boxes to pixel-accurate crop windows and grade contamination.

The model owns semantics (what each object is, which route it takes, what to do
with a contaminated object). This script owns pixels only: it takes the rough
boxes from work/inventory.json, snaps each to the tight ink boundary, measures
four-side clearance, detects foreign ink and margin uniformity, and reports a
mechanical crop-window verdict per object:

  clean          window margin is the canvas background, four sides clear
  clean-on-fill  window margin is one uniform flat non-canvas color, four sides clear
  contaminated   foreign ink in window / object extends beyond window /
                 non-uniform margin / insufficient clearance
  snap-failed    rough box did not land on a usable ink component; needs a look
  skipped        route does not take a crop window (redraw/retype/math/region)

Verdicts are evidence, not gates. contaminated items are for the model to
re-route (regenerate-chroma / flatten), snap-failed items are for the model to
re-check visually. quality_audit.py keeps its own post-hoc crop-window gate.

Usage:
  python scripts/snap_boxes.py input.png --inventory work/inventory.json \
      --out work/snap_report.json --sheet work/snap_sheet.png
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

import region_metrics as rm

SNAP_ROUTES = {"crop", "regenerate-chroma", "flatten"}
VERDICT_COLORS = {
    "clean": "#1a9641",
    "clean-on-fill": "#e0b400",
    "contaminated": "#d7191c",
    "snap-failed": "#808080",
}


def _clamp_box(x: int, y: int, w: int, h: int, width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + w), min(height, y + h)
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)


def _main_object_mask(ink: np.ndarray, rough: tuple[int, int, int, int]) -> np.ndarray | None:
    """Ink components that belong to the surveyed object.

    A component counts as part of the object when the majority of its pixels
    fall inside the rough box; that keeps multi-part objects (icon + separate
    detail strokes) together without grabbing neighbours that merely poke into
    the box. A second pass bridges fragments that anti-aliasing split off the
    object outline: foreign components sitting within 3 px of the accepted
    main ink are merged back in.
    """
    labels, count = ndimage.label(ink)
    if count == 0:
        return None
    rx, ry, rw, rh = rough
    inside = np.zeros_like(ink)
    inside[ry : ry + rh, rx : rx + rw] = True
    main = np.zeros_like(ink)
    found = False
    component_slices = ndimage.find_objects(labels)
    leftovers: list[tuple[Any, np.ndarray]] = []
    for index, slc in enumerate(component_slices, start=1):
        if slc is None:
            continue
        component = labels[slc] == index
        overlap = float(np.logical_and(component, inside[slc]).sum())
        if overlap == 0:
            continue
        if overlap / float(component.sum()) >= 0.5:
            main[slc] |= component
            found = True
        else:
            leftovers.append((slc, component))
    if not found:
        return None
    # Single bridging pass, no chaining: a fragment must touch the accepted
    # main ink itself, which keeps genuinely separate neighbours out. The size
    # cap keeps this to outline fragments; a large adjacent structure (another
    # object right below) must not ride in on a 3 px gap.
    bridge = ndimage.binary_dilation(main, iterations=3)
    size_cap = 0.25 * float(main.sum())
    for slc, component in leftovers:
        if float(component.sum()) > size_cap:
            continue
        if np.logical_and(component, bridge[slc]).any():
            main[slc] |= component
    return main


RING_WIDTH = 8
FLAT_MIN_SHARE = 0.92


def _text_mask_for_window(
    text_boxes: list[tuple[int, int, int, int]], wx: int, wy: int, ww: int, wh: int
) -> np.ndarray | None:
    """Boolean window mask of known text regions (OCR boxes, 2 px halo)."""
    mask = np.zeros((wh, ww), dtype=bool)
    hit = False
    for tx, ty, tw, th in text_boxes:
        x1, y1 = max(0, tx - 2 - wx), max(0, ty - 2 - wy)
        x2, y2 = min(ww, tx + tw + 2 - wx), min(wh, ty + th + 2 - wy)
        if x2 > x1 and y2 > y1:
            mask[y1:y2, x1:x2] = True
            hit = True
    return mask if hit else None


def load_text_boxes(path: Path) -> list[tuple[int, int, int, int]]:
    """Accept prepare_measurements OCR output or a plain list of boxes."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("results", data.get("items", data.get("boxes", data))) if isinstance(data, dict) else data
    boxes: list[tuple[int, int, int, int]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        box = entry.get("box") or entry.get("bbox") or entry
        if isinstance(box, dict) and all(key in box for key in ("x", "y", "w", "h")):
            boxes.append((int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])))
        elif isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
            boxes.append(tuple(int(v) for v in box))  # type: ignore[arg-type]
    return boxes


def _snap_once(
    window: np.ndarray,
    background: np.ndarray,
    rough_in_window: tuple[int, int, int, int],
    text_mask: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, list[int]] | None:
    """One snap pass against a background reference.

    Known text regions can never join the object: captions sitting right next
    to an icon would otherwise be absorbed and drag the window over them.

    Returns (ink, main, tight_bbox_in_window) or None when nothing usable
    lies under the rough box.
    """
    ink = rm.ink_mask(window, background)
    candidate_ink = np.logical_and(ink, ~text_mask) if text_mask is not None else ink
    main = _main_object_mask(candidate_ink, rough_in_window)
    if main is None:
        return None
    tight = rm.tight_bbox(main)
    if tight is None:
        return None
    return ink, main, tight


def snap_object(
    arr: np.ndarray,
    canvas_color: str,
    obj: dict[str, Any],
    margin: int,
    padding: int,
    intruder_min: int,
    min_clearance: int,
    text_boxes: list[tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    height, width = arr.shape[:2]
    bx, by, bw, bh = [int(round(float(v))) for v in obj["bbox"]]
    bx, by, bw, bh = _clamp_box(bx, by, bw, bh, width, height)

    result: dict[str, Any] = {"id": obj["id"], "route": obj.get("route"), "input_bbox": [bx, by, bw, bh]}
    reasons: list[str] = []

    # Background reference comes from the ring just outside the candidate
    # window, not from the working-window border: near card boundaries the
    # border mixes two fills and poisons the ink mask.
    current_margin = margin
    touches_edge = False
    for attempt in range(2):
        wx, wy, ww, wh = _clamp_box(
            bx - current_margin, by - current_margin, bw + 2 * current_margin, bh + 2 * current_margin, width, height
        )
        window = arr[wy : wy + wh, wx : wx + ww]
        rough = (bx - wx, by - wy, bw, bh)
        text_mask = _text_mask_for_window(text_boxes, wx, wy, ww, wh) if text_boxes else None
        if text_mask is not None:
            # Text exclusion is for captions around the object. Inside the
            # rough box the model's claim wins: OCR boxes are sloppy and often
            # cover icon parts, which must stay eligible for the object.
            rx, ry = bx - wx, by - wy
            text_mask[max(0, ry) : ry + bh, max(0, rx) : rx + bw] = False
        background, _ = rm.mode_color(rm.ring_pixels(arr, (bx, by, bw, bh), RING_WIDTH))
        snapped_pass = _snap_once(window, background, rough, text_mask)
        if snapped_pass is None:
            result.update({"verdict": "snap-failed", "reasons": ["no-ink-under-box"]})
            return result
        ink, main, tight = snapped_pass

        # Recalibrate once against the ring outside the *snapped* box: if the
        # rough box was oversized the first ring may sit on a different fill.
        snapped_abs = (wx + tight[0], wy + tight[1], tight[2] - tight[0], tight[3] - tight[1])
        background2, _ = rm.mode_color(rm.ring_pixels(arr, snapped_abs, RING_WIDTH))
        if not rm.color_close(rm.rgb_hex(background), rm.rgb_hex(background2)):
            snapped_pass = _snap_once(window, background2, rough, text_mask)
            if snapped_pass is not None:
                ink, main, tight = snapped_pass
                background = background2

        touches_edge = (
            (tight[0] == 0 and wx > 0)
            or (tight[1] == 0 and wy > 0)
            or (tight[2] == ww and wx + ww < width)
            or (tight[3] == wh and wy + wh < height)
        )
        if touches_edge and attempt == 0:
            current_margin = margin * 3
            continue
        break

    if touches_edge:
        reasons.append("object-extends-beyond-window")

    tight_area = (tight[2] - tight[0]) * (tight[3] - tight[1])
    if tight_area < 0.05 * bw * bh:
        result.update({"verdict": "snap-failed", "reasons": ["ink-far-smaller-than-box"]})
        return result

    ww, wh = window.shape[1], window.shape[0]
    sx1 = max(0, tight[0] - padding)
    sy1 = max(0, tight[1] - padding)
    sx2 = min(ww, tight[2] + padding)
    sy2 = min(wh, tight[3] + padding)

    # Anti-aliasing halos around strokes are neither ink nor fill; a 2 px
    # dilation keeps them out of both the foreign-ink and uniformity checks.
    dilated_main = ndimage.binary_dilation(main, iterations=2)
    foreign = np.logical_and(ink, ~dilated_main)

    # Trim padding rows/columns that caught the fringe of a neighbour (top
    # pixels of a caption under an icon, a border a couple px away). Only rows
    # without any object ink may go, so the object itself is never cut.
    for _ in range(padding + 4):
        trimmed = False
        if sy2 - sy1 > 2 and foreign[sy2 - 1, sx1:sx2].any() and not main[sy2 - 1, sx1:sx2].any():
            sy2 -= 1
            trimmed = True
        if sy2 - sy1 > 2 and foreign[sy1, sx1:sx2].any() and not main[sy1, sx1:sx2].any():
            sy1 += 1
            trimmed = True
        if sx2 - sx1 > 2 and foreign[sy1:sy2, sx2 - 1].any() and not main[sy1:sy2, sx2 - 1].any():
            sx2 -= 1
            trimmed = True
        if sx2 - sx1 > 2 and foreign[sy1:sy2, sx1].any() and not main[sy1:sy2, sx1].any():
            sx1 += 1
            trimmed = True
        if not trimmed:
            break

    snapped = [wx + sx1, wy + sy1, sx2 - sx1, sy2 - sy1]
    result["snapped_bbox"] = snapped

    # Foreign ink inside the snapped window.
    foreign_in_window = foreign[sy1:sy2, sx1:sx2]
    if int(foreign_in_window.sum()) >= intruder_min:
        labels, count = ndimage.label(foreign_in_window)
        sizes = ndimage.sum_labels(foreign_in_window, labels, index=range(1, count + 1)) if count else []
        if any(size >= intruder_min for size in np.atleast_1d(sizes)):
            reasons.append("foreign-ink-in-window")

    # Four-side clearance: distance from the snapped window edge to the nearest
    # foreign ink, capped at the working margin.
    clearance = {}
    spans = {
        "top": foreign[max(0, sy1 - current_margin) : sy1, sx1:sx2][::-1],
        "bottom": foreign[sy2 : min(wh, sy2 + current_margin), sx1:sx2],
        "left": foreign[sy1:sy2, max(0, sx1 - current_margin) : sx1][:, ::-1].T,
        "right": foreign[sy1:sy2, sx2 : min(ww, sx2 + current_margin)].T,
    }
    for side, strip in spans.items():
        distance = current_margin
        for offset in range(strip.shape[0]):
            if strip[offset].any():
                distance = offset
                break
        clearance[side] = int(distance)
    result["clearance"] = clearance
    warnings = [f"zero-clearance-{side}" for side, value in clearance.items() if value == 0]
    if (snapped[2] * snapped[3]) > 1.6 * bw * bh:
        warnings.append("snapped-much-larger-than-box")
    if min_clearance > 0 and any(value < min_clearance for value in clearance.values()):
        reasons.append("insufficient-clearance")

    # Fill flatness of the snapped window minus the (dilated) object ink.
    window_arr = window[sy1:sy2, sx1:sx2]
    margin_pixels = window_arr[~dilated_main[sy1:sy2, sx1:sx2]]
    fill = rm.flat_share(margin_pixels)
    margin_fill = {"uniform": fill["share"] >= FLAT_MIN_SHARE, **fill}
    result["margin_fill"] = margin_fill
    if not margin_fill["uniform"]:
        reasons.append("non-uniform-margin")

    if reasons:
        verdict = "contaminated"
    elif rm.color_close(margin_fill["color"], canvas_color):
        verdict = "clean"
    else:
        verdict = "clean-on-fill"
    result["verdict"] = verdict
    result["reasons"] = reasons
    result["warnings"] = warnings
    result["suggested_crop_window"] = snapped
    return result


def _render_sheet(image: Image.Image, results: list[dict[str, Any]], sheet_path: Path, margin: int) -> None:
    items = [r for r in results if r.get("verdict") not in (None, "skipped")]
    if not items:
        return
    columns = min(4, max(1, math.ceil(math.sqrt(len(items)))))
    rows = math.ceil(len(items) / columns)
    label_h, gap = 30, 10
    tiles = []
    for r in items:
        box = r.get("snapped_bbox") or r["input_bbox"]
        x, y, w, h = box
        cx1, cy1 = max(0, x - margin), max(0, y - margin)
        cx2, cy2 = min(image.width, x + w + margin), min(image.height, y + h + margin)
        tile = image.crop((cx1, cy1, cx2, cy2)).convert("RGB")
        draw = ImageDraw.Draw(tile)
        color = VERDICT_COLORS.get(r["verdict"], "#000000")
        draw.rectangle([x - cx1, y - cy1, x + w - cx1 - 1, y + h - cy1 - 1], outline=color, width=2)
        tiles.append((r, tile))
    col_w = [max(t.width for r, t in tiles[c::columns]) for c in range(columns) if tiles[c::columns]]
    row_h = [max(t.height + label_h for r, t in tiles[ri * columns : (ri + 1) * columns]) for ri in range(rows)]
    sheet = Image.new("RGB", (sum(col_w) + gap * (columns + 1), sum(row_h) + gap * (rows + 1)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    y = gap
    for ri in range(rows):
        x = gap
        for ci in range(columns):
            index = ri * columns + ci
            if index >= len(tiles):
                break
            r, tile = tiles[index]
            label = f"{r['id']}  {r['verdict']}" + (f"  ({', '.join(r['reasons'])})" if r.get("reasons") else "")
            draw.text((x, y + 6), label[:70], fill=VERDICT_COLORS.get(r["verdict"], "black"), font=font)
            sheet.paste(tile, (x, y + label_h))
            x += col_w[ci] + gap
        y += row_h[ri] + gap
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--exclude-text", type=Path, help="OCR result or box list; text regions never join an object")
    parser.add_argument("--margin", type=int, default=24)
    parser.add_argument("--padding", type=int, default=2)
    parser.add_argument("--intruder-min", type=int, default=9)
    parser.add_argument(
        "--min-clearance",
        type=int,
        default=0,
        help="sides with clearance below this count as contaminated; 0 keeps zero-clearance as a warning only",
    )
    args = parser.parse_args()

    image = Image.open(args.image).convert("RGB")
    arr = np.asarray(image, dtype=np.int16)
    canvas_bg, _ = rm.dominant_border_color(arr)
    canvas_color = rm.rgb_hex(canvas_bg)

    text_boxes = load_text_boxes(args.exclude_text) if args.exclude_text else None
    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    objects = data.get("objects", data) if isinstance(data, dict) else data
    if not isinstance(objects, list):
        raise SystemExit("inventory must be a JSON array or an object with an objects array")

    results: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, dict) or not obj.get("id"):
            continue
        route = str(obj.get("route", ""))
        if route not in SNAP_ROUTES or not obj.get("bbox"):
            results.append({"id": obj["id"], "route": route, "verdict": "skipped"})
            continue
        results.append(
            snap_object(
                arr, canvas_color, obj, args.margin, args.padding, args.intruder_min, args.min_clearance, text_boxes
            )
        )

    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    report = {
        "source": str(args.image),
        "canvas_color": canvas_color,
        "params": {
            "margin": args.margin,
            "padding": args.padding,
            "intruder_min": args.intruder_min,
            "min_clearance": args.min_clearance,
        },
        "counts": counts,
        "objects": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.sheet:
        _render_sheet(image, results, args.sheet, args.margin)
    print(json.dumps({"counts": counts, "out": str(args.out), "sheet": str(args.sheet) if args.sheet else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
