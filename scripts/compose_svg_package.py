#!/usr/bin/env python3
"""Compose an editable SVG package from a model-authored manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_svg_from_manifest import build_svg  # type: ignore
from crop_assets import crop_assets as crop_manifest_assets  # type: ignore
from embed_svg_assets import embed  # type: ignore
from quality_audit import audit_and_write, write_quality_report  # type: ignore
from audit_editability import audit as audit_editability, write_report as write_editability_report  # type: ignore
from export_pptx_from_svg import export_native_pptx  # type: ignore


def _ensure_ascii_source(manifest: dict, manifest_path: Path, out_dir: Path) -> Path:
    source = Path(manifest["source_image"])
    if not source.exists():
        source = (manifest_path.parent / manifest["source_image"]).resolve()
    if not source.exists():
        raise FileNotFoundError(f"source_image not found: {manifest['source_image']}")
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".png"
    copied = assets_dir / f"source{suffix}"
    shutil.copy2(source, copied)
    return copied


def _draw_crop_overlay(source: Path, manifest: dict, out_path: Path) -> None:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for asset in manifest.get("assets", []):
        region = asset.get("source_region") or asset
        x, y, w, h = [float(region.get(k, 0)) for k in ("x", "y", "w", "h")]
        status = asset.get("crop_status") or (asset.get("edge_check") or {}).get("status")
        color = (0, 170, 80, 220) if status in {None, "ok", "verified"} else (255, 140, 0, 230)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x, y), str(asset.get("id", "asset")), fill=color)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def _copy_measurement_artifacts(manifest: dict, out_dir: Path) -> None:
    workspace = (manifest.get("diagnostics") or {}).get("measurement_workspace")
    if not workspace:
        return
    src_dir = Path(workspace)
    if not src_dir.exists():
        return
    for name in ["ocr_results.json", "detected_primitives.json", "style_tokens.json", "measurement_report.md"]:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)
    diag_src = src_dir / "diagnostics"
    diag_dst = out_dir / "diagnostics"
    if diag_src.exists():
        diag_dst.mkdir(parents=True, exist_ok=True)
        for item in diag_src.glob("*.png"):
            shutil.copy2(item, diag_dst / item.name)


def compose(manifest_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _copy_measurement_artifacts(manifest, out_dir)
    ascii_source = _ensure_ascii_source(manifest, manifest_path, out_dir)

    # Use the ASCII source for script operations, but keep original source path
    # in a provenance field so Windows Unicode paths are not damaged.
    manifest.setdefault("provenance", {})["original_source_image"] = manifest["source_image"]
    manifest["source_image"] = str(ascii_source)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    crop_manifest_assets(out_dir / "manifest.json", out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    svg = build_svg(manifest)
    (out_dir / "editable.svg").write_text(svg, encoding="utf-8")
    embed(out_dir / "editable.svg", out_dir, out_dir / "editable_embedded.svg")
    _draw_crop_overlay(ascii_source, manifest, out_dir / "diagnostics" / "crop_overlay.png")
    gates = audit_and_write(out_dir)
    try:
        pptx_path = out_dir / "editable.pptx"
        trace_path = out_dir / "editable.pptx.trace.json"
        export_native_pptx(out_dir / "editable.svg", out_dir, pptx_path, trace_path=trace_path)
        gates["pptx_export"] = {"status": "ok", "path": str(pptx_path), "trace": str(trace_path)}
        math_report_path = pptx_path.with_name(pptx_path.name + ".math_report.json")
        if math_report_path.exists():
            gates["pptx_math_export"] = json.loads(math_report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gates["pptx_export"] = {"status": "review", "message": repr(exc)}
    editability = audit_editability(out_dir / "manifest.json", out_dir / "ocr_results.json" if (out_dir / "ocr_results.json").exists() else None)
    write_editability_report(out_dir, editability)
    leak_count = int(editability.get("formula_text_leak_count") or 0)
    gates["formula_text_leakage"] = {
        "status": "review" if leak_count else "ok",
        "count": leak_count,
        "samples": editability.get("formula_text_leak_samples", [])[:20],
    }
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["quality_gates"] = {**(manifest.get("quality_gates") or {}), **gates, "editability": editability}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_quality_report(out_dir, gates)
    return {"out_dir": str(out_dir), "quality_gates": gates}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = compose(args.manifest.resolve(), args.out.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
