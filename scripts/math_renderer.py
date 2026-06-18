#!/usr/bin/env python3
"""Render LaTeX-like math snippets into clean inline SVG fragments.

The reconstruction manifest treats formulas as semantic elements. This module
turns each formula into vector paths so SVG and PPTX output preserve real
mathematical layout: stacked fractions, limits, Greek symbols, and scripts.

Matplotlib mathtext is the default local backend because it is available in the
bundled Python environment and does not need network access. It supports the
TeX subset used in most figure labels. The generated SVG is post-processed to
expand <use> glyph references into ordinary <path> elements so the native PPTX
converter can consume the result.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def normalize_latex(latex: str) -> str:
    """Return a mathtext-ready formula body without display delimiters."""
    text = latex.strip()
    if text.startswith("$$") and text.endswith("$$"):
        text = text[2:-2].strip()
    elif text.startswith("$") and text.endswith("$"):
        text = text[1:-1].strip()
    elif text.startswith(r"\(") and text.endswith(r"\)"):
        text = text[2:-2].strip()
    elif text.startswith(r"\[") and text.endswith(r"\]"):
        text = text[2:-2].strip()
    return text


def _collect_defs(root: ET.Element) -> dict[str, ET.Element]:
    defs: dict[str, ET.Element] = {}
    for elem in root.iter():
        if _local(elem.tag) == "path" and elem.get("id"):
            defs[elem.get("id", "")] = elem
    return defs


def _expand_uses(root: ET.Element) -> None:
    """Replace SVG <use> elements with cloned path elements.

    Matplotlib emits glyphs as <defs><path> plus <use>. Browsers render that
    fine, but the native DrawingML converter intentionally supports a small SVG
    subset. Expanding the references makes math formulas ordinary path groups.
    """
    defs = _collect_defs(root)

    def walk(parent: ET.Element) -> None:
        children = list(parent)
        for idx, child in enumerate(children):
            if _local(child.tag) == "use":
                href = (
                    child.get(f"{{{XLINK_NS}}}href")
                    or child.get("href")
                    or child.get("xlink:href")
                    or ""
                )
                ref_id = href[1:] if href.startswith("#") else href
                source = defs.get(ref_id)
                if source is not None:
                    clone = copy.deepcopy(source)
                    clone.attrib.pop("id", None)
                    style = child.get("style")
                    if style:
                        clone.set("style", style)
                    fill = child.get("fill")
                    if fill:
                        clone.set("fill", fill)
                    transforms = []
                    x = child.get("x")
                    y = child.get("y")
                    if x or y:
                        transforms.append(f"translate({float(x or 0):.6g} {float(y or 0):.6g})")
                    if child.get("transform"):
                        transforms.append(child.get("transform", ""))
                    if transforms:
                        clone.set("transform", " ".join(transforms))
                    parent.remove(child)
                    parent.insert(idx, clone)
                    continue
            walk(child)

    walk(root)


def _strip_nonvisual(root: ET.Element) -> None:
    """Remove metadata/defs/title nodes after glyph expansion."""
    for parent in root.iter():
        for child in list(parent):
            if _local(child.tag) in {"metadata", "defs", "title", "desc"}:
                parent.remove(child)


def _serialize_children(root: ET.Element) -> str:
    return "\n".join(ET.tostring(child, encoding="unicode") for child in list(root))


def render_math_fragment(
    latex: str,
    *,
    font_size: float = 24,
    fill: str = "#111111",
    dpi: int = 72,
) -> dict[str, Any]:
    """Render *latex* to an inline SVG fragment.

    Returns width, height, depth-ish metadata, and cleaned child SVG markup.
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.path import Path as MplPath
    from matplotlib.textpath import TextPath

    body = normalize_latex(latex)
    if not body:
        body = r"\ "
    math_text = f"${body}$"
    prop = FontProperties(family="DejaVu Serif")
    text_path = TextPath((0, 0), math_text, size=font_size, prop=prop, usetex=False)
    bbox = text_path.get_extents()
    min_x, min_y, max_x, max_y = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)

    commands: list[str] = []
    for vertices, code in text_path.iter_segments(curves=True, simplify=False):
        vals = list(vertices)

        def pt(index: int) -> tuple[float, float]:
            x_val = vals[index] - min_x
            y_val = max_y - vals[index + 1]
            return x_val, y_val

        if code == MplPath.MOVETO:
            x0, y0 = pt(0)
            commands.append(f"M {x0:.6g} {y0:.6g}")
        elif code == MplPath.LINETO:
            x0, y0 = pt(0)
            commands.append(f"L {x0:.6g} {y0:.6g}")
        elif code == MplPath.CURVE3:
            x0, y0 = pt(0)
            x1, y1 = pt(2)
            commands.append(f"Q {x0:.6g} {y0:.6g} {x1:.6g} {y1:.6g}")
        elif code == MplPath.CURVE4:
            x0, y0 = pt(0)
            x1, y1 = pt(2)
            x2, y2 = pt(4)
            commands.append(f"C {x0:.6g} {y0:.6g} {x1:.6g} {y1:.6g} {x2:.6g} {y2:.6g}")
        elif code == MplPath.CLOSEPOLY:
            commands.append("Z")

    path_data = " ".join(commands)
    svg = f'<path d="{html.escape(path_data, quote=True)}" fill="{html.escape(fill, quote=True)}"/>'
    view_box = f"0 0 {width:.6g} {height:.6g}"

    return {
        "latex": body,
        "width": width,
        "height": height,
        "viewBox": view_box,
        "svg": svg,
    }


def math_element_to_svg(el: dict[str, Any]) -> str:
    """Return an inline SVG <g> for a manifest math element."""
    latex = str(el.get("latex") or el.get("text") or "")
    font_size = float(el.get("font_size", 24))
    fill = str(el.get("fill", "#111111"))
    target_x = float(el.get("x", 0))
    target_y = float(el.get("y", 0))
    target_w = el.get("w")
    target_h = el.get("h")
    anchor = str(el.get("text_anchor", el.get("anchor", "start")))
    valign = str(el.get("dominant_baseline", el.get("valign", "middle")))

    rendered = render_math_fragment(latex, font_size=font_size, fill=fill)
    src_w = max(float(rendered["width"]), 1.0)
    src_h = max(float(rendered["height"]), 1.0)
    if target_w and target_h:
        scale = min(float(target_w) / src_w, float(target_h) / src_h)
    elif target_w:
        scale = float(target_w) / src_w
    elif target_h:
        scale = float(target_h) / src_h
    else:
        scale = 1.0

    out_w = src_w * scale
    out_h = src_h * scale
    x = target_x
    if anchor == "middle":
        x -= out_w / 2
    elif anchor == "end":
        x -= out_w
    y = target_y
    if valign in {"middle", "central"}:
        y -= out_h / 2
    elif valign in {"baseline", "text-after-edge"}:
        y -= out_h

    eid = html.escape(str(el.get("id", "")), quote=True)
    title = html.escape(latex, quote=False)
    digest = hashlib.sha1(latex.encode("utf-8")).hexdigest()[:10]
    return (
        f'<g id="{eid}" class="math formula" data-latex="{html.escape(latex, quote=True)}" '
        f'data-math-hash="{digest}" transform="translate({x:.6g} {y:.6g}) scale({scale:.8g})">'
        f"<title>{title}</title>"
        f'{rendered["svg"]}'
        "</g>"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("latex")
    parser.add_argument("--font-size", type=float, default=24)
    parser.add_argument("--fill", default="#111111")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = render_math_fragment(args.latex, font_size=args.font_size, fill=args.fill)
    if args.out:
        svg = (
            f'<svg xmlns="{SVG_NS}" width="{result["width"]}" height="{result["height"]}" '
            f'viewBox="{html.escape(result["viewBox"], quote=True)}">{result["svg"]}</svg>\n'
        )
        args.out.write_text(svg, encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "svg"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
