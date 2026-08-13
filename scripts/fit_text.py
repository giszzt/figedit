#!/usr/bin/env python3
"""Fit editable text into measured source slots using the actual font file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import ImageFont


def _font_path(family: str) -> str:
    try:
        from matplotlib import font_manager  # type: ignore

        return font_manager.findfont(family, fallback_to_default=True)
    except Exception:
        return str(Path("C:/Windows/Fonts/arial.ttf"))


def _measure(text: str, font_path: str, size: int) -> tuple[float, float, tuple[int, int, int, int]]:
    font = ImageFont.truetype(font_path, size=size)
    bbox = font.getbbox(text or " ")
    return float(bbox[2] - bbox[0]), float(bbox[3] - bbox[1]), bbox


def fit_item(item: dict[str, Any]) -> dict[str, Any]:
    box = item.get("source_region") or item.get("box") or item
    x, y, w, h = [float(box.get(key, 0)) for key in ("x", "y", "w", "h")]
    inset = max(0.0, float(item.get("inset", 0)))
    x, y, w, h = x + inset, y + inset, max(1.0, w - 2 * inset), max(1.0, h - 2 * inset)
    family = str(item.get("font_family") or "Arial").split(",")[0].strip().strip("'\"")
    font_path = _font_path(family)
    text = str(item.get("text") or "")
    min_size = max(1, int(item.get("min_font_size", 4)))
    max_size = max(min_size, int(item.get("max_font_size", max(6, round(h * 1.5)))))
    low, high, best = min_size, max_size, min_size
    while low <= high:
        size = (low + high) // 2
        tw, th, _ = _measure(text, font_path, size)
        if tw <= w and th <= h:
            best = size
            low = size + 1
        else:
            high = size - 1
    tw, th, bbox = _measure(text, font_path, best)
    anchor = str(item.get("text_anchor") or "middle")
    if anchor == "start":
        text_x = x
    elif anchor == "end":
        text_x = x + w
    else:
        text_x = x + w / 2
    baseline_y = y + (h - th) / 2 - bbox[1]
    return {
        "id": item.get("id"),
        "text": text,
        "font_family": family,
        "font_file": font_path,
        "font_size": best,
        "x": round(text_x, 3),
        "baseline_y": round(baseline_y, 3),
        "text_anchor": anchor,
        "slot": {"x": x, "y": y, "w": w, "h": h},
        "measured": {"w": round(tw, 3), "h": round(th, 3)},
        "residual": {"w": round(w - tw, 3), "h": round(h - th, 3)},
        "status": "ok" if tw <= w and th <= h else "review",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("items", type=Path, help="JSON array or object with an items array")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.items.read_text(encoding="utf-8"))
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        parser.error("input must be a JSON array or object with an items array")
    result = {"items": [fit_item(item) for item in items if isinstance(item, dict)]}
    result["review_count"] = sum(1 for item in result["items"] if item["status"] != "ok")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    items_out = result["items"]
    review = [i for i in items_out if i["status"] != "ok"]
    print(f"文字 {len(items_out)} 条    需复核 {len(review)} 条")
    if review:
        print("\n放不下的，按溢出量排序：")
        for item in sorted(review, key=lambda i: min(i["residual"]["w"], i["residual"]["h"]))[:15]:
            print(
                f"  {str(item.get('id', '?')):24s} 字号 {item['font_size']:<5} "
                f"槽 {item['slot']['w']}x{item['slot']['h']}  实测 {item['measured']['w']:.0f}x{item['measured']['h']:.0f}  "
                f"余量 w{item['residual']['w']:+.0f} h{item['residual']['h']:+.0f}"
            )
    print(f"\n报告 {args.out}    直接喂 manifest_edit.py --apply-fit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
