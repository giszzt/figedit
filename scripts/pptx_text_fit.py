#!/usr/bin/env python3
"""Report text risks that can change when SVG text becomes PowerPoint text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import ImageFont

from build_svg_from_manifest import resolve_font_family


def _font_path(family: str) -> str:
    try:
        from matplotlib import font_manager  # type: ignore

        return font_manager.findfont(family, fallback_to_default=True)
    except Exception:
        return str(Path("C:/Windows/Fonts/arial.ttf"))


def _font_and_coverage(family: str, size: int) -> tuple[ImageFont.FreeTypeFont, str, set[int] | None]:
    path = _font_path(family)
    font = ImageFont.truetype(path, size=max(1, size))
    cmap: set[int] | None = None
    try:
        from fontTools.ttLib import TTFont  # type: ignore

        tt = TTFont(path, lazy=True)
        cmap = set()
        for table in tt["cmap"].tables:
            cmap.update(table.cmap.keys())
        tt.close()
    except Exception:
        pass
    return font, path, cmap


def _rect(element: dict[str, Any]) -> tuple[float, float, float, float] | None:
    box = element
    if not all(key in box for key in ("x", "y", "w", "h")):
        candidate = element.get("source_region") or element.get("source_bbox")
        box = candidate if isinstance(candidate, dict) else element
    if not all(key in box for key in ("x", "y", "w", "h")):
        return None
    x, y, w, h = [float(box.get(key, 0)) for key in ("x", "y", "w", "h")]
    return x, y, x + w, y + h


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def audit(manifest: dict[str, Any]) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    elements = manifest.get("elements", [])
    # Panel/background rectangles are expected to contain text, so treating
    # them as collisions creates noise. Only content-bearing neighbors matter.
    collision_types = {"image", "math", "formula"}
    neighbors = [(el.get("id"), _rect(el)) for el in elements if el.get("type") in collision_types]
    for element in elements:
        if element.get("type") != "text":
            continue
        text_lines = element.get("lines") or [element.get("text", "")]
        lines = [str(line) for line in text_lines]
        resolved_family = resolve_font_family(element.get("font_family") or "var(--font-sans)")
        family = resolved_family.split(",")[0].strip().strip("'\"")
        size = max(1, int(round(float(element.get("font_size", 16)))))
        font, font_path, cmap = _font_and_coverage(family, size)
        widths = [float(font.getlength(line)) for line in lines]
        ink_heights = []
        for line in lines:
            bbox = font.getbbox(line or " ")
            ink_heights.append(float(max(1, bbox[3] - bbox[1])))
        predicted_height = sum(ink_heights) + max(0, len(lines) - 1) * size * 0.2
        slot = element if element.get("w") and element.get("h") else (element.get("source_region") or element.get("source_bbox") or {})
        box_w = float(slot.get("w", 0) or 0)
        box_h = float(slot.get("h", 0) or 0)
        reasons: list[str] = []
        width_tolerance = max(2.0, size * 0.15)
        height_tolerance = max(2.0, size * 0.2)
        if box_w > 0 and widths and max(widths) > box_w + width_tolerance:
            reasons.append("predicted line width exceeds text box")
        if box_h > 0 and predicted_height > box_h + height_tolerance:
            reasons.append("predicted line height exceeds text box")
        missing = sorted({char for line in lines for char in line if cmap is not None and ord(char) not in cmap})
        if missing:
            reasons.append("font lacks glyphs and PowerPoint may fall back")
        rect = _rect(element)
        collisions = []
        if rect:
            for neighbor_id, neighbor_rect in neighbors:
                if neighbor_rect:
                    overlap = _overlap(rect, neighbor_rect)
                    text_area = max(1.0, (rect[2] - rect[0]) * (rect[3] - rect[1]))
                    if overlap / text_area >= 0.2:
                        collisions.append(neighbor_id)
            if collisions:
                reasons.append("declared text box overlaps non-text elements")
        if reasons:
            risks.append(
                {
                    "id": element.get("id"),
                    "reasons": reasons,
                    "font_family": family,
                    "font_file": font_path,
                    "max_line_width": round(max(widths, default=0.0), 3),
                    "box_width": box_w or None,
                    "predicted_text_height": round(predicted_height, 3),
                    "box_height": box_h or None,
                    "missing_glyphs": missing[:30],
                    "collisions": collisions[:30],
                }
            )
    math_count = sum(1 for element in elements if element.get("type") in {"math", "formula"})
    return {
        "status": "review" if risks else "ok",
        "risk_count": len(risks),
        "math_count": math_count,
        "recommended_validation_tier": "pptx-triggered" if risks or math_count else "svg-primary",
        "risks": risks,
        "blind_spots": ["Office Math layout", "rotated text", "PowerPoint theme substitution outside the resolved font stack"],
        "note": "Report-only. Do not shrink text merely to make this advisory report green.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
