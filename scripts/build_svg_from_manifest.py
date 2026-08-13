#!/usr/bin/env python3
"""Build a basic editable SVG from a reconstruction manifest.

This script is a starter generator. It supports common SVG primitives and should be
extended or hand-edited for complex diagrams.

Usage:
  python scripts/build_svg_from_manifest.py manifest.json --out editable.svg
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

from math_renderer import math_element_to_svg


FONT_STACKS = {
    "--font-sans": ["Inter", "Arial", "Helvetica", "Microsoft YaHei", "Noto Sans CJK SC", "sans-serif"],
    "--font-serif": ["Georgia", "Times New Roman", "Noto Serif CJK SC", "serif"],
    "--font-hand": ["Comic Sans MS", "Comic Neue", "Arial Rounded MT Bold", "Microsoft YaHei", "sans-serif"],
}
GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
MARKER_STYLES = {"solid-triangle", "open-chevron", "circle", "diamond"}
_WARNED_FONT_VALUES: set[str] = set()


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def style_attrs(el: Dict[str, Any]) -> str:
    attrs = []
    for key, svg_key in [
        ("fill", "fill"),
        ("stroke", "stroke"),
        ("stroke_width", "stroke-width"),
        ("dasharray", "stroke-dasharray"),
        ("opacity", "opacity"),
    ]:
        if key in el:
            attrs.append(f'{svg_key}="{esc(el[key])}"')
    return " ".join(attrs)


def transform_attr(el: Dict[str, Any]) -> str:
    if "transform" not in el:
        return ""
    return f'transform="{esc(el["transform"])}"'


@lru_cache(maxsize=1)
def _installed_font_names() -> set[str]:
    names: set[str] = set()
    try:
        from matplotlib import font_manager  # type: ignore

        names.update(font.name.casefold() for font in font_manager.fontManager.ttflist if font.name)
    except Exception:
        pass
    try:
        import winreg  # type: ignore

        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            index = 0
            while True:
                try:
                    value_name, _, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", str(value_name)).strip()
                if cleaned:
                    names.add(cleaned.casefold())
                index += 1
    except Exception:
        pass
    return names


def _quote_font(font: str) -> str:
    return font if font in GENERIC_FONTS or " " not in font else f'"{font}"'


def resolve_font_family(value: Any) -> str:
    """Expand CSS font variables and put an installed family first."""

    raw = str(value or "var(--font-sans)").strip()
    match = re.fullmatch(r"var\(\s*(--font-[a-z0-9-]+)\s*\)", raw, flags=re.I)
    if match:
        fonts = list(FONT_STACKS.get(match.group(1).lower(), FONT_STACKS["--font-sans"]))
    else:
        fonts = [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]
    if not fonts:
        fonts = list(FONT_STACKS["--font-sans"])

    installed = _installed_font_names()
    chosen = next((font for font in fonts if font.casefold() in installed and font not in GENERIC_FONTS), None)
    if chosen is None:
        chosen = next((font for font in fonts if font not in GENERIC_FONTS), "Segoe UI")
        if raw not in _WARNED_FONT_VALUES:
            print(f"WARNING: no installed font found for {raw!r}; keeping first declared family {chosen!r}", file=sys.stderr)
            _WARNED_FONT_VALUES.add(raw)
    ordered = [chosen] + [font for font in fonts if font != chosen]
    return ", ".join(_quote_font(font) for font in ordered)


def _normalize_marker_spec(el: Dict[str, Any], field: str) -> Dict[str, Any] | None:
    spec = el.get(field)
    legacy = field == "marker_end" and el.get("arrow_end") or field == "marker_start" and el.get("arrow_start")
    if spec is None and legacy:
        spec = {"style": "solid-triangle", "size": 7}
    if not isinstance(spec, dict):
        return None
    style = str(spec.get("style", "solid-triangle"))
    if style not in MARKER_STYLES:
        style = "solid-triangle"
    try:
        size = max(1.0, float(spec.get("size", 7)))
    except Exception:
        size = 7.0
    return {**spec, "style": style, "size": size}


def _marker_id(spec: Dict[str, Any]) -> str:
    size = float(spec["size"])
    size_token = str(int(size)) if size.is_integer() else str(size).replace(".", "p")
    return f"marker-{spec['style']}-{size_token}"


def make_marker_defs(elements: Iterable[Dict[str, Any]]) -> str:
    specs: Dict[str, Dict[str, Any]] = {}
    for el in elements:
        for field in ("marker_start", "marker_end"):
            spec = _normalize_marker_spec(el, field)
            if spec:
                specs[_marker_id(spec)] = spec
    # Legacy definitions remain for hand-authored SVG compatibility.
    specs.setdefault("arrow-end", {"style": "solid-triangle", "size": 7.0})
    specs.setdefault("arrow-start", {"style": "solid-triangle", "size": 7.0})

    lines = ["  <defs>"]
    for marker_id, spec in specs.items():
        size = spec["size"]
        style = spec["style"]
        lines.append(
            f'    <marker id="{esc(marker_id)}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="{size:g}" markerHeight="{size:g}" markerUnits="userSpaceOnUse" orient="auto-start-reverse">'
        )
        if style == "open-chevron":
            lines.append('      <polyline points="1,1 9,5 1,9" fill="none" stroke="context-stroke" stroke-width="1.6"/>')
        elif style == "circle":
            lines.append('      <circle cx="5" cy="5" r="4" fill="context-stroke"/>')
        elif style == "diamond":
            lines.append('      <polygon points="1,5 5,1 9,5 5,9" fill="context-stroke"/>')
        else:
            lines.append('      <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/>')
        lines.append("    </marker>")
    lines.append("  </defs>")
    return "\n".join(lines)


def marker_attrs(el: Dict[str, Any]) -> str:
    out = []
    end_spec = _normalize_marker_spec(el, "marker_end")
    start_spec = _normalize_marker_spec(el, "marker_start")
    if end_spec:
        out.append(f'marker-end="url(#{_marker_id(end_spec)})"')
    if start_spec:
        out.append(f'marker-start="url(#{_marker_id(start_spec)})"')
    return " ".join(out)


def _parse_points(value: Any) -> list[tuple[float, float]]:
    nums = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))]
    return list(zip(nums[0::2], nums[1::2]))


def _point_on_polyline(points: list[tuple[float, float]], at: float) -> tuple[float, float, float] | None:
    if len(points) < 2:
        return None
    segments = []
    total = 0.0
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        segments.append((a, b, length))
        total += length
    if total <= 0:
        return None
    target = min(1.0, max(0.0, at)) * total
    walked = 0.0
    for index, (a, b, length) in enumerate(segments):
        if walked + length >= target or index == len(segments) - 1:
            ratio = 0.0 if length == 0 else (target - walked) / length
            x = a[0] + (b[0] - a[0]) * ratio
            y = a[1] + (b[1] - a[1]) * ratio
            angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            return x, y, angle
        walked += length
    return None


def _adjust_connector(el: Dict[str, Any]) -> Dict[str, Any]:
    try:
        clearance = max(0.0, float(el.get("connector_clearance", 0)))
    except Exception:
        clearance = 0.0
    if clearance <= 0:
        return el
    out = dict(el)
    if el.get("type") == "line":
        x1, y1 = float(el.get("x1", 0)), float(el.get("y1", 0))
        x2, y2 = float(el.get("x2", 0)), float(el.get("y2", 0))
        length = math.hypot(x2 - x1, y2 - y1)
        if length > 2 * clearance:
            ux, uy = (x2 - x1) / length, (y2 - y1) / length
            out.update({"x1": x1 + ux * clearance, "y1": y1 + uy * clearance, "x2": x2 - ux * clearance, "y2": y2 - uy * clearance})
    elif el.get("type") == "polyline":
        points = _parse_points(el.get("points"))
        if len(points) >= 2:
            def move(a: tuple[float, float], b: tuple[float, float], distance: float) -> tuple[float, float]:
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                if length <= distance or length == 0:
                    return a
                return a[0] + (b[0] - a[0]) * distance / length, a[1] + (b[1] - a[1]) * distance / length
            points[0] = move(points[0], points[1], clearance)
            points[-1] = move(points[-1], points[-2], clearance)
            out["points"] = " ".join(f"{x:g},{y:g}" for x, y in points)
    return out


def _mid_marker_svg(el: Dict[str, Any]) -> str:
    spec = _normalize_marker_spec(el, "marker_mid")
    if not spec:
        return ""
    typ = el.get("type")
    if typ == "line":
        points = [(float(el.get("x1", 0)), float(el.get("y1", 0))), (float(el.get("x2", 0)), float(el.get("y2", 0)))]
    elif typ == "polyline":
        points = _parse_points(el.get("points"))
    elif typ == "path":
        points = [(float(x), float(y)) for x, y in re.findall(r"[MLml]\s*(-?\d+(?:\.\d+)?)\s*[ ,]\s*(-?\d+(?:\.\d+)?)", str(el.get("d", "")))]
    else:
        return ""
    point = _point_on_polyline(points, float(spec.get("at", 0.5)))
    if point is None:
        return ""
    x, y, angle = point
    size = float(spec["size"])
    half = size / 2.0
    stroke = esc(el.get("stroke", "#111"))
    eid = esc(f"{el.get('id', 'connector')}-marker-mid")
    transform = f'rotate({angle:g} {x:g} {y:g})'
    style = spec["style"]
    if style == "circle":
        return f'<circle id="{eid}" cx="{x:g}" cy="{y:g}" r="{half:g}" fill="{stroke}"/>'
    if style == "diamond":
        pts = f"{x-half:g},{y:g} {x:g},{y-half:g} {x+half:g},{y:g} {x:g},{y+half:g}"
        return f'<polygon id="{eid}" points="{pts}" fill="{stroke}" transform="{transform}"/>'
    pts = f"{x-half:g},{y-half:g} {x+half:g},{y:g} {x-half:g},{y+half:g}"
    if style == "open-chevron":
        return f'<polyline id="{eid}" points="{pts}" fill="none" stroke="{stroke}" stroke-width="1.6" transform="{transform}"/>'
    return f'<polygon id="{eid}" points="{pts}" fill="{stroke}" transform="{transform}"/>'


def text_element(el: Dict[str, Any]) -> str:
    x = el.get("x", 0)
    y = el.get("y", 0)
    fs = el.get("font_size", 16)
    fw = el.get("font_weight", "400")
    ff = resolve_font_family(el.get("font_family", "var(--font-sans)"))
    fill = el.get("fill", "#111")
    anchor = el.get("text_anchor", "middle")
    lines = el.get("lines") or [el.get("text", "")]
    tspans = []
    line_gap = float(fs) * 1.25
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_gap
        tspans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    transform = transform_attr(el)
    return (
        f'<text id="{esc(el.get("id", ""))}" x="{x}" y="{y}" '
        f'font-family="{esc(ff)}" font-size="{fs}" font-weight="{esc(fw)}" '
        f'fill="{esc(fill)}" text-anchor="{esc(anchor)}" {transform}>'
        + "".join(tspans)
        + "</text>"
    )


def element_to_svg(el: Dict[str, Any], asset_by_id: Dict[str, Dict[str, Any]]) -> str:
    el = _adjust_connector(el)
    typ = el["type"]
    eid = esc(el.get("id", ""))
    extra = style_attrs(el)
    marker = marker_attrs(el)
    transform = transform_attr(el)

    if typ == "rect":
        return f'<rect id="{eid}" x="{el.get("x",0)}" y="{el.get("y",0)}" width="{el.get("w",0)}" height="{el.get("h",0)}" rx="{el.get("rx",0)}" ry="{el.get("ry",el.get("rx",0))}" {extra} {transform}/>'
    if typ == "line":
        base = f'<line id="{eid}" x1="{el.get("x1",0)}" y1="{el.get("y1",0)}" x2="{el.get("x2",0)}" y2="{el.get("y2",0)}" {extra} {marker} {transform}/>'
        mid = _mid_marker_svg(el)
        return base + ("\n    " + mid if mid else "")
    if typ == "path":
        base = f'<path id="{eid}" d="{esc(el.get("d",""))}" {extra} {marker} {transform}/>'
        mid = _mid_marker_svg(el)
        return base + ("\n    " + mid if mid else "")
    if typ == "polyline":
        base = f'<polyline id="{eid}" points="{esc(el.get("points",""))}" {extra} {marker} {transform}/>'
        mid = _mid_marker_svg(el)
        return base + ("\n    " + mid if mid else "")
    if typ == "polygon":
        return f'<polygon id="{eid}" points="{esc(el.get("points",""))}" {extra} {transform}/>'
    if typ == "circle":
        return f'<circle id="{eid}" cx="{el.get("x",0)}" cy="{el.get("y",0)}" r="{el.get("r",0)}" {extra} {transform}/>'
    if typ == "ellipse":
        return f'<ellipse id="{eid}" cx="{el.get("x",0)}" cy="{el.get("y",0)}" rx="{el.get("rx",0)}" ry="{el.get("ry",0)}" {extra} {transform}/>'
    if typ == "text":
        return text_element(el)
    if typ in {"math", "formula"}:
        return math_element_to_svg(el)
    if typ == "image":
        href = el.get("href")
        if not href and el.get("asset_id") in asset_by_id:
            href = asset_by_id[el["asset_id"]]["file"]
        preserve = el.get("preserve_aspect_ratio", "xMidYMid meet")
        return f'<image id="{eid}" href="{esc(href or "")}" x="{el.get("x",0)}" y="{el.get("y",0)}" width="{el.get("w",0)}" height="{el.get("h",0)}" preserveAspectRatio="{esc(preserve)}" {transform}/>'
    return f'<!-- Unsupported element type: {esc(typ)} id={eid} -->'


def build_svg(manifest: Dict[str, Any]) -> str:
    canvas = manifest["canvas"]
    w = canvas["width"]
    h = canvas["height"]
    bg = canvas.get("background", "#ffffff")
    asset_by_id = {a["id"]: a for a in manifest.get("assets", [])}

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append(make_marker_defs(manifest.get("elements", [])))
    parts.append("""
  <style>
    :root {
      --font-sans: "Inter", "Arial", "Helvetica", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
      --font-serif: "Georgia", "Times New Roman", "Noto Serif CJK SC", serif;
      --font-hand: "Comic Sans MS", "Comic Neue", "Arial Rounded MT Bold", "Microsoft YaHei", sans-serif;
    }
  </style>
""".rstrip())
    parts.append(f'  <rect id="canvas-background" x="0" y="0" width="{w}" height="{h}" fill="{esc(bg)}"/>')

    groups = {
        "background": [],
        "assets": [],
        "panels": [],
        "sections": [],
        "icons": [],
        "connectors": [],
        "texts": [],
        "annotations": [],
    }

    background_plans = manifest.get("background_plans")
    if not isinstance(background_plans, list):
        legacy_plan = manifest.get("background_plan")
        background_plans = [legacy_plan] if isinstance(legacy_plan, dict) else []
    background_plate_ids = set()
    for index, background_plan in enumerate(plan for plan in background_plans if isinstance(plan, dict)):
        plate_asset_id = background_plan.get("plate_asset_id")
        plate_file = background_plan.get("plate_file")
        if not (plate_asset_id or plate_file):
            continue
        if plate_asset_id:
            background_plate_ids.add(plate_asset_id)
        region = background_plan.get("source_region") or {}
        plate = {
            "type": "image",
            "id": f"background-plate-{background_plan.get('scope_id') or index}",
            "asset_id": plate_asset_id,
            "href": plate_file,
            "x": region.get("x", 0),
            "y": region.get("y", 0),
            "w": region.get("w", w),
            "h": region.get("h", h),
            "preserve_aspect_ratio": "none",
        }
        groups["background"].append("    " + element_to_svg(plate, asset_by_id))

    for el in manifest.get("elements", []):
        typ = el.get("type")
        if typ == "image" and el.get("asset_id") in background_plate_ids:
            continue
        cls = el.get("class", "")
        explicit_layer = el.get("layer")
        if explicit_layer in groups:
            key = explicit_layer
        elif typ == "image":
            key = "assets"
        elif typ == "text":
            key = "texts"
        elif typ in {"math", "formula"}:
            key = "texts"
        elif typ in ("line", "path", "polyline"):
            key = "connectors"
        elif "panel" in cls or (typ == "rect" and el.get("panel_id") is None):
            key = "panels"
        elif typ in ("circle", "ellipse", "polygon"):
            key = "icons"
        else:
            key = "sections"
        groups[key].append("    " + element_to_svg(el, asset_by_id))

    group_order = ["background", "assets", "panels", "connectors", "sections", "icons", "texts", "annotations"]
    for gid in group_order:
        lines = groups.get(gid, [])
        if not lines:
            continue
        parts.append(f'  <g id="{gid}">')
        parts.extend(lines)
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("editable.svg"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    svg = build_svg(manifest)
    args.out.write_text(svg, encoding="utf-8")
    print(f"SVG written to: {args.out}")


if __name__ == "__main__":
    main()
