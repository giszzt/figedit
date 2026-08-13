#!/usr/bin/env python3
"""Put a number on every thing in the figure, so the model can point instead of measure.

The model reads coordinates off a picture badly (its own estimates land 10-40px
out), but it names things perfectly. This script closes that gap from the other
side: it finds every object by pure geometry -- no semantics, no model -- gives
each one an id, and reports the boxes it measured. The model then says
"c17 crop, c31 regenerate" and never types a coordinate.

Finding an object and drawing its exact boundary are different jobs. This script
is tuned for the first: on a historical corpus every object a finished task
needed had a candidate on it, while only about two thirds had a pixel-exact box.
That split is deliberate -- a missed object forces the model back to hand
measurement, an imperfect box is fixed downstream by snap_boxes.

Usage:
  python scripts/read_figure.py <image> --out work/evidence.json \\
      --ocr work/ocr_results.json --geometry work/geometry.json \\
      --sheets work/diagnostics

Outputs:
  evidence.json          objects[], text_slots[], regions[], repeats[]
  atlas_shapes.png       source with every shape candidate numbered
  atlas_text.png         source with every text slot numbered
  zoom_shapes_N.png      candidates magnified, <=40 per sheet, numbered
  a digest on stdout     read this first; it is the whole picture in 30 lines
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))

import region_metrics as rm  # noqa: E402
from probe_geometry import image_profile  # noqa: E402

# Ink thresholds in CIE Lab distance from the local background. Three passes
# catch flat icons (large delta), tinted panels (mid) and hairline strokes (low).
THRESHOLDS = (6.0, 12.0, 25.0)
MIN_AREA = 60
MAX_AREA_SHARE = 0.25
MIN_SIDE = 6
MIN_FILL = 0.04          # ink share inside the box; below this it is scatter, not an object
TEXT_OVERLAP_DROP = 0.70  # candidate is mostly OCR text -> the text slot already covers it
DEDUPE_IOU = 0.70
SAME_OBJECT_GROWTH = 1.6  # an enclosing box only this much bigger is the same object, not a container
CAP_DEFAULT = 220
TILES_PER_SHEET = 40

CAP_RATIO_LATIN = 0.875
EM_RATIO_CJK = 0.758

CJK_FONTS = ("msyh.ttc", "simhei.ttf", "simsun.ttc", "NotoSansCJK-Regular.ttc")


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _font(size: int) -> Any:
    for name in CJK_FONTS:
        p = Path("C:/Windows/Fonts") / name
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = lin @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    out = np.empty_like(xyz)
    out[..., 0] = 116.0 * f[..., 1] - 16.0
    out[..., 1] = 500.0 * (f[..., 0] - f[..., 1])
    out[..., 2] = 200.0 * (f[..., 1] - f[..., 2])
    return out


def local_background(img: Image.Image) -> np.ndarray:
    """What each pixel's surroundings would look like without the object on top."""
    w, h = img.size
    k = max(8, int(min(w, h) * 0.04))
    small = img.resize((max(1, w // k), max(1, h // k)), Image.BOX).filter(ImageFilter.MedianFilter(5))
    return np.asarray(small.resize((w, h), Image.BILINEAR), dtype=np.float64)


def iou(a: list[int], b: list[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / float(aw * ah + bw * bh - inter)


def contains(outer: list[int], inner: list[int], slack: int = 2) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (ix >= ox - slack and iy >= oy - slack
            and ix + iw <= ox + ow + slack and iy + ih <= oy + oh + slack)


def text_mask_from(ocr: dict | None, shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    if not ocr:
        return mask
    for item in ocr.get("items", []) or []:
        b = item.get("bbox") or {}
        if not b:
            continue
        x, y = int(b.get("x", 0)), int(b.get("y", 0))
        w, h = int(b.get("w", 0)), int(b.get("h", 0))
        mask[max(0, y - 2): y + h + 2, max(0, x - 2): x + w + 2] = True
    return mask


def raw_candidates(ink_by_threshold: dict[float, np.ndarray], canvas_area: float,
                   dilations: list[int]) -> list[dict[str, Any]]:
    """Every connected blob, at several ink thresholds and several grouping radii."""
    found: list[dict[str, Any]] = []
    for thr, ink in ink_by_threshold.items():
        variants: list[tuple[str, np.ndarray]] = [("fine", ink)]
        for d in dilations:
            variants.append((f"grouped{d}", ndimage.binary_dilation(ink, np.ones((d, d), bool))))
        for gran, mask in variants:
            labels, n = ndimage.label(mask)
            if n == 0 or n > 80000:
                continue
            slices = ndimage.find_objects(labels)
            for sl in slices:
                if sl is None:
                    continue
                ys, xs = sl
                sub = ink[ys, xs]
                if not sub.any():
                    continue
                rows = np.where(sub.any(axis=1))[0]
                cols = np.where(sub.any(axis=0))[0]
                x = xs.start + int(cols[0])
                y = ys.start + int(rows[0])
                w = int(cols[-1] - cols[0] + 1)
                h = int(rows[-1] - rows[0] + 1)
                if w < MIN_SIDE or h < MIN_SIDE:
                    continue
                area = float(w * h)
                if area < MIN_AREA or area > MAX_AREA_SHARE * canvas_area:
                    continue
                ink_px = int(sub.sum())
                if ink_px / area < MIN_FILL:
                    continue
                found.append({
                    "bbox": [x, y, w, h],
                    "granularity": "fine" if gran == "fine" else "grouped",
                    "threshold": thr,
                    "ink_px": ink_px,
                    "fill": ink_px / area,
                })
    return found


def drop_text(cands: list[dict[str, Any]], tmask: np.ndarray) -> list[dict[str, Any]]:
    """A blob that is mostly OCR text is already covered by a text slot."""
    if not tmask.any():
        return cands
    kept = []
    for c in cands:
        x, y, w, h = c["bbox"]
        window = tmask[y: y + h, x: x + w]
        if window.size and window.mean() >= TEXT_OVERLAP_DROP:
            continue
        kept.append(c)
    return kept


def dedupe(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse the same blob seen at several thresholds; prefer the more stable one."""
    order = sorted(cands, key=lambda c: (-c["bbox"][2] * c["bbox"][3], -c["fill"]))
    kept: list[dict[str, Any]] = []
    for c in order:
        hit = None
        for k in kept:
            if iou(c["bbox"], k["bbox"]) >= DEDUPE_IOU:
                hit = k
                break
        if hit is None:
            c["seen"] = 1
            kept.append(c)
        else:
            hit["seen"] = hit.get("seen", 1) + 1
            if c["granularity"] == "grouped":
                hit["granularity"] = "grouped"
    return kept


def collapse_fragments(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop a blob only when a barely-larger blob already covers the same object.

    A flat icon shatters into colour blobs at a high threshold while the grouped
    pass sees it as one; those are the same object twice and one can go. An icon
    sitting inside a panel is NOT the same object as the panel, so containment
    alone must never remove it -- the enclosing box has to be close in size
    before the two can be the same thing.
    """
    by_area = sorted(cands, key=lambda c: -(c["bbox"][2] * c["bbox"][3]))
    kept: list[dict[str, Any]] = []
    for c in by_area:
        area = c["bbox"][2] * c["bbox"][3]
        duplicate = False
        for k in kept:
            k_area = k["bbox"][2] * k["bbox"][3]
            if k_area <= SAME_OBJECT_GROWTH * area and contains(k["bbox"], c["bbox"]):
                duplicate = True
                if c["granularity"] == "fine":
                    k["has_fine"] = True
                break
        if not duplicate:
            kept.append(c)
    return kept


def objectness(c: dict[str, Any]) -> float:
    """Rank for the cap. Solid, compact, threshold-stable blobs win."""
    w, h = c["bbox"][2], c["bbox"][3]
    aspect = min(w, h) / max(w, h)
    return c["fill"] * 2.0 + aspect + 0.35 * c.get("seen", 1)


def dhash(img: Image.Image, size: int = 16) -> int:
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def find_repeats(source: Image.Image, cands: list[dict[str, Any]]) -> list[list[str]]:
    """Same icon used several times: generate or crop once, place many."""
    sigs = []
    for c in cands:
        x, y, w, h = c["bbox"]
        sigs.append((c["id"], dhash(source.crop((x, y, x + w, y + h))), w, h))
    groups: list[list[str]] = []
    used: set[str] = set()
    for i, (cid, sig, w, h) in enumerate(sigs):
        if cid in used:
            continue
        members = [cid]
        for jid, jsig, jw, jh in sigs[i + 1:]:
            if jid in used:
                continue
            if abs(jw - w) > max(4, 0.15 * w) or abs(jh - h) > max(4, 0.15 * h):
                continue
            if bin(sig ^ jsig).count("1") <= 8:
                members.append(jid)
        if len(members) > 1:
            groups.append(members)
            used.update(members)
    return groups


def measure_object(arr: np.ndarray, box: list[int]) -> dict[str, Any]:
    """Clearance, margin colour and the clean / clean-on-fill / contaminated call."""
    x, y, w, h = box
    margin = 24
    H, W = arr.shape[:2]
    x0, y0 = max(0, x - margin), max(0, y - margin)
    x1, y1 = min(W, x + w + margin), min(H, y + h + margin)
    window = arr[y0:y1, x0:x1]
    if window.size == 0:
        return {"verdict": "snap-failed", "clearance": None, "margin_fill": None}
    ring = rm.ring_pixels(arr, (x, y, w, h), margin)
    flat = rm.flat_share(ring) if len(ring) else {"color": None, "share": 0.0}
    bg, _ = rm.dominant_border_color(window)
    ink = rm.ink_mask(window, bg)
    inner = ink[y - y0: y - y0 + h, x - x0: x - x0 + w]
    gaps = {
        "left": int(x - x0), "top": int(y - y0),
        "right": int(x1 - (x + w)), "bottom": int(y1 - (y + h)),
    }
    outside = ink.copy()
    outside[y - y0: y - y0 + h, x - x0: x - x0 + w] = False
    intruders = int(outside.sum())
    if flat["share"] >= 0.97:
        verdict = "clean"
    elif flat["share"] >= 0.85:
        verdict = "clean-on-fill"
    else:
        verdict = "contaminated"
    if intruders > max(40, 0.02 * outside.size):
        verdict = "contaminated"
    object_px = window[y - y0: y - y0 + h, x - x0: x - x0 + w]
    colors = rm.flat_share(object_px[inner] if inner.any() else object_px.reshape(-1, 3))
    return {
        "verdict": verdict,
        "clearance": gaps,
        "margin_fill": flat["color"],
        "margin_flatness": flat["share"],
        "dominant": colors["color"],
    }


def solve_font_size(arr: np.ndarray, box: list[int], text: str) -> dict[str, Any]:
    x, y, w, h = box
    sub = arr[y: y + h, x: x + w]
    if sub.size == 0:
        return {}
    bg, _ = rm.dominant_border_color(sub)
    ink = rm.ink_mask(sub, bg)
    tb = rm.tight_bbox(ink)
    if tb is None:
        return {}
    ink_h = tb[3] - tb[1]
    cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    ratio = EM_RATIO_CJK if cjk else CAP_RATIO_LATIN
    return {"font_size_solved": round(ink_h / ratio, 1), "ink_height": int(ink_h)}


# --- rendering ---------------------------------------------------------------

def draw_atlas(source: Image.Image, items: list[dict[str, Any]], out: Path, colour_by: str | None = None) -> None:
    scale = min(1.0, 2000.0 / max(source.size))
    canvas = source.resize((int(source.width * scale), int(source.height * scale)), Image.LANCZOS).convert("RGB")
    layer = canvas.copy()
    draw = ImageDraw.Draw(layer)
    font = _font(max(12, int(15 / max(scale, 0.35))))
    palette = {"crop": (46, 160, 67), "regenerate": (219, 109, 40), "redraw": (47, 109, 214),
               "recheck": (200, 44, 44), "text": (90, 90, 90), "region": (140, 80, 190)}
    for it in items:
        x, y, w, h = [v * scale for v in it["bbox"]]
        colour = palette.get(it.get(colour_by or "", ""), (200, 60, 60))
        draw.rectangle([x, y, x + w, y + h], outline=colour, width=2)
        label = it["id"]
        tw = draw.textlength(label, font=font)
        ly = max(0, y - 15)
        draw.rectangle([x, ly, x + tw + 6, ly + 15], fill=colour)
        draw.text((x + 3, ly), label, fill=(255, 255, 255), font=font)
    blended = Image.blend(canvas, layer, 0.88)
    out.parent.mkdir(parents=True, exist_ok=True)
    blended.save(out)


def draw_zoom_sheets(source: Image.Image, items: list[dict[str, Any]], out_dir: Path, stem: str) -> list[Path]:
    paths: list[Path] = []
    cell = 190
    cols = 8
    font = _font(14)
    for page in range(0, len(items), TILES_PER_SHEET):
        chunk = items[page: page + TILES_PER_SHEET]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell, rows * (cell + 24) + 6), (250, 250, 250))
        draw = ImageDraw.Draw(sheet)
        for i, it in enumerate(chunk):
            r, c = divmod(i, cols)
            ox, oy = c * cell, r * (cell + 24) + 3
            x, y, w, h = it["bbox"]
            tile = source.crop((x, y, x + w, y + h))
            box = cell - 14
            if max(tile.size) < box // 2:
                f = max(1, box // max(1, max(tile.size)))
                tile = tile.resize((tile.width * f, tile.height * f), Image.NEAREST)
            tile.thumbnail((box, box), Image.LANCZOS)
            sheet.paste(tile, (ox + (cell - tile.width) // 2, oy + (box - tile.height) // 2))
            draw.rectangle([ox + 4, oy, ox + cell - 4, oy + box], outline=(222, 222, 222))
            note = f"{it['id']} {it['bbox'][2]}x{it['bbox'][3]} {it.get('verdict','')}"
            draw.text((ox + 6, oy + box + 4), note[:26], fill=(40, 40, 40), font=font)
        p = out_dir / f"{stem}_{page // TILES_PER_SHEET + 1}.png"
        out_dir.mkdir(parents=True, exist_ok=True)
        sheet.save(p)
        paths.append(p)
    return paths


# --- driver ------------------------------------------------------------------

def read_figure(image_path: Path, ocr_path: Path | None, geometry_path: Path | None,
                cap: int) -> tuple[dict[str, Any], Image.Image]:
    source = Image.open(image_path).convert("RGB")
    arr = np.asarray(source)
    canvas_area = float(source.width * source.height)

    # Blob finding assumes flat design: an object is a patch of pixels unlike its
    # background. Photographs, illustrations and posters break that assumption --
    # a rich pictorial object shatters into colour fragments and the candidate
    # sits on a tenth of it. Measured on the corpus, those figures score 5-60%
    # while flat ones score 90-100%, so this abstains rather than emitting
    # candidates that would send the model chasing fragments.
    profile = image_profile(arr)
    abstained = bool(profile["abstained"])

    lab = srgb_to_lab(arr.astype(np.float64))
    bg_lab = srgb_to_lab(local_background(source))
    delta = np.sqrt(((lab - bg_lab) ** 2).sum(axis=2))

    ocr = json.loads(ocr_path.read_text(encoding="utf-8")) if ocr_path and ocr_path.is_file() else None
    geometry = json.loads(geometry_path.read_text(encoding="utf-8")) if geometry_path and geometry_path.is_file() else None
    tmask = text_mask_from(ocr, delta.shape)

    dil = [max(3, int(min(source.size) * 0.006)), max(6, int(min(source.size) * 0.015))]
    ink_by_threshold = {t: (delta > t) & (~tmask) for t in THRESHOLDS}

    cands = raw_candidates(ink_by_threshold, canvas_area, dil)
    raw_count = len(cands)
    cands = drop_text(cands, tmask)
    cands = dedupe(cands)
    after_dedupe = len(cands)
    cands = collapse_fragments(cands)
    after_collapse = len(cands)
    cands.sort(key=objectness, reverse=True)
    capped = cands[:cap]
    capped.sort(key=lambda c: (c["bbox"][1], c["bbox"][0]))

    objects = []
    for i, c in enumerate(capped, 1):
        obj = {"id": f"c{i}", "bbox": [int(v) for v in c["bbox"]],
               "granularity": c["granularity"], "fill": round(c["fill"], 3)}
        obj.update(measure_object(arr, c["bbox"]))
        objects.append(obj)

    repeats = find_repeats(source, objects)
    rep_of = {}
    for gi, members in enumerate(repeats, 1):
        for m in members:
            rep_of[m] = f"g{gi}"
    for o in objects:
        o["repeat_group"] = rep_of.get(o["id"])

    text_slots = []
    if geometry:
        for i, s in enumerate(geometry.get("text_slots", []) or [], 1):
            b = s.get("bbox")
            if not b:
                continue
            slot = {"id": f"t{i}", "bbox": [int(v) for v in b], "text": s.get("text", ""),
                    "fill": s.get("fill"), "ocr_confidence": s.get("ocr_confidence")}
            slot.update(solve_font_size(arr, slot["bbox"], slot["text"]))
            text_slots.append(slot)
    elif ocr:
        for i, item in enumerate(ocr.get("items", []) or [], 1):
            b = item.get("bbox") or {}
            if not b:
                continue
            slot = {"id": f"t{i}", "bbox": [int(b["x"]), int(b["y"]), int(b["w"]), int(b["h"])],
                    "text": item.get("text", ""), "ocr_confidence": item.get("confidence")}
            slot.update(solve_font_size(arr, slot["bbox"], slot["text"]))
            text_slots.append(slot)

    regions = []
    if geometry:
        for i, r in enumerate(geometry.get("fill_regions", []) or [], 1):
            b = r.get("bbox")
            if not b:
                continue
            regions.append({"id": f"r{i}", "bbox": [int(v) for v in b], "color": r.get("color"),
                            "stroke": r.get("stroke"), "kind": r.get("kind")})

    evidence = {
        "source_image": str(image_path),
        "canvas": {"width": source.width, "height": source.height},
        "image_profile": profile,
        "abstained": abstained,
        "objects": objects,
        "text_slots": text_slots,
        "regions": regions,
        "repeats": repeats,
        "funnel": {"raw": raw_count, "after_dedupe": after_dedupe,
                   "after_collapse": after_collapse, "kept": len(objects), "cap": cap},
    }
    if abstained:
        evidence["abstain_reason"] = (
            f"flat_design_score {profile['flat_design_score']} 低于 {profile['abstain_threshold']}："
            "这是照片/插画/海报一类的连续画面，图形对象无法靠连通域切出来。"
            "objects 仅供参考，不要照着它点名；这张图的素材边界用 measure.py 量，或整区走清版。"
        )
    return evidence, source


def print_digest(ev: dict[str, Any], sheets: dict[str, Any]) -> None:
    _utf8()
    c = ev["canvas"]
    objs = ev["objects"]
    print(f"画布   {c['width']}x{c['height']}   平面度 {ev['image_profile']['flat_design_score']}")
    if ev.get("abstained"):
        print("\n！！ 这张图读不了")
        print(ev["abstain_reason"])
        print("\n下面的候选只当参考，别照着点名。\n")
    print(f"找到   图形 {len(objs)}   文字槽 {len(ev['text_slots'])}   面板 {len(ev['regions'])}")
    verdicts: dict[str, int] = {}
    for o in objs:
        verdicts[o.get("verdict", "?")] = verdicts.get(o.get("verdict", "?"), 0) + 1
    print("窗口   " + "   ".join(f"{k} {v}" for k, v in sorted(verdicts.items())))
    grouped = sum(1 for o in objs if o["granularity"] == "grouped")
    print(f"粒度   拼合 {grouped}   碎片 {len(objs) - grouped}   （同一对象两种粒度都在，挑对的那个）")

    if ev["repeats"]:
        print(f"\n重复   {len(ev['repeats'])} 组，同组只需切一次或生成一次，多处放置")
        for gi, members in enumerate(ev["repeats"][:6], 1):
            print(f"  g{gi}  {' = '.join(members[:8])}")

    dirty = [o for o in objs if o.get("verdict") == "contaminated"]
    if dirty:
        print(f"\n切不干净 {len(dirty)} 个，这些要么再生要么压平，不能直接切：")
        for o in dirty[:12]:
            print(f"  {o['id']:5s} {str(o['bbox']):26s} 余量平整度 {o.get('margin_flatness', 0):.2f}")

    weak = [t for t in ev["text_slots"] if (t.get("ocr_confidence") or 1.0) < 0.85]
    if weak:
        print(f"\n低置信文字 {len(weak)} 条：" + "  ".join(f"{t['id']}({t['ocr_confidence']:.2f})" for t in weak[:10]))

    f = ev["funnel"]
    print(f"\n候选漏斗  原始 {f['raw']} → 去重 {f['after_dedupe']} → 收碎片 {f['after_collapse']} → 保留 {f['kept']}")
    print("\n看图顺序  先 atlas_shapes 看分布，再 zoom_shapes 认对象，文字看 atlas_text")
    for k, v in sheets.items():
        print(f"  {k:16s} {v}")


def main() -> int:
    _utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ocr", type=Path)
    ap.add_argument("--geometry", type=Path)
    ap.add_argument("--sheets", type=Path, help="directory for atlas and zoom sheets")
    ap.add_argument("--cap", type=int, default=CAP_DEFAULT, help="max shape candidates kept")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    evidence, source = read_figure(args.image, args.ocr, args.geometry, args.cap)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    sheets: dict[str, Any] = {"evidence": args.out}
    if args.sheets:
        d = args.sheets
        draw_atlas(source, evidence["objects"], d / "atlas_shapes.png")
        sheets["atlas_shapes"] = d / "atlas_shapes.png"
        if evidence["text_slots"]:
            draw_atlas(source, evidence["text_slots"], d / "atlas_text.png")
            sheets["atlas_text"] = d / "atlas_text.png"
        if evidence["regions"]:
            draw_atlas(source, evidence["regions"], d / "atlas_regions.png")
            sheets["atlas_regions"] = d / "atlas_regions.png"
        for p in draw_zoom_sheets(source, evidence["objects"], d, "zoom_shapes"):
            sheets[p.stem] = p

    if not args.quiet:
        print_digest(evidence, sheets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
