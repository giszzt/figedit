#!/usr/bin/env python3
"""Quality audit helpers for FigEdit Background Aware outputs."""

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


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _status(status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, **extra}


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


def _is_ai_clean_plate(manifest: dict[str, Any]) -> bool:
    plan = manifest.get("background_plan") or {}
    return plan.get("strategy") == "ai-clean-plate"


def _canvas_area(manifest: dict[str, Any]) -> float:
    canvas = manifest.get("canvas", {})
    return max(1.0, _num(canvas.get("width"), 1.0) * _num(canvas.get("height"), 1.0))


def _is_source_crop(asset: dict[str, Any], plate_id: str | None) -> bool:
    if asset.get("id") == plate_id or asset.get("kind") == "background-plate":
        return False
    source_mode = str(asset.get("source_mode", "")).lower()
    decision = str(asset.get("decision", "")).lower()
    return bool(asset.get("source_region")) or source_mode == "source-crop" or decision in {"crop", "source-preserve"}


def _ai_patchwork_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Catch the failure mode where an AI plate is covered by dirty source blocks."""

    if not _is_ai_clean_plate(manifest):
        return _status("ok", reason="no AI clean plate")

    plan = manifest.get("background_plan") or {}
    plate_id = plan.get("plate_asset_id")
    area = _canvas_area(manifest)
    crops = [asset for asset in manifest.get("assets", []) if _is_source_crop(asset, plate_id)]
    crop_summaries = []
    large = []
    total_area = 0.0
    residue = []

    for asset in crops:
        asset_area = max(0.0, _num(asset.get("w")) * _num(asset.get("h")))
        ratio = asset_area / area
        total_area += asset_area
        if ratio >= 0.04:
            large.append(asset)
        crop_summaries.append({"id": asset.get("id"), "area_ratio": round(ratio, 4)})

        residue_flags = [
            asset.get("text_residue"),
            asset.get("old_text_residue"),
            asset.get("annotation_residue"),
            asset.get("contains_old_text"),
            asset.get("contains_foreground_text"),
        ]
        crop_status = str(asset.get("crop_status", "")).lower()
        notes = str(asset.get("review_notes", "") + " " + asset.get("decision_reason", "")).lower()
        if any(flag is True for flag in residue_flags) or any(token in crop_status for token in ["residue", "dirty", "old-text"]) or "old text" in notes or "annotation residue" in notes:
            residue.append(asset.get("id"))

    total_ratio = total_area / area
    if residue:
        return _status(
            "failed",
            message="source crops contain old text or annotation residue",
            residue_assets=residue,
        )
    if len(large) >= 3 or total_ratio >= 0.35:
        return _status(
            "failed",
            message="AI clean-plate output appears to be patchwork source-crop reconstruction",
            source_crop_count=len(crops),
            large_source_crop_count=len(large),
            source_crop_area_ratio=round(total_ratio, 4),
            crops=crop_summaries[:20],
        )
    if large:
        return _status(
            "review",
            message="AI clean-plate output uses large source crops; confirm they are clean, identity-critical assets",
            source_crop_count=len(crops),
            large_source_crop_count=len(large),
            source_crop_area_ratio=round(total_ratio, 4),
            crops=crop_summaries[:20],
        )
    return _status("ok", source_crop_count=len(crops), source_crop_area_ratio=round(total_ratio, 4))


def _raw_detector_import_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Flag raw detector/measurement candidates that leaked into the final SVG.

    Detector-agnostic: any tool's raw output imported wholesale into `elements`
    without model review is the failure, whatever produced the numbers."""

    structural_types = {"rect", "line", "path", "polyline", "polygon", "circle", "ellipse"}
    raw_decisions = {"auto", "raw", "raw-detection", "detector-import", "opencv-import", "cv-import"}
    raw = []
    unreviewed_detector = []

    for element in manifest.get("elements", []):
        if element.get("type") not in structural_types:
            continue
        detector = " ".join(str(element.get(k, "")) for k in ["detector", "source", "evidence"]).lower()
        decision = str(element.get("decision", "")).lower()
        review = str(element.get("review_status", "")).lower()
        if decision in raw_decisions:
            raw.append(element.get("id"))
        if any(token in detector for token in ["opencv", "cv", "hough", "detected_primitives"]) and review not in {"verified", "ok", "accepted"}:
            unreviewed_detector.append(element.get("id"))

    if raw:
        return _status("failed", message="raw detector primitives were imported into final elements", samples=raw[:30])
    if len(unreviewed_detector) > 20:
        return _status(
            "review",
            message="many detector-sourced primitives lack explicit review; check for detector noise",
            count=len(unreviewed_detector),
            samples=unreviewed_detector[:30],
        )
    return _status("ok", unreviewed_detector_count=len(unreviewed_detector))


def _hex_to_rgb(text: str) -> tuple[int, int, int]:
    value = text.lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (255, 255, 255)


def _crop_window_gate(manifest: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Pixel back-check for the model's Crop Window Check verdicts.

    The verdict itself is a visual judgment made while authoring the manifest
    (`crop_window`: clean / clean-on-fill / contaminated). This gate only
    audits it after the fact: for every coordinate-crop asset it inspects the
    window's border ring (does the window straddle two backings? is the
    backing the canvas background?) and whether ink touches the window edge
    (clipped element or intruding neighbor). Contradictions come back as
    review evidence for the model to re-examine — the gate does not overrule
    the model, except for the hard case of cropping a declared-contaminated
    window."""

    crops = [
        asset
        for asset in manifest.get("assets", [])
        if str(asset.get("decision", "")).lower() == "crop" and isinstance(asset.get("source_region"), dict)
    ]
    if not crops:
        return _status("ok", reason="no coordinate-crop assets")

    try:
        import numpy as np
        from PIL import Image

        source = Path(str(manifest.get("source_image") or ""))
        if not source.exists():
            found = sorted((out_dir / "assets").glob("source.*"))
            source = found[0] if found else None
        if source is None:
            return _status("skipped", reason="source image not found")
        arr = np.asarray(Image.open(source).convert("RGB"), dtype=np.int64)
    except Exception as exc:
        return _status("skipped", reason=repr(exc))

    background = _hex_to_rgb(str(((manifest.get("canvas") or {}).get("background")) or "#ffffff"))
    height, width = arr.shape[:2]
    failed = []
    review = []

    for asset in crops:
        region = asset["source_region"]
        try:
            x, y = int(_num(region.get("x"))), int(_num(region.get("y")))
            w, h = int(_num(region.get("w"))), int(_num(region.get("h")))
        except Exception:
            continue
        if w <= 4 or h <= 4:
            continue
        declared = str(asset.get("crop_window", "")).lower() or None

        if declared == "contaminated":
            failed.append({"id": asset.get("id"), "reason": "crop_window is contaminated but decision is still crop; the window contains foreground or backing pixels that are not the element"})
            continue

        band = 3
        rx1, ry1 = max(0, x - band), max(0, y - band)
        rx2, ry2 = min(width, x + w + band), min(height, y + h + band)
        ring_parts = []
        if ry1 < y:
            ring_parts.append(arr[ry1:y, rx1:rx2].reshape(-1, 3))
        if y + h < ry2:
            ring_parts.append(arr[y + h : ry2, rx1:rx2].reshape(-1, 3))
        if rx1 < x:
            ring_parts.append(arr[max(0, y) : min(height, y + h), rx1:x].reshape(-1, 3))
        if x + w < rx2:
            ring_parts.append(arr[max(0, y) : min(height, y + h), x + w : rx2].reshape(-1, 3))
        if not ring_parts:
            continue
        try:
            import numpy as np

            ring = np.concatenate(ring_parts)
            quantized = (ring // 16) * 16
            colors, counts = np.unique(quantized, axis=0, return_counts=True)
            mode_index = int(np.argmax(counts))
            in_bucket = (quantized == colors[mode_index]).all(axis=1)
            # Mean of the actual pixels in the dominant bucket, not the
            # quantized bucket value — light card fills sit only ~25 units
            # from white, so bucket-value precision loss would hide them.
            mode_rgb = ring[in_bucket].mean(axis=0)
            dominant_share = float(counts[mode_index]) / float(len(quantized))
            bg_dist = float(np.sqrt(((mode_rgb - np.array(background, dtype=float)) ** 2).sum()))

            window = arr[max(0, y) : min(height, y + h), max(0, x) : min(width, x + w)]
            ink = np.sqrt(((window.astype(float) - mode_rgb.astype(float)) ** 2).sum(axis=2)) > 40.0
            edge_touch = bool(ink[0, :].any() or ink[-1, :].any() or ink[:, 0].any() or ink[:, -1].any())
        except Exception:
            continue

        evidence = {
            "id": asset.get("id"),
            "declared": declared,
            "ring_dominant": "#{:02x}{:02x}{:02x}".format(*[int(v) for v in mode_rgb]),
            "ring_dominant_share": round(dominant_share, 3),
            "ink_touches_edge": edge_touch,
        }
        if dominant_share < 0.90:
            evidence["reason"] = "window border ring straddles more than one backing color; likely mid-layer or neighbor contamination"
            review.append(evidence)
        elif bg_dist > 12.0 and declared in {None, "clean"}:
            evidence["reason"] = "backing is a uniform non-background fill; declare crop_window clean-on-fill and redraw the backing with this exact fill"
            review.append(evidence)
        elif edge_touch and declared in {None, "clean", "clean-on-fill"}:
            evidence["reason"] = "ink touches the crop window edge; the window may clip the element or include an intruding neighbor"
            review.append(evidence)

    if failed:
        return _status("failed", message="assets with a contaminated crop window are still coordinate-cropped", samples=failed[:30])
    if review:
        return _status(
            "review",
            message="pixel evidence contradicts the declared crop_window verdicts; re-examine these windows against the source",
            count=len(review),
            samples=review[:30],
        )
    return _status("ok", checked=len(crops))


def _ocr_fallback_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Flag OCR fallback text that has not been model-verified."""

    fallback = []
    low_conf_unverified = []
    unreviewed_ocr = []

    for element in manifest.get("elements", []):
        if element.get("type") != "text":
            continue
        joined = " ".join(str(element.get(k, "")) for k in ["decision", "source", "detector", "review_status"]).lower()
        review = str(element.get("review_status", "")).lower()
        confidence = element.get("confidence")
        if "ocr-fallback" in joined or "fallback-ocr" in joined:
            fallback.append(element.get("id"))
        if confidence is not None and _num(confidence, 1.0) < 0.65 and review not in {"verified", "ok", "accepted"}:
            low_conf_unverified.append(element.get("id"))
        if "ocr" in joined and review not in {"verified", "ok", "accepted", "manual-verified"}:
            unreviewed_ocr.append(element.get("id"))

    if fallback:
        return _status("failed", message="OCR fallback text reached final elements", samples=fallback[:30])
    if len(low_conf_unverified) > 0:
        return _status(
            "review",
            message="low-confidence OCR text requires manual verification",
            count=len(low_conf_unverified),
            samples=low_conf_unverified[:30],
        )
    if len(unreviewed_ocr) > 30:
        return _status(
            "review",
            message="many OCR-sourced text elements lack explicit review",
            count=len(unreviewed_ocr),
            samples=unreviewed_ocr[:30],
        )
    return _status("ok", unreviewed_ocr_count=len(unreviewed_ocr))


def _text_math_layout_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    """Review trigger for dense editable text/math layouts.

    This is intentionally a review gate rather than a pixel-diff substitute.
    It catches the common false-green case where formulas are editable and the
    SVG renders, but dense text/math placement has not been constrained or
    visually reviewed after PPTX export.
    """

    elements = manifest.get("elements", [])
    text_elements = [el for el in elements if el.get("type") == "text"]
    math_elements = [el for el in elements if el.get("type") in {"math", "formula"}]
    classification = manifest.get("classification") or {}
    figure_type = str(classification.get("figure_type", "")).lower()
    complexity = str(classification.get("complexity", "")).lower()

    dense = (
        len(math_elements) >= 20
        or len(text_elements) >= 80
        or "formula" in figure_type
        or ("high" in complexity and len(math_elements) >= 8)
    )
    if not dense:
        return _status("ok", reason="not a dense text/math layout")

    unconstrained_math = [
        el.get("id")
        for el in math_elements
        if not el.get("source_region")
        or not el.get("w")
        or not el.get("h")
        or not (el.get("layout_lock") or el.get("baseline_y") or el.get("dominant_baseline"))
    ]
    unconstrained_text = [
        el.get("id")
        for el in text_elements
        if (not el.get("source_region") or not (el.get("w") or el.get("max_width"))) and _num(el.get("font_size"), 16) <= 14
    ]

    review = manifest.get("pptx_visual_review") or (manifest.get("quality_gates") or {}).get("pptx_visual_review")
    review_ok = isinstance(review, dict) and str(review.get("status", "")).lower() in {"ok", "verified", "passed"}

    if not review_ok:
        return _status(
            "review",
            message="dense editable text/math layout requires PPTX visual review",
            text_count=len(text_elements),
            math_count=len(math_elements),
            unconstrained_math_count=len(unconstrained_math),
            unconstrained_text_count=len(unconstrained_text),
            samples=(unconstrained_math + unconstrained_text)[:30],
        )
    if len(unconstrained_math) > max(3, len(math_elements) * 0.25):
        return _status(
            "review",
            message="many math elements lack source-slot layout constraints",
            math_count=len(math_elements),
            unconstrained_math_count=len(unconstrained_math),
            samples=unconstrained_math[:30],
        )
    if len(unconstrained_text) > 20:
        return _status(
            "review",
            message="many small text elements lack source-region or width constraints",
            text_count=len(text_elements),
            unconstrained_text_count=len(unconstrained_text),
            samples=unconstrained_text[:30],
        )
    return _status(
        "ok",
        text_count=len(text_elements),
        math_count=len(math_elements),
        pptx_visual_review="ok",
    )


def _background_plate_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    if not _is_ai_clean_plate(manifest):
        return _status("ok", reason="conventional route")

    plan = manifest.get("background_plan") or {}
    plate_id = plan.get("plate_asset_id")
    plate = next((asset for asset in manifest.get("assets", []) if asset.get("id") == plate_id), None)
    provenance = plan.get("generation_provenance") or {}
    review = plan.get("candidate_review") or {}

    if not isinstance(plate, dict):
        return _status("failed", message="AI clean plate asset is missing")
    if plate.get("kind") != "background-plate":
        return _status("failed", message="AI clean plate asset should use kind=background-plate")
    if not provenance.get("output"):
        return _status("failed", message="AI clean plate lacks generation provenance output")
    if review.get("accepted") is not True:
        return _status("failed", message="AI clean plate candidate was not accepted")

    canvas = manifest.get("canvas", {})
    w_ok = abs(_num(plate.get("w")) - _num(canvas.get("width"))) <= max(1.0, _num(canvas.get("width")) * 0.01)
    h_ok = abs(_num(plate.get("h")) - _num(canvas.get("height"))) <= max(1.0, _num(canvas.get("height")) * 0.01)
    if not w_ok or not h_ok:
        return _status("failed", message="AI clean plate is not canvas-aligned")
    return _status("ok")


def _background_route_consistency_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    classification = manifest.get("classification") or {}
    style = str(classification.get("style_type", "")).lower()
    intent = str(classification.get("reconstruction_intent", "")).lower()
    mode = str(classification.get("reconstruction_mode", "")).lower()
    has_plan = bool(manifest.get("background_plan"))

    ai_declared = (
        style == "continuous-visual-field"
        or intent == "clean-plate-plus-editable-overlay"
        or mode == "e-ai"
    )
    if ai_declared and not has_plan:
        return _status(
            "review",
            message="classification suggests an AI clean-plate route, but background_plan is missing",
            style_type=style,
            reconstruction_intent=intent,
            reconstruction_mode=mode,
        )
    if has_plan and not _is_ai_clean_plate(manifest):
        return _status("failed", message="background_plan is present but strategy is not ai-clean-plate")
    return _status("ok")


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
        "background_route_consistency": _background_route_consistency_gate(manifest),
        "background_plate": _background_plate_gate(manifest),
        "ai_patchwork_source_crops": _ai_patchwork_gate(manifest),
        "crop_window_consistency": _crop_window_gate(manifest, out_dir),
        "raw_detector_import": _raw_detector_import_gate(manifest),
        "ocr_fallback_text": _ocr_fallback_gate(manifest),
        "text_math_layout_fidelity": _text_math_layout_gate(manifest),
    }
    return gates


def write_quality_report(out_dir: Path, gates: dict[str, Any]) -> None:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    ocr = json.loads((out_dir / "ocr_results.json").read_text(encoding="utf-8")) if (out_dir / "ocr_results.json").exists() else {}
    assets = manifest.get("assets", [])
    elements = manifest.get("elements", [])
    editability = (manifest.get("quality_gates") or {}).get("editability", {})
    pptx_math = gates.get("pptx_math_export") or (manifest.get("quality_gates") or {}).get("pptx_math_export", {})
    formula_leaks = editability.get("formula_text_leak_samples", [])
    low_conf = [el for el in elements if el.get("review_status") in {"low-confidence", "needs-check"}]
    crop_issues = [a for a in assets if a.get("crop_status") not in {None, "verified", "ok"} or (a.get("edge_check") or {}).get("status") not in {None, "ok"}]
    background_plan = manifest.get("background_plan") or {}

    lines = [
        "# Reconstruction Quality Report",
        "",
        "## Summary",
        "",
        f"- Project: {manifest.get('project')}",
        f"- Source image: {manifest.get('source_image')}",
        f"- Canvas: {manifest.get('canvas', {}).get('width')} x {manifest.get('canvas', {}).get('height')}",
        f"- OCR status: {ocr.get('status', 'missing')} ({len(ocr.get('items', []))} text candidates)",
        f"- Background strategy: {background_plan.get('strategy', 'conventional')}",
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
    editability_ok = editability.get("status") in {None, "ok"}
    if not low_conf and not crop_issues and editability_ok and all(v.get("status") in {"ok", "skipped"} for v in gates.values()):
        lines.append("- No high-priority review items detected by automated checks.")
    if editability.get("status") == "unavailable":
        lines.append(
            "- Gate `editability` is `unavailable`: OCR evidence is missing, so text_lift_ratio could not be computed. "
            "Manually verify that no editable text was baked into raster assets, or restore `ocr_results.json` "
            "(set `diagnostics.measurement_workspace` in the manifest, or keep the measurement `work/` directory next to it) and rerun."
        )
    elif editability.get("status") == "review":
        lines.append(f"- Gate `editability` needs review: text_lift_ratio={editability.get('text_lift_ratio')} asset_text_risks={editability.get('asset_text_risk_count')} formula_leaks={editability.get('formula_text_leak_count')}")
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
            samples = value.get("samples") if isinstance(value.get("samples"), list) else []
            for sample in samples[:20]:
                lines.append(f"- Gate `{key}` sample: `{sample}`")
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
            "- `diagnostics/placement_overlay.png`",
            "- `diagnostics/style_overlay.png`",
            "- `editability_report.md`",
            "",
            "## Notes",
            "",
            "- Dense maps, heatmaps, screenshots, and charts remain source-preserved raster assets unless explicitly vectorized.",
            "- AI clean plate is a background repair route, not a foreground patchwork route.",
            "- Source-specific assets should be cropped only when identity matters and the crop is clean.",
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
