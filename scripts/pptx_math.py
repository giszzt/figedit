#!/usr/bin/env python3
"""Inject editable Office Math equations into generated PPTX files.

The SVG package keeps formula elements as vector paths for browser fidelity.
PowerPoint needs a different representation: editable equations are serialized
as Office Math (OMML) inside DrawingML text bodies. This module converts
manifest LaTeX to MathML, transforms MathML to OMML with Microsoft's Office XSL,
and appends equation shapes to the PPTX slide XML.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from lxml import etree

from math_renderer import normalize_latex  # type: ignore


EMU_PER_PX = 9525
FONT_PX_TO_HUNDREDTHS_PT = 75

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"

NS = {"p": P_NS, "a": A_NS, "m": M_NS, "mc": MC_NS, "a14": A14_NS}


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _office_xsl_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get("MML2OMML_XSL")
    if env_path:
        candidates.append(Path(env_path))

    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]
    for root in roots:
        if not root:
            continue
        base = Path(root)
        candidates.extend(
            [
                base / "Microsoft Office" / "root" / "Office16" / "MML2OMML.XSL",
                base / "Microsoft Office" / "Office16" / "MML2OMML.XSL",
                base / "Microsoft Office" / "Office15" / "MML2OMML.XSL",
                base / "Microsoft Office" / "Office14" / "MML2OMML.XSL",
            ]
        )

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path).lower()
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def find_mml2omml_xsl() -> Path | None:
    """Return the installed Microsoft MathML-to-OMML transform, if present."""
    for path in _office_xsl_candidates():
        if path.exists():
            return path
    return None


def _hex_color(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.lower() in {"none", "transparent"}:
        return None
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        text = "".join(ch * 2 for ch in text)
    if len(text) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return text.upper()
    return None


def latex_to_omml_para(latex: str, *, font_size_px: float = 24, fill: str = "#111111") -> etree._Element:
    """Convert one LaTeX formula body to an editable OMML paragraph element."""
    try:
        from latex2mathml.converter import convert as latex_to_mathml
    except ImportError as exc:  # pragma: no cover - exercised in packaging gaps
        raise RuntimeError("latex2mathml is required for editable PPTX formulas") from exc

    xsl_path = find_mml2omml_xsl()
    if xsl_path is None:
        raise RuntimeError("MML2OMML.XSL was not found; install Microsoft Office or set MML2OMML_XSL")

    body = normalize_latex(latex)
    mathml = latex_to_mathml(body)

    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    mathml_root = etree.fromstring(mathml.encode("utf-8"), parser=parser)
    transform = etree.XSLT(etree.parse(str(xsl_path), parser=parser))
    result = transform(mathml_root)
    root = result.getroot()
    if root is None:
        raise RuntimeError("MathML to OMML transform returned no root element")

    if root.tag == _q(M_NS, "oMathPara"):
        para = deepcopy(root)
    elif root.tag == _q(M_NS, "oMath"):
        para = etree.Element(_q(M_NS, "oMathPara"), nsmap={"m": M_NS})
        para.append(deepcopy(root))
    else:
        found = root.find(".//m:oMath", namespaces=NS)
        if found is None:
            raise RuntimeError(f"MathML to OMML transform returned unexpected root: {root.tag}")
        para = etree.Element(_q(M_NS, "oMathPara"), nsmap={"m": M_NS})
        para.append(deepcopy(found))

    _apply_ppt_math_run_properties(para, font_size_px=font_size_px, fill=fill)
    return para


def _apply_ppt_math_run_properties(para: etree._Element, *, font_size_px: float, fill: str) -> None:
    """Attach DrawingML run properties so equations size correctly in PPT."""
    sz = max(100, int(round(float(font_size_px) * FONT_PX_TO_HUNDREDTHS_PT)))
    color = _hex_color(fill)
    for run in para.findall(".//m:r", namespaces=NS):
        existing = run.find("a:rPr", namespaces=NS)
        if existing is not None:
            rpr = existing
            rpr.set("sz", str(sz))
            rpr.set("dirty", "0")
            rpr.set("smtClean", "0")
        else:
            rpr = etree.Element(_q(A_NS, "rPr"), lang="en-US", sz=str(sz), dirty="0", smtClean="0")
            insert_at = 0
            if len(run) and run[0].tag == _q(M_NS, "rPr"):
                insert_at = 1
            run.insert(insert_at, rpr)

        if color is not None and rpr.find("a:solidFill", namespaces=NS) is None:
            solid = etree.Element(_q(A_NS, "solidFill"))
            etree.SubElement(solid, _q(A_NS, "srgbClr"), val=color)
            rpr.insert(0, solid)
        if rpr.find("a:latin", namespaces=NS) is None:
            etree.SubElement(rpr, _q(A_NS, "latin"), typeface="Cambria Math")
        if rpr.find("a:ea", namespaces=NS) is None:
            etree.SubElement(rpr, _q(A_NS, "ea"), typeface="Cambria Math")
        if rpr.find("a:cs", namespaces=NS) is None:
            etree.SubElement(rpr, _q(A_NS, "cs"), typeface="Cambria Math")


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _equation_bounds(el: dict[str, Any]) -> tuple[float, float, float, float]:
    latex = normalize_latex(str(el.get("latex") or el.get("text") or ""))
    font_size = _float_value(el.get("font_size"), 24.0)
    x = _float_value(el.get("x"), 0.0)
    y = _float_value(el.get("y"), 0.0)
    w = _float_value(el.get("w"), max(font_size * max(len(latex), 3) * 0.48, font_size * 3.0))
    h = _float_value(el.get("h"), font_size * 1.8)
    w = max(w, font_size * 2.0)
    h = max(h, font_size * 1.2)

    anchor = str(el.get("text_anchor", el.get("anchor", "start"))).lower()
    if anchor == "middle":
        x -= w / 2.0
    elif anchor == "end":
        x -= w

    baseline = str(el.get("dominant_baseline", el.get("valign", "middle"))).lower()
    if baseline in {"middle", "central"}:
        y -= h / 2.0
    elif baseline in {"baseline", "text-after-edge", "after-edge"}:
        y -= h

    return x, y, w, h


def _emu(px: float) -> int:
    return int(round(px * EMU_PER_PX))


def _text_rpr_xml(font_size_px: float, fill: str) -> str:
    sz = max(100, int(round(float(font_size_px) * FONT_PX_TO_HUNDREDTHS_PT)))
    color = _hex_color(fill)
    fill_xml = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if color else ""
    return (
        f'<a:rPr lang="en-US" sz="{sz}" dirty="0" smtClean="0">'
        f"{fill_xml}"
        '<a:latin typeface="Cambria Math"/>'
        '<a:ea typeface="Cambria Math"/>'
        '<a:cs typeface="Cambria Math"/>'
        "</a:rPr>"
    )


def _fallback_text_shape(
    *,
    shape_id: int,
    name: str,
    latex: str,
    x_emu: int,
    y_emu: int,
    w_emu: int,
    h_emu: int,
    font_size_px: float,
    fill: str,
) -> str:
    safe_name = html.escape(name, quote=True)
    safe_latex = html.escape(normalize_latex(latex), quote=False)
    rpr = _text_rpr_xml(font_size_px, fill)
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{safe_name} Fallback"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:noFill/>
    <a:ln><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="none" rtlCol="0"><a:spAutoFit/></a:bodyPr>
    <a:lstStyle/>
    <a:p><a:pPr><a:defRPr sz="{max(100, int(round(font_size_px * FONT_PX_TO_HUNDREDTHS_PT)))}"/></a:pPr><a:r>{rpr}<a:t>{safe_latex}</a:t></a:r></a:p>
  </p:txBody>
</p:sp>"""


def _equation_shape_xml(shape_id: int, el: dict[str, Any], omml_para_xml: str) -> str:
    eid = str(el.get("id") or f"equation-{shape_id}")
    latex = str(el.get("latex") or el.get("text") or "")
    font_size_px = _float_value(el.get("font_size"), 24.0)
    fill = str(el.get("fill") or "#111111")
    x, y, w, h = _equation_bounds(el)
    x_emu, y_emu, w_emu, h_emu = _emu(x), _emu(y), _emu(w), _emu(h)
    safe_name = html.escape(f"Editable Equation {eid}", quote=True)
    rpr = _text_rpr_xml(font_size_px, fill)
    fallback = _fallback_text_shape(
        shape_id=shape_id,
        name=f"Editable Equation {eid}",
        latex=latex,
        x_emu=x_emu,
        y_emu=y_emu,
        w_emu=w_emu,
        h_emu=h_emu,
        font_size_px=font_size_px,
        fill=fill,
    )
    return f"""
<mc:AlternateContent xmlns:mc="{MC_NS}" xmlns:a14="{A14_NS}" xmlns:m="{M_NS}" xmlns:p="{P_NS}" xmlns:a="{A_NS}">
  <mc:Choice Requires="a14">
    <p:sp>
      <p:nvSpPr>
        <p:cNvPr id="{shape_id}" name="{safe_name}"/>
        <p:cNvSpPr txBox="1"/>
        <p:nvPr/>
      </p:nvSpPr>
      <p:spPr>
        <a:xfrm><a:off x="{x_emu}" y="{y_emu}"/><a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        <a:noFill/>
        <a:ln><a:noFill/></a:ln>
      </p:spPr>
      <p:txBody>
        <a:bodyPr wrap="none" rtlCol="0"><a:spAutoFit/></a:bodyPr>
        <a:lstStyle/>
        <a:p>
          <a:pPr><a:defRPr sz="{max(100, int(round(font_size_px * FONT_PX_TO_HUNDREDTHS_PT)))}"/></a:pPr>
          <a:r>{rpr}<a:t></a:t></a:r>
          <a14:m>{omml_para_xml}</a14:m>
        </a:p>
      </p:txBody>
    </p:sp>
  </mc:Choice>
  <mc:Fallback>{fallback}</mc:Fallback>
</mc:AlternateContent>"""


def iter_manifest_math_elements(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    elements = manifest.get("elements") or []
    return [
        el
        for el in elements
        if isinstance(el, dict)
        and str(el.get("type", "")).lower() in {"math", "formula"}
        and str(el.get("latex") or el.get("text") or "").strip()
    ]


def prepare_editable_math(manifest_path: Path) -> dict[str, Any]:
    """Convert manifest formulas to OMML XML strings, with per-item errors."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    math_elements = iter_manifest_math_elements(manifest)
    prepared: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    xsl_path = find_mml2omml_xsl()

    for el in math_elements:
        eid = str(el.get("id") or "")
        latex = str(el.get("latex") or el.get("text") or "")
        try:
            para = latex_to_omml_para(
                latex,
                font_size_px=_float_value(el.get("font_size"), 24.0),
                fill=str(el.get("fill") or "#111111"),
            )
            prepared.append(
                {
                    "id": eid,
                    "latex": normalize_latex(latex),
                    "element": el,
                    "omml_para_xml": etree.tostring(para, encoding="unicode"),
                }
            )
        except Exception as exc:
            failures.append({"id": eid, "latex": normalize_latex(latex), "message": repr(exc)})

    status = "ok"
    if failures and prepared:
        status = "review"
    elif failures:
        status = "failed"
    elif not math_elements:
        status = "skipped"

    return {
        "status": status,
        "attempted_count": len(math_elements),
        "prepared_count": len(prepared),
        "editable_count": 0,
        "fallback_vector_count": len(failures),
        "mml2omml_xsl": str(xsl_path) if xsl_path else None,
        "prepared": prepared,
        "failures": failures,
    }


def _max_shape_id(root: etree._Element) -> int:
    max_id = 1
    for elem in root.findall(".//p:cNvPr", namespaces=NS):
        raw = elem.get("id")
        if raw and raw.isdigit():
            max_id = max(max_id, int(raw))
    return max_id


def _count_office_math(slide_xml: str) -> int:
    return len(re.findall(r"<(?:[A-Za-z0-9_]+:)?m(?:\s|>)", slide_xml))


def patch_pptx_with_prepared_math(
    pptx_path: Path,
    prepared_report: dict[str, Any],
    *,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Append prepared editable equations to slide1.xml in *pptx_path*."""
    prepared = list(prepared_report.get("prepared") or [])
    failures = list(prepared_report.get("failures") or [])
    report = {
        "status": prepared_report.get("status", "skipped"),
        "attempted_count": int(prepared_report.get("attempted_count") or 0),
        "prepared_count": len(prepared),
        "editable_count": 0,
        "fallback_vector_count": len(failures),
        "office_math_xml_count": 0,
        "mml2omml_xsl": prepared_report.get("mml2omml_xsl"),
        "failures": failures,
    }

    if not prepared:
        if report_path:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    with tempfile.TemporaryDirectory(prefix="i2svg_omml_") as tmp:
        tmp_dir = Path(tmp)
        extract_dir = tmp_dir / "pptx"
        with zipfile.ZipFile(pptx_path, "r") as zf:
            zf.extractall(extract_dir)

        slide_path = extract_dir / "ppt" / "slides" / "slide1.xml"
        parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)
        tree = etree.parse(str(slide_path), parser=parser)
        root = tree.getroot()
        sp_tree = root.find(".//p:spTree", namespaces=NS)
        if sp_tree is None:
            raise RuntimeError("slide1.xml has no p:spTree")

        next_id = _max_shape_id(root) + 1
        inserted = 0
        for item in prepared:
            shape_xml = _equation_shape_xml(next_id, item["element"], str(item["omml_para_xml"]))
            shape = etree.fromstring(shape_xml.encode("utf-8"), parser=parser)
            sp_tree.append(shape)
            next_id += 1
            inserted += 1

        tree.write(str(slide_path), encoding="UTF-8", xml_declaration=True, standalone=True)
        slide_xml = slide_path.read_text(encoding="utf-8")

        patched = tmp_dir / "patched.pptx"
        with zipfile.ZipFile(patched, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(extract_dir))
        shutil.move(str(patched), str(pptx_path))

    report["editable_count"] = inserted
    report["office_math_xml_count"] = _count_office_math(slide_xml)
    if failures:
        report["status"] = "review"
    elif inserted == report["attempted_count"]:
        report["status"] = "ok"
    else:
        report["status"] = "review"
    if report["attempted_count"] and inserted == 0:
        report["status"] = "failed"
    if report_path:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def patch_pptx_with_editable_math(
    pptx_path: Path,
    manifest_path: Path,
    *,
    report_path: Path | None = None,
) -> dict[str, Any]:
    prepared = prepare_editable_math(manifest_path)
    return patch_pptx_with_prepared_math(pptx_path, prepared, report_path=report_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = patch_pptx_with_editable_math(args.pptx, args.manifest, report_path=args.report)
    print(json.dumps({k: v for k, v in report.items() if k != "prepared"}, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {"ok", "skipped", "review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
