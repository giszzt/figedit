#!/usr/bin/env python3
"""Turn the source-vs-render difference into a per-element work queue.

A tile grid says "the region around 340,880 is wrong" and leaves the model to
work out which element that was -- another look, another round trip, once per
defect. Projecting the same difference onto each element's own box answers the
question directly: which id, how bad, and what kind of wrong.

Called by compose_svg_package.py at the end of the svg stage. Running it alone
is for re-reading a finished package without recomposing.

Usage:
  python scripts/fix_worklist.py source.png out/preview.png out/manifest.json \\
      --out out/diagnostics/fix_list.json --sheet out/diagnostics/fix_sheet.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# quality_checklist.md does not count antialiasing, stroke weight, sub-pixel
# baseline or colour-management drift as defects, and retyped text never matches
# the source pixel for pixel. A low threshold buries the real defects under
# those, so this sits well above them: at 12 the flagged items are differences
# a reader would notice.
MIN_DELTA = 12.0
# Figures differ in how closely a rebuild can ever match: a retyped, redrawn
# figure runs a higher baseline everywhere than a crop-heavy one. Flagging on an
# absolute number alone therefore floods on one kind of figure and stays silent
# on another. The bar is whichever is higher -- visible in absolute terms, or
# clearly worse than this figure's own baseline.
BASELINE_MULTIPLE = 2.0
LIST_LIMIT = 25
TOP_TILES = 12
CJK_FONTS = ("msyh.ttc", "simhei.ttf", "simsun.ttc")


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


def element_box(el: dict) -> list[int] | None:
    """Where the element claims to be, in source pixels."""
    sr = el.get("source_region")
    if isinstance(sr, dict) and sr.get("w") and sr.get("h"):
        return [int(sr["x"]), int(sr["y"]), int(sr["w"]), int(sr["h"])]
    x, y = el.get("x"), el.get("y")
    w, h = el.get("w"), el.get("h")
    if x is not None and y is not None and w and h:
        return [int(x), int(y), int(w), int(h)]
    if el.get("type") == "line" and el.get("x1") is not None:
        x1, y1 = float(el["x1"]), float(el["y1"])
        x2, y2 = float(el.get("x2", x1)), float(el.get("y2", y1))
        pad = 4
        return [int(min(x1, x2) - pad), int(min(y1, y2) - pad),
                int(abs(x2 - x1) + 2 * pad), int(abs(y2 - y1) + 2 * pad)]
    if el.get("type") == "text" and x is not None and y is not None and el.get("font_size"):
        fs = float(el["font_size"])
        text = el.get("text") or ""
        return [int(x), int(y - fs), max(8, int(len(text) * fs * 0.62)), int(fs * 1.4)]
    return None


def classify(source: np.ndarray, render: np.ndarray, delta: np.ndarray,
             box: list[int], el: dict) -> str:
    """Name the failure so the fix does not need another look."""
    x, y, w, h = box
    H, W = delta.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return "落在画布外"
    sub = delta[y0:y1, x0:x1]
    src = source[y0:y1, x0:x1].astype(float)
    ren = render[y0:y1, x0:x1].astype(float)

    src_ink = (np.abs(src - src.reshape(-1, 3).mean(axis=0)).sum(axis=2) > 40)
    ren_ink = (np.abs(ren - ren.reshape(-1, 3).mean(axis=0)).sum(axis=2) > 40)
    if src_ink.mean() > 0.04 and ren_ink.mean() < 0.005:
        return "整个没画出来"
    if ren_ink.mean() > 0.04 and src_ink.mean() < 0.005:
        return "源图这里是空的，多画了"

    inner = sub[max(1, sub.shape[0] // 4): -max(1, sub.shape[0] // 4) or None,
                max(1, sub.shape[1] // 4): -max(1, sub.shape[1] // 4) or None]
    if inner.size and sub.mean() > 0 and inner.mean() < 0.45 * sub.mean():
        return "位置偏了（误差集中在边缘）"

    if src_ink.any() and ren_ink.any():
        sw = float(src_ink.any(axis=0).sum())
        rw = float(ren_ink.any(axis=0).sum())
        sh = float(src_ink.any(axis=1).sum())
        rh = float(ren_ink.any(axis=1).sum())
        is_text = el.get("type") == "text"
        if sw > 0 and rw / sw > 1.12:
            return "字号偏大" if is_text else "画宽了"
        if sw > 0 and rw / sw < 0.88:
            return "字号偏小" if is_text else "画窄了"
        if sh > 0 and rh / sh > 1.15:
            return "画高了"
        if sh > 0 and rh / sh < 0.85:
            return "画矮了"

    if src_ink.mean() > 0.02 and abs(src_ink.mean() - ren_ink.mean()) < 0.02:
        return "形状对得上，颜色不符"
    return "对不上，原因待查"


def build(source_path: Path, preview_path: Path, manifest_path: Path) -> dict[str, Any]:
    source_img = Image.open(source_path).convert("RGB")
    preview = Image.open(preview_path).convert("RGB")
    if preview.size != source_img.size:
        preview = preview.resize(source_img.size, Image.LANCZOS)
    source = np.asarray(source_img)
    render = np.asarray(preview)
    delta = np.sqrt(((srgb_to_lab(source.astype(float)) - srgb_to_lab(render.astype(float))) ** 2).sum(axis=2))

    baseline = float(delta.mean())
    threshold = max(MIN_DELTA, BASELINE_MULTIPLE * baseline)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = []
    for el in manifest.get("elements", []) or []:
        box = element_box(el)
        if not box or box[2] < 4 or box[3] < 4:
            continue
        x, y, w, h = box
        H, W = delta.shape
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            continue
        sub = delta[y0:y1, x0:x1]
        mean = float(sub.mean())
        if mean < threshold:
            continue
        items.append({
            "id": el.get("id", "?"),
            "type": el.get("type"),
            "bbox": box,
            "mean_delta_e": round(mean, 1),
            "p95_delta_e": round(float(np.percentile(sub, 95)), 1),
            "times_baseline": round(mean / baseline, 1) if baseline > 0.1 else None,
            "hint": classify(source, render, delta, box, el),
        })
    items.sort(key=lambda i: -i["mean_delta_e"])
    return {
        "source": str(source_path),
        "preview": str(preview_path),
        "checked": len(manifest.get("elements", []) or []),
        "flagged": len(items),
        "baseline_delta_e": round(baseline, 2),
        "threshold": round(threshold, 1),
        "items": items[:LIST_LIMIT],
        "truncated": max(0, len(items) - LIST_LIMIT),
    }


def draw_sheet(report: dict[str, Any], out: Path) -> None:
    """Source above, render below, for the worst offenders -- one look, not twelve."""
    items = report["items"][:TOP_TILES]
    if not items:
        return
    source = Image.open(report["source"]).convert("RGB")
    preview = Image.open(report["preview"]).convert("RGB")
    if preview.size != source.size:
        preview = preview.resize(source.size, Image.LANCZOS)
    cell_w, strip_h = 250, 110
    cols = 4
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * (strip_h * 2 + 40) + 8), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        ox, oy = c * cell_w, r * (strip_h * 2 + 40) + 4
        x, y, w, h = it["bbox"]
        pad = 6
        crop_box = (max(0, x - pad), max(0, y - pad),
                    min(source.width, x + w + pad), min(source.height, y + h + pad))
        for k, img in enumerate((source, preview)):
            tile = img.crop(crop_box)
            tile.thumbnail((cell_w - 14, strip_h), Image.LANCZOS)
            sheet.paste(tile, (ox + 7, oy + k * strip_h + (strip_h - tile.height) // 2))
        draw.line([ox + 7, oy + strip_h, ox + cell_w - 7, oy + strip_h], fill=(215, 215, 215))
        draw.text((ox + 7, oy + 2 * strip_h + 3), f"{it['id']}  ΔE {it['mean_delta_e']}", fill=(20, 20, 20), font=font)
        draw.text((ox + 7, oy + 2 * strip_h + 20), it["hint"][:20], fill=(150, 50, 50), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def print_digest(report: dict[str, Any], sheet: Path | None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    items = report["items"]
    base = report["baseline_delta_e"]
    thr = report["threshold"]
    if not items:
        print(f"差异工单   {report['checked']} 个元素没有一个超过 ΔE {thr}（全图基线 {base}），没有要改的")
        return
    print(f"差异工单   {report['flagged']}/{report['checked']} 个元素超过 ΔE {thr}"
          f"（全图基线 {base}，门槛取基线 2 倍与 {MIN_DELTA} 的较大者），按误差排序：")
    for it in items[:10]:
        mult = f"{it['times_baseline']}x" if it.get("times_baseline") else ""
        print(f"  {str(it['id']):24s} {str(it['type'] or ''):8s} ΔE{it['mean_delta_e']:<6} {mult:<6} {it['hint']}")
    rest = (len(items) - 10) + report.get("truncated", 0)
    if rest > 0:
        print(f"  …… 还有 {rest} 个，见 fix_list.json")
    print("\n改法：把修正写进 manifest 再重跑 compose，不要逐个手改 JSON。")
    if sheet:
        print(f"\n对照图 {sheet}   上为源图下为成品，一次看完再动手改")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("preview", type=Path)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    report = build(args.source, args.preview, args.manifest)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.sheet:
        draw_sheet(report, args.sheet)
    if not args.quiet:
        print_digest(report, args.sheet if args.sheet else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
