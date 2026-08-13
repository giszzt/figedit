#!/usr/bin/env python3
"""Batched pixel measurement. One call answers many questions, numbers and picture together.

Replaces the ad-hoc `python -c "import numpy ..."` probes that dominate task time:
every query below was written by hand, repeatedly, in past tasks. Asking them one
at a time costs one round trip each; asking them together costs one.

Usage:
  python scripts/measure.py <image> --q "name:type@args" ... [--sheet work/measure_sheet.png]

Query types (args are the window x,y,w,h in source pixels unless noted):
  info                    image size / mode; `info@path` for another file
  bbox@x,y,w,h            tight ink box inside the window, plus how much slack was trimmed
  color@x,y,w,h           dominant color, mean color, whether the window is one flat color
  clearance@x,y,w,h       empty margin on each side between the window edge and the ink
  alpha-bbox@path         tight box of non-transparent pixels in an RGBA file
  fontfit@x,y,w,h         font_size that reproduces the text rendered in this window
  diff@path,x,y,w,h       scale / offset / color distance between a file and a source region
  zoom@x,y,w,h            no numbers, just put a magnified crop on the sheet

Every query also contributes a labeled tile to --sheet, so one Read covers all of them.
Names are free-form and echo back in both the table and the sheet.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from region_metrics import (  # noqa: E402
    dominant_border_color,
    flat_share,
    ink_mask,
    mode_color,
    rgb_hex,
    tight_bbox,
)

# Rendered ink height as a share of font_size, measured over 26 historical tasks.
CAP_RATIO_LATIN = 0.875
EM_RATIO_CJK = 0.758

CELL = 260
COLS = 5

# Sheet labels carry Chinese; the PIL default font renders it as boxes.
CJK_FONTS = ("msyh.ttc", "msyhl.ttc", "simhei.ttf", "simsun.ttc", "NotoSansCJK-Regular.ttc")


def label_font(size: int) -> Any:
    for name in CJK_FONTS:
        for path in (Path("C:/Windows/Fonts") / name, Path("/usr/share/fonts/opentype/noto") / name):
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class QueryError(ValueError):
    pass


def parse_query(raw: str) -> dict[str, Any]:
    """`name:type@args` -> {name, type, args}. `@args` is optional."""
    if ":" not in raw:
        raise QueryError(f"missing ':' in {raw!r}; expected name:type@args")
    name, rest = raw.split(":", 1)
    if "@" in rest:
        qtype, args = rest.split("@", 1)
    else:
        qtype, args = rest, ""
    return {"name": name.strip(), "type": qtype.strip().lower(), "args": args.strip()}


def parse_box(args: str, canvas: tuple[int, int]) -> tuple[int, int, int, int]:
    parts = [p for p in args.replace(" ", "").split(",") if p]
    if len(parts) != 4:
        raise QueryError(f"expected x,y,w,h; got {args!r}")
    try:
        x, y, w, h = (int(round(float(p))) for p in parts)
    except ValueError as exc:
        raise QueryError(f"non-numeric box {args!r}") from exc
    width, height = canvas
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    w = max(1, min(width - x, w))
    h = max(1, min(height - y, h))
    return x, y, w, h


def crop(arr: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    return arr[y : y + h, x : x + w]


def q_info(path: Path) -> dict[str, Any]:
    with Image.open(path) as im:
        return {"summary": f"{im.size[0]}x{im.size[1]} {im.mode}", "size": list(im.size), "mode": im.mode}


def q_bbox(arr: np.ndarray, box: tuple[int, int, int, int], text_mask: np.ndarray | None = None) -> dict[str, Any]:
    sub = crop(arr, box)
    background, _ = dominant_border_color(sub)
    mask = ink_mask(sub, background)
    if text_mask is not None:
        # A rough window around an icon almost always catches its caption, and a
        # box drawn round both is the wrong crop. OCR already knows where the
        # letters are, so exclude them from what counts as the object.
        mask = mask & ~crop(text_mask[..., None], box)[..., 0]
    tb = tight_bbox(mask)
    if tb is None:
        return {"summary": "empty (no ink found)", "bbox": None}
    x, y, w, h = box
    abs_box = [x + tb[0], y + tb[1], tb[2] - tb[0], tb[3] - tb[1]]
    trimmed = [tb[0], tb[1], w - tb[2], h - tb[3]]
    return {
        "summary": f"{abs_box[0]},{abs_box[1]},{abs_box[2]},{abs_box[3]}  裁掉 L{trimmed[0]} T{trimmed[1]} R{trimmed[2]} B{trimmed[3]}",
        "bbox": abs_box,
        "trimmed": trimmed,
        "background": rgb_hex(background),
    }


def q_color(arr: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Any]:
    sub = crop(arr, box)
    pixels = sub.reshape(-1, 3)
    dominant, share = mode_color(pixels)
    flat = flat_share(pixels)
    mean = pixels.mean(axis=0)
    uniform = flat["share"] >= 0.97
    return {
        "summary": f"主色 {rgb_hex(dominant)} 占{share:.0%}  均值 {rgb_hex(mean)}  {'单一实色' if uniform else '非实色'}",
        "dominant": rgb_hex(dominant),
        "dominant_share": round(float(share), 4),
        "mean": rgb_hex(mean),
        "flat_share": flat["share"],
        "uniform": bool(uniform),
    }


def q_clearance(arr: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Any]:
    sub = crop(arr, box)
    background, _ = dominant_border_color(sub)
    mask = ink_mask(sub, background)
    tb = tight_bbox(mask)
    if tb is None:
        x, y, w, h = box
        return {"summary": "empty (no ink found)", "clearance": {"left": w // 2, "top": h // 2, "right": w // 2, "bottom": h // 2}}
    x, y, w, h = box
    gaps = {"left": tb[0], "top": tb[1], "right": w - tb[2], "bottom": h - tb[3]}
    touching = [k for k, v in gaps.items() if v <= 0]
    note = f"  贴边: {'/'.join(touching)}" if touching else ""
    return {
        "summary": f"L{gaps['left']} T{gaps['top']} R{gaps['right']} B{gaps['bottom']}{note}",
        "clearance": gaps,
        "touching": touching,
    }


def q_alpha_bbox(path: Path) -> dict[str, Any]:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    alpha = np.asarray(rgba)[:, :, 3]
    mask = alpha > 8
    tb = tight_bbox(mask)
    if tb is None:
        return {"summary": "fully transparent", "bbox": None}
    box = [tb[0], tb[1], tb[2] - tb[0], tb[3] - tb[1]]
    filled = float(mask.mean())
    return {
        "summary": f"{box[0]},{box[1]},{box[2]},{box[3]}  画布 {rgba.size[0]}x{rgba.size[1]}  不透明占{filled:.0%}",
        "bbox": box,
        "canvas": list(rgba.size),
        "opaque_share": round(filled, 4),
    }


def q_fontfit(arr: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Any]:
    sub = crop(arr, box)
    background, _ = dominant_border_color(sub)
    mask = ink_mask(sub, background)
    tb = tight_bbox(mask)
    if tb is None:
        return {"summary": "empty (no glyphs found)", "font_size": None}
    ink_h = tb[3] - tb[1]
    ink_w = tb[2] - tb[0]
    latin = ink_h / CAP_RATIO_LATIN
    cjk = ink_h / EM_RATIO_CJK
    return {
        "summary": f"墨迹 {ink_w}x{ink_h}  字号 拉丁{latin:.1f} 中日韩{cjk:.1f}",
        "ink_size": [ink_w, ink_h],
        "font_size_latin": round(latin, 1),
        "font_size_cjk": round(cjk, 1),
    }


def q_diff(arr: np.ndarray, args: str, canvas: tuple[int, int]) -> dict[str, Any]:
    parts = args.split(",", 1)
    if len(parts) != 2:
        raise QueryError("expected path,x,y,w,h")
    path = Path(parts[0].strip())
    box = parse_box(parts[1], canvas)
    if not path.is_file():
        raise QueryError(f"file not found: {path}")
    with Image.open(path) as im:
        candidate = im.convert("RGB")
    x, y, w, h = box
    scale_x = candidate.size[0] / w
    scale_y = candidate.size[1] / h
    resized = np.asarray(candidate.resize((w, h), Image.LANCZOS), dtype=float)
    source = crop(arr, box).astype(float)
    delta = float(np.sqrt(((source - resized) ** 2).sum(axis=2)).mean())
    return {
        "summary": f"缩放 {scale_x:.3f}x{scale_y:.3f}  平均色距 {delta:.1f}  {'对得上' if delta < 12 else '对不上'}",
        "scale": [round(scale_x, 4), round(scale_y, 4)],
        "mean_distance": round(delta, 2),
        "aligned": bool(delta < 12),
    }


def load_text_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", data) if isinstance(data, dict) else data
    mask = np.zeros(shape, dtype=bool)
    for item in items or []:
        b = item.get("bbox") if isinstance(item, dict) else None
        if not b:
            continue
        x, y = int(b.get("x", 0)), int(b.get("y", 0))
        w, h = int(b.get("w", 0)), int(b.get("h", 0))
        mask[max(0, y - 1): y + h + 1, max(0, x - 1): x + w + 1] = True
    return mask


def run_query(q: dict[str, Any], arr: np.ndarray, source: Path, canvas: tuple[int, int],
              text_mask: np.ndarray | None = None) -> dict[str, Any]:
    qtype, args = q["type"], q["args"]
    if qtype == "info":
        return q_info(Path(args) if args else source)
    if qtype == "alpha-bbox":
        if not args:
            raise QueryError("alpha-bbox needs a file path")
        return q_alpha_bbox(Path(args))
    if qtype == "diff":
        return q_diff(arr, args, canvas)
    if qtype in {"bbox", "color", "clearance", "fontfit", "zoom"}:
        box = parse_box(args, canvas)
        if qtype == "bbox":
            result = q_bbox(arr, box, text_mask)
        elif qtype == "color":
            result = q_color(arr, box)
        elif qtype == "clearance":
            result = q_clearance(arr, box)
        elif qtype == "fontfit":
            result = q_fontfit(arr, box)
        else:
            result = {"summary": f"{box[2]}x{box[3]} 放大图见 sheet"}
        result["window"] = list(box)
        return result
    raise QueryError(f"unknown query type {qtype!r}")


def tile_image(q: dict[str, Any], result: dict[str, Any], source_img: Image.Image) -> Image.Image | None:
    """The picture that goes with a query: the window, magnified to fill a cell."""
    window = result.get("window")
    if window:
        x, y, w, h = window
        tile = source_img.crop((x, y, x + w, y + h))
        measured = result.get("bbox")
        if measured and len(measured) == 4:
            # Show where the answer landed inside the window asked about, so the
            # sheet confirms the number instead of only illustrating the query.
            tile = tile.convert("RGB")
            d = ImageDraw.Draw(tile)
            mx, my, mw, mh = measured
            d.rectangle([mx - x, my - y, mx - x + mw - 1, my - y + mh - 1],
                        outline=(220, 30, 30), width=max(1, min(w, h) // 60))
        return tile
    if q["type"] == "alpha-bbox" and q["args"]:
        try:
            with Image.open(q["args"]) as im:
                return im.convert("RGBA")
        except Exception:
            return None
    if q["type"] == "diff":
        path = q["args"].split(",", 1)[0].strip()
        try:
            with Image.open(path) as im:
                return im.convert("RGB")
        except Exception:
            return None
    return None


def fit_label(draw: ImageDraw.ImageDraw, text: str, font: Any, limit: int) -> str:
    """Truncate by rendered width; CJK glyphs are far wider than a char count implies."""
    if draw.textlength(text, font=font) <= limit:
        return text
    while text and draw.textlength(text + "…", font=font) > limit:
        text = text[:-1]
    return text + "…"


def build_sheet(queries: list[dict[str, Any]], results: list[dict[str, Any]], source_img: Image.Image, out: Path) -> None:
    tiles = []
    for q, r in zip(queries, results):
        if "error" in r:
            continue
        img = tile_image(q, r, source_img)
        if img is not None:
            tiles.append((q, r, img))
    if not tiles:
        return
    cols = min(COLS, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL, rows * (CELL + 40) + 8), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    name_font = label_font(15)
    note_font = label_font(14)
    for i, (q, r, img) in enumerate(tiles):
        row, col = divmod(i, cols)
        ox, oy = col * CELL, row * (CELL + 40) + 4
        box = CELL - 16
        work = img.copy()
        if max(work.size) < box // 2:  # magnify small windows so they stay legible
            factor = max(1, box // max(1, max(work.size)))
            work = work.resize((work.size[0] * factor, work.size[1] * factor), Image.NEAREST)
        work.thumbnail((box, box), Image.LANCZOS)
        if work.mode == "RGBA":
            plate = Image.new("RGB", work.size, (235, 235, 235))
            plate.paste(work, (0, 0), work)
            work = plate
        px = ox + (CELL - work.size[0]) // 2
        py = oy + (box - work.size[1]) // 2
        draw.rectangle([ox + 6, oy, ox + CELL - 6, oy + box], outline=(220, 220, 220))
        sheet.paste(work, (px, py))
        limit = CELL - 20
        head = fit_label(draw, f"{q['name']}  [{q['type']}]", name_font, limit)
        note = fit_label(draw, str(r.get("summary", "")), note_font, limit)
        draw.text((ox + 8, oy + box + 4), head, fill=(20, 20, 20), font=name_font)
        draw.text((ox + 8, oy + box + 22), note, fill=(120, 60, 60), font=note_font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main() -> None:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path, help="source figure; windows are in its pixel coordinates")
    parser.add_argument("--q", nargs="+", required=True, metavar="QUERY", help="name:type@args, repeatable")
    parser.add_argument("--exclude-text", type=Path, metavar="OCR",
                        help="ocr_results.json; bbox then ignores caption pixels inside the window")
    parser.add_argument("--sheet", type=Path, help="write a labeled contact sheet of every query window")
    parser.add_argument("--json", type=Path, help="also write full results as JSON")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"image not found: {args.image}")
    with Image.open(args.image) as im:
        source_img = im.convert("RGB")
    arr = np.asarray(source_img)
    canvas = source_img.size
    text_mask = None
    if args.exclude_text:
        if not args.exclude_text.is_file():
            parser.error(f"ocr file not found: {args.exclude_text}")
        text_mask = load_text_mask(args.exclude_text, arr.shape[:2])

    queries: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for raw in args.q:
        try:
            q = parse_query(raw)
        except QueryError as exc:
            queries.append({"name": raw.split(":", 1)[0][:24], "type": "?", "args": ""})
            results.append({"summary": f"错误: {exc}", "error": str(exc)})
            continue
        queries.append(q)
        try:  # one bad path must not cost the other answers
            results.append(run_query(q, arr, args.image, canvas, text_mask))
        except Exception as exc:
            results.append({"summary": f"错误: {exc}", "error": str(exc)})

    width = max((len(q["name"]) for q in queries), default=4)
    width = max(4, min(28, width))
    for q, r in zip(queries, results):
        print(f"{q['name']:<{width}}  {q['type']:<11}  {r.get('summary', '')}")

    failures = sum(1 for r in results if "error" in r)
    if args.sheet:
        build_sheet(queries, results, source_img, args.sheet)
        print(f"\nsheet  {args.sheet}")
    if args.json:
        payload = [{"name": q["name"], "type": q["type"], **r} for q, r in zip(queries, results)]
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"json   {args.json}")
    if failures:
        print(f"\n{failures}/{len(results)} 个查询失败")
        if failures == len(results):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
