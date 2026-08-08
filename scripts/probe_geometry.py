#!/usr/bin/env python3
"""Machine-measure the structural evidence a manifest needs: fills and text slots.

This script owns pixels only. It answers the questions the model used to answer
by hand-writing throwaway measurement scripts on every task:

  fill_regions  where are the panels/cards/bars, outlined or solid, what color
  text_slots    where does each OCR line sit, at what font size, in what color

Separators and rules are deliberately NOT reported. Every antialias fringe
along a panel edge forms its own thin connected component and is
indistinguishable from a hairline divider, so the candidates are overwhelmingly
noise. Straight strokes are still detected internally — the rectangle assembler
is built from them — they are just not offered as elements. Do not add a
`rules` output back without evidence that the two cases can be told apart.

Everything it emits is a *candidate*. OpenCV-style candidates are never
automatically final: the model adopts them (draft_elements.py + manifest_edit
--adopt) and owns the result. Nothing here writes manifest.json.

Silence is a valid answer. On photographic / painterly / AI-clean-plate images
there genuinely are no flat panels to find, so the probe computes a
`flat_design_score` first and abstains when the image is not flat-design. An
abstained run emits only very-high-confidence candidates, capped. Giving too
little costs the model one manual measurement; giving something wrong costs it
a wrong element in the manifest, which is far more expensive.

Usage:
  python scripts/probe_geometry.py input.png --out work/geometry.json \
      --ocr work/ocr_results.json --overlay work/diagnostics/geometry_overlay.png
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# --- tuning -----------------------------------------------------------------
QUANT_STEP = 16          # color bucket size when hunting dominant colors
COLOR_TOLERANCE = 22.0   # euclidean RGB distance that still counts as "same flat color"
TOP_COLORS = 14          # how many dominant colors get a connected-component pass
MIN_FILL_AREA_PX = 400   # absolute floor for a fill region
MIN_FILL_AREA_RATIO = 2e-4
MIN_FILL_SIDE = 10
FILL_RECTANGULARITY = 0.86   # component area / bbox area
STROKE_MAX_THICKNESS = 7       # thicker than this is a slab, not a stroke
STROKE_MIN_LENGTH = 24         # shortest stroke that may serve as a box side
STROKE_MIN_ASPECT = 8.0
CORNER_TOLERANCE = 8           # how far box sides may miss their shared corner
RECT_MIN_SIDE = 24
SIDE_COVERAGE = 0.70           # share of a box edge its stroke must actually cover
RING_UNIFORM_SHARE = 0.70      # share of the outside ring sitting in one color bucket
RING_FILLED_RATIO = 0.92       # the hole an outline encloses must fill its own bbox
RING_STROKE_SHARE_MAX = 0.45   # outline pixels vs enclosed area: an outline, not a slab
RING_BORDER_COVER = 0.75       # every one of the four borders must be drawn
MAX_FILL_CANVAS_SHARE = 0.55   # anything larger is the page background, not a panel
FLAT_ABSTAIN_BELOW = 0.55
ABSTAINED_FILL_CAP = 5
ABSTAINED_MIN_CONFIDENCE = 0.90
# font_size / ocr_box_height, medians calibrated on matched lines from past tasks
FONT_RATIO_LATIN = 0.875
FONT_RATIO_CJK = 0.758

CJK_RE = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


def _hex(color: np.ndarray) -> str:
    r, g, b = (int(round(float(c))) for c in color[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


# --- image profile ----------------------------------------------------------

def image_profile(arr: np.ndarray) -> dict[str, Any]:
    """Decide whether this image is flat-design enough for structure detection.

    Three signals, all cheap and all robust to size:
      coverage  share of pixels sitting in the top-N quantized color buckets
      flatness  share of pixels whose local gradient is essentially zero
      edges     share of pixels on a strong gradient (photos are full of them)
    """
    small = arr
    if max(arr.shape[:2]) > 1600:
        scale = 1600 / max(arr.shape[:2])
        h, w = arr.shape[:2]
        small = np.asarray(
            Image.fromarray(arr).resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        )
    flat = small.reshape(-1, 3)
    quant = (flat // QUANT_STEP) * QUANT_STEP
    _, counts = np.unique(quant, axis=0, return_counts=True)
    counts = np.sort(counts)[::-1]
    coverage = float(counts[:TOP_COLORS].sum()) / float(counts.sum())

    gray = small.astype(np.float32).mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    grad = np.zeros_like(gray)
    grad[:, :-1] += gx
    grad[:-1, :] += gy
    flatness = float((grad < 2.0).mean())
    edges = float((grad > 24.0).mean())

    score = 0.45 * coverage + 0.45 * flatness + 0.10 * max(0.0, 1.0 - edges * 8.0)
    return {
        "flat_design_score": round(score, 3),
        "top_color_coverage": round(coverage, 3),
        "flat_pixel_share": round(flatness, 3),
        "edge_pixel_share": round(edges, 4),
        "abstained": bool(score < FLAT_ABSTAIN_BELOW),
        "abstain_threshold": FLAT_ABSTAIN_BELOW,
    }


# --- component pass ---------------------------------------------------------

def _dominant_colors(arr: np.ndarray, limit: int) -> list[np.ndarray]:
    flat = arr.reshape(-1, 3)
    quant = (flat // QUANT_STEP) * QUANT_STEP
    colors, counts = np.unique(quant, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:limit]
    out = []
    for idx in order:
        bucket = (quant == colors[idx]).all(axis=1)
        out.append(flat[bucket].mean(axis=0).astype(float))
    return out


def _corner_radius(mask: np.ndarray) -> int:
    """Estimate corner rounding by walking the top-left diagonal of the bbox."""
    h, w = mask.shape
    limit = min(24, h // 2, w // 2)
    if limit < 2:
        return 0
    radius = 0
    for d in range(limit):
        if not mask[d, 0] and not mask[0, d]:
            radius = d + 1
        else:
            break
    return radius


def _edge_straightness(mask: np.ndarray) -> float:
    """How square-shouldered the component is: 1.0 = perfect rectangle edges."""
    rows = mask.any(axis=1)
    cols = mask.any(axis=0)
    if not rows.any() or not cols.any():
        return 0.0
    row_widths = mask.sum(axis=1)[rows]
    col_heights = mask.sum(axis=0)[cols]
    rw = float(np.median(row_widths)) or 1.0
    ch = float(np.median(col_heights)) or 1.0
    row_var = float(np.mean(np.abs(row_widths - rw))) / rw
    col_var = float(np.mean(np.abs(col_heights - ch))) / ch
    return max(0.0, 1.0 - 0.5 * (row_var + col_var))


def _ring_uniform(arr: np.ndarray, box: tuple[int, int, int, int], pad: int = 3) -> bool:
    """Does the candidate sit on one uniform surface?

    A panel or card rests on a flat parent, so the ring of pixels just outside
    its bbox is one color. A fragment of an illustration or icon rests on busy
    pixels. This is what separates a real fill region from a lucky blob inside
    a picture, and it is why small candidates are held to it.
    """
    x, y, w, h = box
    height, width = arr.shape[:2]
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(width, x + w + pad), min(height, y + h + pad)
    outer = arr[y1:y2, x1:x2]
    if outer.size == 0:
        return False
    mask = np.ones(outer.shape[:2], dtype=bool)
    iy1, ix1 = max(0, y - y1), max(0, x - x1)
    mask[iy1 : iy1 + h, ix1 : ix1 + w] = False
    ring = outer[mask]
    if len(ring) < 24:
        return False
    quant = (ring // QUANT_STEP) * QUANT_STEP
    _, counts = np.unique(quant, axis=0, return_counts=True)
    return float(counts.max()) / float(counts.sum()) >= RING_UNIFORM_SHARE



def collect_segments(arr: np.ndarray) -> tuple[list[dict], list[dict]]:
    """Thin straight strokes, per dominant color, plus flat blobs.

    Strokes are the load-bearing primitive: in the figures this skill actually
    gets, panels are outlined boxes, not colored slabs, so the outline is what
    can be found reliably. Blobs (solid slabs) are collected in the same pass
    because they fall out of the same connected-component scan.
    """
    height, width = arr.shape[:2]
    min_area = max(MIN_FILL_AREA_PX, int(width * height * MIN_FILL_AREA_RATIO))
    segments: list[dict] = []
    blobs: list[dict] = []

    for color in _dominant_colors(arr, TOP_COLORS):
        distance = np.sqrt(((arr.astype(np.float32) - color) ** 2).sum(axis=2))
        mask = distance <= COLOR_TOLERANCE
        if not mask.any():
            continue
        labels, count = ndimage.label(mask)
        if count == 0:
            continue
        for index, slc in enumerate(ndimage.find_objects(labels), start=1):
            if slc is None:
                continue
            ys, xs = slc
            x, y = int(xs.start), int(ys.start)
            w, h = int(xs.stop - xs.start), int(ys.stop - ys.start)
            sub = labels[slc] == index
            area = int(sub.sum())
            box_area = w * h
            if box_area == 0:
                continue
            rectangularity = area / box_area
            long_side, short_side = max(w, h), min(w, h)
            hexcolor = _hex(arr[slc][sub].mean(axis=0))

            if (
                short_side <= STROKE_MAX_THICKNESS
                and long_side >= STROKE_MIN_LENGTH
                and long_side / max(1, short_side) >= STROKE_MIN_ASPECT
                and rectangularity >= 0.80
            ):
                segments.append(
                    {
                        "orient": "h" if w >= h else "v",
                        "x1": x,
                        "y1": y,
                        "x2": x + w,
                        "y2": y + h,
                        "thickness": short_side,
                        "length": long_side,
                        "color": hexcolor,
                        "rectangularity": round(rectangularity, 3),
                    }
                )
                continue

            if area < min_area or w < MIN_FILL_SIDE or h < MIN_FILL_SIDE:
                continue

            # A filled panel is rarely a solid slab: icons, cards and labels sit
            # on top of it, so the flat-color component is the panel minus its
            # contents and scores as ragged. Judging it by the shape it encloses
            # is what finds it. The area guard keeps the page background itself
            # -- which encloses everything -- from being reported as a panel.
            if rectangularity < FILL_RECTANGULARITY:
                filled = ndimage.binary_fill_holes(sub)
                filled_area = int(filled.sum()) if filled is not None else 0
                if filled_area and filled_area < width * height * MAX_FILL_CANVAS_SHARE:
                    filled_rectangularity = filled_area / box_area
                    if filled_rectangularity >= FILL_RECTANGULARITY and _ring_uniform(arr, (x, y, w, h)):
                        blobs.append(
                            {
                                "bbox": [x, y, w, h],
                                "color": hexcolor,
                                "stroke": None,
                                "area": filled_area,
                                "corner_radius_est": _corner_radius(filled),
                                "kind": "solid",
                                "confidence": round(min(0.93, 0.30 + 0.65 * filled_rectangularity), 3),
                            }
                        )
                        continue
                # An outlined panel is one ring-shaped component, not four
                # strokes: its own area is tiny but it encloses a rectangle.
                ring = _as_outlined_box(arr, sub, (x, y, w, h), hexcolor)
                if ring is not None:
                    blobs.append(ring)
                continue

            straight = _edge_straightness(sub)
            if straight < 0.70:
                continue
            if not _ring_uniform(arr, (x, y, w, h)):
                continue
            blobs.append(
                {
                    "bbox": [x, y, w, h],
                    "color": hexcolor,
                    "stroke": None,
                    "area": area,
                    "corner_radius_est": _corner_radius(sub),
                    "kind": "solid",
                    "confidence": round(min(0.95, 0.30 + 0.35 * rectangularity + 0.30 * straight), 3),
                }
            )
    return segments, blobs


def _as_outlined_box(
    arr: np.ndarray, sub: np.ndarray, box: tuple[int, int, int, int], hexcolor: str
) -> dict | None:
    """Accept a component only if it is a closed rectangular outline.

    Four conditions, all of which an icon contour or a stray squiggle fails:
    the hole it encloses fills its own bounding box; the stroke itself is thin
    relative to that box; every one of the four borders is actually drawn; and
    the enclosed area is a flat color rather than a picture.
    """
    x, y, w, h = box
    if w < RECT_MIN_SIDE or h < RECT_MIN_SIDE:
        return None
    filled = ndimage.binary_fill_holes(sub)
    if filled is None:
        return None
    filled_ratio = float(filled.sum()) / float(w * h)
    if filled_ratio < RING_FILLED_RATIO:
        return None
    stroke_share = float(sub.sum()) / float(filled.sum() or 1)
    if stroke_share > RING_STROKE_SHARE_MAX:
        return None
    border_cover = min(
        float(sub[0].mean()),
        float(sub[-1].mean()),
        float(sub[:, 0].mean()),
        float(sub[:, -1].mean()),
    )
    if border_cover < RING_BORDER_COVER:
        return None
    interior = _interior_fill(arr, box, inset=max(2, int(min(w, h) * 0.12)))
    if interior is None:
        return None
    thickness = max(1, int(round(sub.sum() / max(1.0, 2.0 * (w + h)))))
    return {
        "bbox": [x, y, w, h],
        "color": interior,
        "stroke": hexcolor,
        "stroke_width": thickness,
        "area": w * h,
        "corner_radius_est": _corner_radius(sub),
        "kind": "outlined",
        "confidence": round(min(0.95, 0.55 + 0.40 * border_cover), 3),
    }


def _interior_fill(arr: np.ndarray, box: tuple[int, int, int, int], inset: int = 4) -> str | None:
    """Modal color strictly inside a box, or None when the inside is not flat."""
    x, y, w, h = box
    height, width = arr.shape[:2]
    x1, y1 = max(0, x + inset), max(0, y + inset)
    x2, y2 = min(width, x + w - inset), min(height, y + h - inset)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    patch = arr[y1:y2, x1:x2].reshape(-1, 3)
    quant = (patch // QUANT_STEP) * QUANT_STEP
    colors, counts = np.unique(quant, axis=0, return_counts=True)
    top = int(np.argmax(counts))
    if counts[top] / counts.sum() < 0.35:
        return None
    return _hex(patch[(quant == colors[top]).all(axis=1)].mean(axis=0))


def build_rectangles(arr: np.ndarray, segments: list[dict]) -> tuple[list[dict], set[int]]:
    """Assemble two horizontal + two vertical strokes of one color into a box.

    Four independent strokes agreeing on the same four corners is strong
    evidence — antialias fringes, glyph stems and icon details do not do that
    by accident. Consumed strokes are reported so they are not also emitted as
    standalone rules.
    """
    height, width = arr.shape[:2]
    rectangles: list[dict] = []
    consumed: set[int] = set()

    by_color: dict[str, list[int]] = {}
    for index, seg in enumerate(segments):
        by_color.setdefault(seg["color"], []).append(index)

    for color, indices in by_color.items():
        horizontals = [i for i in indices if segments[i]["orient"] == "h"]
        verticals = [i for i in indices if segments[i]["orient"] == "v"]
        if not horizontals or not verticals:
            continue
        buckets: dict[tuple[int, int], list[int]] = {}
        for i in horizontals:
            seg = segments[i]
            key = (int(seg["x1"] / CORNER_TOLERANCE), int(seg["x2"] / CORNER_TOLERANCE))
            for dx1 in (-1, 0, 1):
                for dx2 in (-1, 0, 1):
                    buckets.setdefault((key[0] + dx1, key[1] + dx2), []).append(i)
        seen: set[tuple[int, int]] = set()
        for i in horizontals:
            top = segments[i]
            key = (int(top["x1"] / CORNER_TOLERANCE), int(top["x2"] / CORNER_TOLERANCE))
            for j in buckets.get(key, []):
                if j == i or (min(i, j), max(i, j)) in seen:
                    continue
                bottom = segments[j]
                if bottom["y1"] <= top["y1"]:
                    continue
                seen.add((min(i, j), max(i, j)))
                if abs(bottom["x1"] - top["x1"]) > CORNER_TOLERANCE:
                    continue
                if abs(bottom["x2"] - top["x2"]) > CORNER_TOLERANCE:
                    continue
                box_h = bottom["y2"] - top["y1"]
                box_w = max(top["x2"], bottom["x2"]) - min(top["x1"], bottom["x1"])
                if box_h < RECT_MIN_SIDE or box_w < RECT_MIN_SIDE:
                    continue
                left = _find_side(segments, verticals, min(top["x1"], bottom["x1"]), top["y1"], bottom["y2"])
                right = _find_side(segments, verticals, max(top["x2"], bottom["x2"]), top["y1"], bottom["y2"])
                if left is None or right is None:
                    continue
                x = min(top["x1"], bottom["x1"])
                y = top["y1"]
                rectangles.append(
                    {
                        "bbox": [int(x), int(y), int(box_w), int(box_h)],
                        "stroke": color,
                        "stroke_width": top["thickness"],
                        "color": _interior_fill(arr, (int(x), int(y), int(box_w), int(box_h))),
                        "area": int(box_w * box_h),
                        "corner_radius_est": 0,
                        "kind": "outlined",
                        "confidence": 0.92,
                    }
                )
                consumed.update({i, j, left, right})
    return rectangles, consumed


def _find_side(segments: list[dict], verticals: list[int], x: float, y_top: float, y_bottom: float) -> int | None:
    """A vertical stroke at x spanning most of [y_top, y_bottom]."""
    span = y_bottom - y_top
    best, best_cover = None, 0.0
    for index in verticals:
        seg = segments[index]
        centre = (seg["x1"] + seg["x2"]) / 2
        if abs(centre - x) > CORNER_TOLERANCE:
            continue
        overlap = min(seg["y2"], y_bottom) - max(seg["y1"], y_top)
        cover = overlap / span if span else 0.0
        if cover > best_cover:
            best, best_cover = index, cover
    return best if best_cover >= SIDE_COVERAGE else None




def dedupe_fills(fills: list[dict]) -> list[dict]:
    """Drop near-duplicate boxes (an outline and its antialias twin)."""
    kept: list[dict] = []
    for candidate in sorted(fills, key=lambda f: (-f["confidence"], -f["area"])):
        box = tuple(candidate["bbox"])
        if any(_box_iou(box, tuple(other["bbox"])) > 0.85 for other in kept):
            continue
        kept.append(candidate)
    return kept


def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    return inter / (aw * ah + bw * bh - inter)



def nest(fills: list[dict]) -> None:
    """Set each fill's parent to the smallest region that fully contains it."""
    for child in fills:
        cx, cy, cw, ch = child["bbox"]
        best = None
        best_area = None
        for parent in fills:
            if parent is child:
                continue
            px, py, pw, ph = parent["bbox"]
            if px <= cx and py <= cy and px + pw >= cx + cw and py + ph >= cy + ch:
                if best_area is None or pw * ph < best_area:
                    best, best_area = parent, pw * ph
        child["parent"] = best["id"] if best else None


# --- text slots -------------------------------------------------------------

def _text_color(arr: np.ndarray, box: tuple[int, int, int, int]) -> tuple[str, str]:
    x, y, w, h = box
    height, width = arr.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + w), min(height, y + h)
    if x2 <= x1 or y2 <= y1:
        return "#000000", "#ffffff"
    patch = arr[y1:y2, x1:x2].reshape(-1, 3).astype(np.float32)
    # The background is the modal color of the box; the glyph color is the mean
    # of the pixels furthest from it. Averaging all ink pixels instead pulls the
    # answer toward the antialiased rim and is far less accurate.
    quant = (patch // QUANT_STEP) * QUANT_STEP
    colors, counts = np.unique(quant, axis=0, return_counts=True)
    top = int(np.argmax(counts))
    background = patch[(quant == colors[top]).all(axis=1)].mean(axis=0)
    distance = np.sqrt(((patch - background) ** 2).sum(axis=1))
    ink = patch[distance > 70.0]
    if len(ink) < 4:
        order = np.argsort(distance)
        ink = patch[order[-max(1, len(order) // 10) :]]
    far = ink[np.argsort(np.sqrt(((ink - background) ** 2).sum(axis=1)))[-max(1, len(ink) // 5) :]]
    return _hex(far.mean(axis=0)), _hex(background)


def text_slots(arr: np.ndarray, ocr_items: list[dict]) -> list[dict]:
    slots: list[dict] = []
    for item in ocr_items:
        box = item.get("bbox") or {}
        try:
            x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        text = str(item.get("text", ""))
        ratio = FONT_RATIO_CJK if CJK_RE.search(text) else FONT_RATIO_LATIN
        fill, background = _text_color(arr, (x, y, w, h))
        slots.append(
            {
                "bbox": [x, y, w, h],
                "text": text,
                "line_count": 1,
                "font_size_est": max(6, int(round(h * ratio))),
                "fill": fill,
                "background_sample": background,
                "baseline_y_est": int(round(y + h * 0.80)),
                "ocr_ids": [item.get("id")],
                "ocr_confidence": round(float(item.get("confidence", 0.0)), 3),
            }
        )
    slots.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))
    return slots


# --- overlay ----------------------------------------------------------------

def draw_overlay(arr: np.ndarray, geometry: dict, path: Path) -> None:
    image = Image.fromarray(arr).convert("RGB")
    draw = ImageDraw.Draw(image)
    for region in geometry["fill_regions"]:
        x, y, w, h = region["bbox"]
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(0, 140, 255), width=2)
        draw.text((x + 3, y + 3), region["id"].replace("g-fill-", "F"), fill=(0, 90, 200))
    for slot in geometry["text_slots"]:
        x, y, w, h = slot["bbox"]
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(20, 170, 90), width=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


# --- driver -----------------------------------------------------------------

def probe(image_path: Path, ocr_path: Path | None = None) -> tuple[dict, np.ndarray]:
    with Image.open(image_path) as im:
        arr = np.asarray(im.convert("RGB"))

    ocr_items: list[dict] = []
    if ocr_path and ocr_path.exists():
        payload = json.loads(ocr_path.read_text(encoding="utf-8"))
        ocr_items = payload.get("items", [])

    text_mask = np.zeros(arr.shape[:2], dtype=bool)
    for item in ocr_items:
        box = item.get("bbox") or {}
        try:
            x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
        except (KeyError, TypeError, ValueError):
            continue
        text_mask[max(0, y) : y + h, max(0, x) : x + w] = True

    profile = image_profile(arr)
    segments, blobs = collect_segments(arr)
    outlined, _ = build_rectangles(arr, segments)
    fills = dedupe_fills(outlined + blobs)

    if profile["abstained"]:
        fills = [f for f in fills if f["confidence"] >= ABSTAINED_MIN_CONFIDENCE]
        fills.sort(key=lambda f: -f["area"])
        fills = fills[:ABSTAINED_FILL_CAP]
        profile["abstain_reason"] = (
            "image is not flat-design (photographic/painterly gradients dominate); "
            "structure candidates are unreliable here, measure by hand or route to AI clean plate"
        )

    fills.sort(key=lambda f: -f["area"])
    for index, region in enumerate(fills):
        region["id"] = f"g-fill-{index:03d}"
    nest(fills)

    slots = text_slots(arr, ocr_items)
    for index, slot in enumerate(slots):
        slot["id"] = f"g-slot-{index:03d}"

    geometry = {
        "source_image": str(image_path),
        "canvas": {"width": int(arr.shape[1]), "height": int(arr.shape[0])},
        "image_profile": profile,
        "fill_regions": fills,
        "text_slots": slots,
        "contract": "candidates only; never auto-final. Adopt via draft_elements.py + manifest_edit --adopt.",
        "measured_reliability": {
            "fill_regions": "verify against the overlay before adopting",
            "text_slot_position": "reliable; it is OCR",
            "text_slot_font_size": "estimate; expect to correct roughly 1 in 3",
            "text_slot_fill": "estimate; expect to correct roughly 1 in 3",
        },
    }
    return geometry, arr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ocr", type=Path, default=None)
    parser.add_argument("--overlay", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    geometry, arr = probe(args.image.resolve(), args.ocr.resolve() if args.ocr else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.overlay:
        draw_overlay(arr, geometry, args.overlay.resolve())

    profile = geometry["image_profile"]
    if not args.quiet:
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "flat_design_score": profile["flat_design_score"],
                    "abstained": profile["abstained"],
                    "fill_regions": len(geometry["fill_regions"]),
                    "text_slots": len(geometry["text_slots"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
