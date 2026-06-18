#!/usr/bin/env python3
"""Prepare OCR/CV/style diagnostics for model-led SVG reconstruction."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect_ocr_paddle import save_ocr_outputs  # type: ignore
from detect_primitives_cv import save_primitives_outputs  # type: ignore
from sample_styles import save_style_outputs  # type: ignore


def prepare(image_path: Path, out_dir: Path, lang: str = "ch", gpu: bool = False, ocr_profile: str = "v6_medium") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = out_dir / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    source_copy = assets / f"source{image_path.suffix.lower() or '.png'}"
    shutil.copy2(image_path, source_copy)

    ocr = save_ocr_outputs(source_copy, out_dir / "ocr_results.json", diagnostics / "ocr_overlay.png", lang=lang, use_gpu=gpu, profile=ocr_profile)
    primitives = save_primitives_outputs(source_copy, out_dir / "ocr_results.json", out_dir / "detected_primitives.json", diagnostics / "structure_overlay.png")
    styles = save_style_outputs(source_copy, out_dir / "detected_primitives.json", out_dir / "style_tokens.json", diagnostics / "style_overlay.png")

    with Image.open(source_copy) as im:
        width, height = im.size
    draft = {
        "project": out_dir.name,
        "source_image": str(image_path),
        "working_source_image": str(source_copy),
        "canvas": {"width": width, "height": height, "background": styles.get("background", "#ffffff")},
        "classification": {
            "layout_topology": "model-to-classify",
            "complexity": "model-to-classify",
            "style_type": "image-derived",
            "reconstruction_mode": "model-led-hybrid",
            "reconstruction_intent": "Use OCR/CV measurements only as evidence; model must author semantic manifest.",
        },
        "assets": [],
        "elements": [],
        "style_tokens": styles,
        "diagnostics": {
            "ocr_overlay": "diagnostics/ocr_overlay.png",
            "structure_overlay": "diagnostics/structure_overlay.png",
            "style_overlay": "diagnostics/style_overlay.png",
            "ocr_status": ocr.get("status"),
            "ocr_profile": ocr.get("selected_profile"),
            "opencv_status": primitives.get("status"),
        },
        "quality_gates": {"semantic_manifest_required": {"status": "review"}},
    }
    (out_dir / "draft_manifest.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Measurement Report",
        "",
        f"- Source: {image_path}",
        f"- Working copy: {source_copy}",
        f"- Canvas: {width} x {height}",
        f"- OCR: {ocr.get('status')} ({len(ocr.get('items', []))} candidates; profile: {ocr.get('selected_profile')}; requested: {ocr.get('requested_profile')})",
        f"- OpenCV: {primitives.get('status')} ({primitives.get('counts', {})})",
        "",
        "These are measurement artifacts only. Do not directly convert all OpenCV candidates into final SVG elements.",
    ]
    (out_dir / "measurement_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"out_dir": str(out_dir), "ocr": ocr.get("status"), "opencv": primitives.get("status")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--ocr-profile", default="v6_medium", choices=["auto", "v6_medium", "v6_small", "v6_tiny", "v5_mobile"])
    args = parser.parse_args()
    result = prepare(args.image.resolve(), args.out.resolve(), lang=args.lang, gpu=args.gpu, ocr_profile=args.ocr_profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
