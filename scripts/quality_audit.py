#!/usr/bin/env python3
"""Quality audit helpers for FigEdit outputs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _parse_xml(path: Path) -> tuple[bool, str]:
    try:
        ET.parse(path)
        return True, "ok"
    except Exception as exc:
        return False, repr(exc)


def _find_chrome() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if path.exists():
            return path
    found = shutil.which("chrome") or shutil.which("msedge") or shutil.which("chromium")
    return Path(found) if found else None


def render_preview(svg_path: Path, preview_path: Path, width: int, height: int) -> dict[str, Any]:
    chrome = _find_chrome()
    if not chrome:
        return {"status": "skipped", "reason": "Chrome/Edge executable not found"}
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    url = svg_path.resolve().as_uri()
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={int(width)},{int(height)}",
        f"--screenshot={str(preview_path)}",
        url,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
    return {
        "status": "ok" if proc.returncode == 0 and preview_path.exists() else "failed",
        "renderer": str(chrome),
        "returncode": proc.returncode,
        "output": proc.stdout[-1000:],
    }


def audit_output(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    canvas = manifest.get("canvas", {})
    width = int(canvas.get("width", 1200) or 1200)
    height = int(canvas.get("height", 800) or 800)

    editable_ok, editable_msg = _parse_xml(out_dir / "editable.svg")
    embedded_ok, embedded_msg = _parse_xml(out_dir / "editable_embedded.svg")
    preview = render_preview(out_dir / "editable.svg", out_dir / "preview.png", width, height)

    assets = manifest.get("assets", [])
    elements = manifest.get("elements", [])
    low_conf = [el for el in elements if el.get("review_status") in {"low-confidence", "needs-check"}]
    crop_issues = [a for a in assets if a.get("crop_status") not in {None, "verified", "ok"} or (a.get("edge_check") or {}).get("status") not in {None, "ok"}]

    gates = {
        "xml_editable": {"status": "ok" if editable_ok else "failed", "message": editable_msg},
        "xml_embedded": {"status": "ok" if embedded_ok else "failed", "message": embedded_msg},
        "preview_render": preview,
        "low_confidence_elements": {"status": "review" if low_conf else "ok", "count": len(low_conf)},
        "crop_edge_checks": {"status": "review" if crop_issues else "ok", "count": len(crop_issues)},
    }
    return gates


def write_quality_report(out_dir: Path, gates: dict[str, Any]) -> None:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    ocr = json.loads((out_dir / "ocr_results.json").read_text(encoding="utf-8")) if (out_dir / "ocr_results.json").exists() else {}
    primitives = json.loads((out_dir / "detected_primitives.json").read_text(encoding="utf-8")) if (out_dir / "detected_primitives.json").exists() else {}
    assets = manifest.get("assets", [])
    elements = manifest.get("elements", [])
    editability = (manifest.get("quality_gates") or {}).get("editability", {})
    pptx_math = gates.get("pptx_math_export") or (manifest.get("quality_gates") or {}).get("pptx_math_export", {})
    formula_leaks = editability.get("formula_text_leak_samples", [])
    low_conf = [el for el in elements if el.get("review_status") in {"low-confidence", "needs-check"}]
    crop_issues = [a for a in assets if a.get("crop_status") not in {None, "verified", "ok"} or (a.get("edge_check") or {}).get("status") not in {None, "ok"}]

    lines = [
        "# Reconstruction Quality Report",
        "",
        "## Summary",
        "",
        f"- Project: {manifest.get('project')}",
        f"- Source image: {manifest.get('source_image')}",
        f"- Canvas: {manifest.get('canvas', {}).get('width')} x {manifest.get('canvas', {}).get('height')}",
        f"- OCR status: {ocr.get('status', 'missing')} ({len(ocr.get('items', []))} text candidates)",
        f"- OpenCV status: {primitives.get('status', 'missing')} ({primitives.get('counts', {})})",
        f"- Assets: {len(assets)}",
        f"- Elements: {len(elements)}",
        f"- SVG text elements: {len([e for e in elements if e.get('type') == 'text'])}",
        f"- SVG math elements: {len([e for e in elements if e.get('type') in {'math','formula'}])}",
        f"- Formula-like text leaks: {editability.get('formula_text_leak_count', 0)}",
        f"- PPTX editable formula objects: {pptx_math.get('editable_count', 0)}/{pptx_math.get('attempted_count', 0)}",
        f"- Structural SVG elements: {len([e for e in elements if e.get('type') in {'rect','line','path','polyline','polygon','circle','ellipse'}])}",
        "",
        "## Quality Gates",
        "",
    ]
    for key, value in gates.items():
        lines.append(f"- {key}: `{value.get('status')}`")
    if editability:
        lines.append(f"- editability: `{editability.get('status')}` text_lift_ratio={editability.get('text_lift_ratio')} asset_text_risks={editability.get('asset_text_risk_count')}")
    lines.extend(["", "## Items Needing Review", ""])
    if not low_conf and not crop_issues and all(v.get("status") in {"ok", "skipped"} for v in gates.values()):
        lines.append("- No high-priority review items detected by automated checks.")
    for el in low_conf[:80]:
        lines.append(f"- Element `{el.get('id')}` needs review: status={el.get('review_status')} confidence={el.get('confidence')}")
    for asset in crop_issues[:80]:
        lines.append(f"- Asset `{asset.get('id')}` crop review: {asset.get('edge_check')} status={asset.get('crop_status')}")
    for key, value in gates.items():
        if value.get("status") not in {"ok", "skipped"}:
            if key == "formula_text_leakage":
                message = f"{value.get('count', 0)} formula-like text element(s)"
            else:
                message = value.get("message") or value.get("reason") or value
            lines.append(f"- Gate `{key}` needs review: {message}")
            if key == "pptx_math_export":
                for failure in value.get("failures", [])[:20]:
                    lines.append(f"- Formula `{failure.get('id')}` not editable: {failure.get('message')}")
            if key == "formula_text_leakage":
                for leak in value.get("samples", [])[:20]:
                    reasons = ", ".join(leak.get("reasons", []))
                    lines.append(f"- Formula-like text `{leak.get('id')}` should be split or converted: `{leak.get('text')}` reasons={reasons}")
    if formula_leaks and "formula_text_leakage" not in gates:
        for leak in formula_leaks[:20]:
            reasons = ", ".join(leak.get("reasons", []))
            lines.append(f"- Formula-like text `{leak.get('id')}` should be split or converted: `{leak.get('text')}` reasons={reasons}")
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "- `diagnostics/ocr_overlay.png`",
            "- `diagnostics/structure_overlay.png`",
            "- `diagnostics/crop_overlay.png`",
            "- `diagnostics/style_overlay.png`",
            "- `diagnostics/rejected_candidates.png`",
            "- `editability_report.md`",
            "",
            "## Notes",
            "",
            "- Dense maps, heatmaps, screenshots, and charts remain source-preserved raster assets unless explicitly vectorized.",
            "- Low-confidence OCR text should be checked against the source image before publication use.",
        ]
    )
    (out_dir / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_and_write(out_dir: Path) -> dict[str, Any]:
    gates = audit_output(out_dir)
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["quality_gates"] = gates
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_quality_report(out_dir, gates)
    return gates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    gates = audit_and_write(args.out_dir)
    print(json.dumps(gates, ensure_ascii=False, indent=2))
    return 0 if all(v.get("status") in {"ok", "skipped", "review"} for v in gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
