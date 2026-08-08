#!/usr/bin/env python3
"""Prepare OCR/style diagnostics for model-led SVG reconstruction."""

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
from sample_styles import save_style_outputs  # type: ignore
from probe_geometry import probe as probe_geometry, draw_overlay as draw_geometry_overlay  # type: ignore


def prepare(
    image_path: Path,
    out_dir: Path,
    lang: str = "ch",
    gpu: bool = False,
    ocr_profile: str = "v6_medium",
    geometry: bool = True,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = out_dir / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    source_copy = assets / f"source{image_path.suffix.lower() or '.png'}"
    shutil.copy2(image_path, source_copy)

    ocr = save_ocr_outputs(source_copy, out_dir / "ocr_results.json", diagnostics / "ocr_overlay.png", lang=lang, use_gpu=gpu, profile=ocr_profile)
    styles = save_style_outputs(source_copy, None, out_dir / "style_tokens.json", diagnostics / "style_overlay.png")

    geometry_summary: dict | None = None
    if geometry:
        payload, arr = probe_geometry(source_copy, out_dir / "ocr_results.json")
        (out_dir / "geometry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        draw_geometry_overlay(arr, payload, diagnostics / "geometry_overlay.png")
        geometry_summary = {
            "flat_design_score": payload["image_profile"]["flat_design_score"],
            "abstained": payload["image_profile"]["abstained"],
            "fill_regions": len(payload["fill_regions"]),
            "text_slots": len(payload["text_slots"]),
        }

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
            "reconstruction_intent": "Use OCR/style measurements only as evidence; model must author semantic manifest.",
        },
        "assets": [],
        "elements": [],
        "style_tokens": styles,
        "diagnostics": {
            # Keep this field when authoring the final manifest: the compose
            # step copies ocr_results.json from here into the package so the
            # editability gate can compute text_lift_ratio.
            "measurement_workspace": str(out_dir),
            "ocr_overlay": "diagnostics/ocr_overlay.png",
            "style_overlay": "diagnostics/style_overlay.png",
            "ocr_status": ocr.get("status"),
            "ocr_profile": ocr.get("selected_profile"),
            "geometry": "geometry.json" if geometry_summary else None,
            "geometry_overlay": "diagnostics/geometry_overlay.png" if geometry_summary else None,
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
    ]
    if geometry_summary:
        report += [
            f"- Geometry: flat_design_score {geometry_summary['flat_design_score']}"
            f"{' (ABSTAINED)' if geometry_summary['abstained'] else ''}; "
            f"{geometry_summary['fill_regions']} fill regions, {geometry_summary['text_slots']} text slots",
            "  Look at diagnostics/geometry_overlay.png once, then draft_elements.py to turn these into drafts.",
        ]
    report += [
        "",
        "These are measurement artifacts only. Do not directly convert OCR candidates into final SVG elements.",
    ]
    (out_dir / "measurement_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"out_dir": str(out_dir), "ocr": ocr.get("status"), "geometry": geometry_summary}


def scaffold(image_path: Path, name: str, root: Path) -> dict:
    """Create the task directory, copy the source in, write a manifest skeleton."""
    task_dir = (root / name).resolve()
    work = task_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    (task_dir / "out").mkdir(parents=True, exist_ok=True)

    local_source = task_dir / f"input{image_path.suffix.lower() or '.png'}"
    shutil.copy2(image_path, local_source)
    with Image.open(local_source) as im:
        width, height = im.size

    manifest_path = task_dir / "manifest.json"
    if not manifest_path.exists():
        # No reconstruction_plan block: its fields are closed enumerations
        # (edit_scope, validation_tier) with no valid "to be decided" value, so
        # a placeholder would only produce a manifest that fails validation.
        # The plan is authored from the survey, before any element is written.
        manifest_path.write_text(
            json.dumps(
                {
                    "project": name,
                    "source_image": str(local_source),
                    "canvas": {"width": width, "height": height, "background": "#ffffff"},
                    "classification": {
                        "layout_topology": "model-to-classify",
                        "complexity": "model-to-classify",
                        "style_type": "image-derived",
                        "reconstruction_mode": "model-led-hybrid",
                    },
                    "assets": [],
                    "elements": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return {"task_dir": str(task_dir), "work": str(work), "source": str(local_source),
            "canvas": {"width": width, "height": height}, "manifest": str(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--init", metavar="NAME", help="scaffold <NAME>/{work,out} + manifest skeleton, then measure into <NAME>/work")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--no-geometry", action="store_true", help="skip structure probing (OCR and styles only)")
    parser.add_argument("--ocr-profile", default="v6_medium", choices=["auto", "v6_medium", "v6_small", "v6_tiny", "v5_mobile"])
    args = parser.parse_args()

    image = args.image.resolve()
    scaffolded = None
    out_dir = args.out.resolve() if args.out else None
    if args.init:
        scaffolded = scaffold(image, args.init, args.root.resolve())
        image = Path(scaffolded["source"])
        out_dir = out_dir or Path(scaffolded["work"])
    if out_dir is None:
        parser.error("--out is required unless --init is given")

    result = prepare(
        image,
        out_dir,
        lang=args.lang,
        gpu=args.gpu,
        ocr_profile=args.ocr_profile,
        geometry=not args.no_geometry,
    )
    if scaffolded:
        result["scaffold"] = scaffolded
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
