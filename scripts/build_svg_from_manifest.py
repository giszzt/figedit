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
from pathlib import Path
from typing import Any, Dict, Iterable, List

from math_renderer import math_element_to_svg


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


def make_marker_defs() -> str:
    return """
  <defs>
    <marker id="arrow-end" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/>
    </marker>
    <marker id="arrow-start" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 10 0 L 0 5 L 10 10 z" fill="context-stroke"/>
    </marker>
  </defs>
""".rstrip()


def marker_attrs(el: Dict[str, Any]) -> str:
    out = []
    if el.get("arrow_end"):
        out.append('marker-end="url(#arrow-end)"')
    if el.get("arrow_start"):
        out.append('marker-start="url(#arrow-start)"')
    return " ".join(out)


def text_element(el: Dict[str, Any]) -> str:
    x = el.get("x", 0)
    y = el.get("y", 0)
    fs = el.get("font_size", 16)
    fw = el.get("font_weight", "400")
    ff = el.get("font_family", "var(--font-sans)")
    fill = el.get("fill", "#111")
    anchor = el.get("text_anchor", "middle")
    lines = el.get("lines") or [el.get("text", "")]
    tspans = []
    line_gap = float(fs) * 1.25
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else line_gap
        tspans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return (
        f'<text id="{esc(el.get("id", ""))}" x="{x}" y="{y}" '
        f'font-family="{esc(ff)}" font-size="{fs}" font-weight="{esc(fw)}" '
        f'fill="{esc(fill)}" text-anchor="{esc(anchor)}">'
        + "".join(tspans)
        + "</text>"
    )


def element_to_svg(el: Dict[str, Any], asset_by_id: Dict[str, Dict[str, Any]]) -> str:
    typ = el["type"]
    eid = esc(el.get("id", ""))
    extra = style_attrs(el)
    marker = marker_attrs(el)

    if typ == "rect":
        return f'<rect id="{eid}" x="{el.get("x",0)}" y="{el.get("y",0)}" width="{el.get("w",0)}" height="{el.get("h",0)}" rx="{el.get("rx",0)}" ry="{el.get("ry",el.get("rx",0))}" {extra}/>'
    if typ == "line":
        return f'<line id="{eid}" x1="{el.get("x1",0)}" y1="{el.get("y1",0)}" x2="{el.get("x2",0)}" y2="{el.get("y2",0)}" {extra} {marker}/>'
    if typ == "path":
        return f'<path id="{eid}" d="{esc(el.get("d",""))}" {extra} {marker}/>'
    if typ == "polyline":
        return f'<polyline id="{eid}" points="{esc(el.get("points",""))}" {extra} {marker}/>'
    if typ == "polygon":
        return f'<polygon id="{eid}" points="{esc(el.get("points",""))}" {extra}/>'
    if typ == "circle":
        return f'<circle id="{eid}" cx="{el.get("x",0)}" cy="{el.get("y",0)}" r="{el.get("r",0)}" {extra}/>'
    if typ == "ellipse":
        return f'<ellipse id="{eid}" cx="{el.get("x",0)}" cy="{el.get("y",0)}" rx="{el.get("rx",0)}" ry="{el.get("ry",0)}" {extra}/>'
    if typ == "text":
        return text_element(el)
    if typ in {"math", "formula"}:
        return math_element_to_svg(el)
    if typ == "image":
        href = el.get("href")
        if not href and el.get("asset_id") in asset_by_id:
            href = asset_by_id[el["asset_id"]]["file"]
        return f'<image id="{eid}" href="{esc(href or "")}" x="{el.get("x",0)}" y="{el.get("y",0)}" width="{el.get("w",0)}" height="{el.get("h",0)}" preserveAspectRatio="xMidYMid meet"/>'
    return f'<!-- Unsupported element type: {esc(typ)} id={eid} -->'


def build_svg(manifest: Dict[str, Any]) -> str:
    canvas = manifest["canvas"]
    w = canvas["width"]
    h = canvas["height"]
    bg = canvas.get("background", "#ffffff")
    asset_by_id = {a["id"]: a for a in manifest.get("assets", [])}

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    parts.append(make_marker_defs())
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

    for el in manifest.get("elements", []):
        typ = el.get("type")
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

    group_order = ["background", "assets", "panels", "sections", "icons", "connectors", "texts", "annotations"]
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
