#!/usr/bin/env python3
"""Compose an editable SVG package from a model-authored manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
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
from pptx_text_fit import audit as audit_pptx_text_fit  # type: ignore
from svg_stage_report import analyze as analyze_svg_stage  # type: ignore
from validate_manifest import _validate_route_decision  # type: ignore


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
    if copied.exists() and copied.stat().st_size == source.stat().st_size:
        return copied
    shutil.copy2(source, copied)
    return copied


def _draw_placement_overlay(source: Path, manifest: dict, out_path: Path) -> None:
    """All declared source boxes drawn back onto the source image: asset crops
    (green/orange by status) plus text/math source regions (blue), so wrong or
    shifted boxes are visible in one review pass."""
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    for asset in manifest.get("assets", []):
        region = asset.get("source_region") or asset
        x, y, w, h = [float(region.get(k, 0)) for k in ("x", "y", "w", "h")]
        status = asset.get("crop_status") or (asset.get("edge_check") or {}).get("status")
        color = (0, 170, 80, 220) if status in {None, "ok", "verified"} else (255, 140, 0, 230)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x, y), str(asset.get("id", "asset")), fill=color)
    for element in manifest.get("elements", []):
        if element.get("type") not in {"text", "math"}:
            continue
        region = element.get("source_region") or element.get("source_bbox")
        if not region:
            continue
        x, y, w, h = [float(region.get(k, 0)) for k in ("x", "y", "w", "h")]
        color = (40, 90, 220, 200)
        draw.rectangle([x, y, x + w, y + h], outline=color, width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)


def _copy_measurement_artifacts(manifest: dict, manifest_path: Path, out_dir: Path) -> None:
    """Copy OCR/style evidence into the package so the editability gate can
    compute text_lift_ratio. `diagnostics.measurement_workspace` is the
    declared location; when it is absent, fall back to the conventional
    `work/` directories next to the manifest — a missing copy silently
    disables the baked-text check downstream, so never fail quietly."""
    declared = (manifest.get("diagnostics") or {}).get("measurement_workspace")
    candidates = []
    if declared:
        declared_path = Path(declared)
        if not declared_path.is_absolute():
            declared_path = (manifest_path.parent / declared_path).resolve()
        candidates.append(declared_path)
    candidates.append(manifest_path.parent / "work")
    candidates.append(manifest_path.parent.parent / "work")

    src_dir = next((c for c in candidates if c.exists() and (c / "ocr_results.json").exists()), None)
    if src_dir is None:
        print(
            "WARNING: no measurement workspace found (checked diagnostics.measurement_workspace and ./work, ../work); "
            "ocr_results.json will be missing and the editability gate will report `unavailable`.",
            file=sys.stderr,
        )
        return
    for name in ["ocr_results.json", "style_tokens.json", "measurement_report.md"]:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)
    diag_src = src_dir / "diagnostics"
    diag_dst = out_dir / "diagnostics"
    if diag_src.exists():
        diag_dst.mkdir(parents=True, exist_ok=True)
        for item in diag_src.glob("*.png"):
            shutil.copy2(item, diag_dst / item.name)


def _copy_background_artifacts(manifest: dict, manifest_path: Path, out_dir: Path) -> None:
    plans = manifest.get("background_plans")
    if not isinstance(plans, list):
        legacy = manifest.get("background_plan")
        plans = [legacy] if isinstance(legacy, dict) else []
    for index, plan in enumerate(plan for plan in plans if isinstance(plan, dict)):
        workspace = plan.get("diagnostics_workspace")
        if not workspace and plan.get("plate_asset_id"):
            plate = next((a for a in manifest.get("assets", []) if a.get("id") == plan.get("plate_asset_id")), None)
            if plate and plate.get("source_mode") == "external":
                workspace = str(Path(plate["file"]).parent)
        if not workspace:
            continue
        src_dir = Path(workspace)
        if not src_dir.is_absolute():
            src_dir = (manifest_path.parent / src_dir).resolve()
        if not src_dir.exists():
            continue
        diag_dst = out_dir / "diagnostics"
        diag_dst.mkdir(parents=True, exist_ok=True)
        scope_prefix = str(plan.get("scope_id") or f"background-{index}")
        for name in ["background_mask.png", "background_mask_overlay.png", "background_preparation.json"]:
            src = src_dir / name
            if src.exists():
                shutil.copy2(src, diag_dst / f"{scope_prefix}-{name}")


def _copy_generation_artifacts(manifest: dict, manifest_path: Path, out_dir: Path) -> None:
    plans = manifest.get("background_plans")
    if not isinstance(plans, list):
        legacy = manifest.get("background_plan")
        plans = [legacy] if isinstance(legacy, dict) else []
    diag_dst = out_dir / "diagnostics"
    for index, plan in enumerate(plan for plan in plans if isinstance(plan, dict)):
        provenance = plan.get("generation_provenance") or {}
        scope_prefix = str(plan.get("scope_id") or f"background-{index}")
        for field, suffix in [
            ("job_record", "generation-job.json"),
            ("prompt_file", "clean-plate-prompt.txt"),
        ]:
            value = provenance.get(field)
            if not value:
                continue
            src = Path(value)
            if not src.is_absolute():
                src = (manifest_path.parent / src).resolve()
            if not src.exists():
                continue
            target_name = f"{scope_prefix}-{suffix}"
            diag_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, diag_dst / target_name)
            provenance[field] = f"diagnostics/{target_name}"


def _require_ready_route(manifest: dict) -> None:
    plan = manifest.get("reconstruction_plan")
    if isinstance(plan, dict):
        open_questions = plan.get("open_questions") or []
        if open_questions:
            raise RuntimeError(
                "The reconstruction plan has open user questions. Resolve them before measurement, "
                f"cropping, generation, or composition: {json.dumps(open_questions, ensure_ascii=False)}"
            )
        pending = [
            region.get("id")
            for region in plan.get("background_regions", [])
            if isinstance(region, dict) and region.get("foreground_mode") == "pending-user-choice"
        ]
        if pending:
            raise RuntimeError(f"Background regions still await a foreground choice: {', '.join(map(str, pending))}")
        canvas = manifest.get("canvas") or {}
        width = float(canvas.get("width") or 0)
        height = float(canvas.get("height") or 0)
        if width <= 0 or height <= 0 or not _validate_route_decision(manifest, width, height):
            raise RuntimeError("The reconstruction plan failed validation; composition is blocked.")
        return

    route = manifest.get("route_decision")
    if not isinstance(route, dict) or route.get("schema_version") != 2:
        return
    if route.get("route_status") != "ready":
        unresolved = route.get("unresolved_decisions") or []
        raise RuntimeError(
            "Route Decision v2 is not ready. Resolve the user's foreground editability choices before "
            f"measurement, cropping, generation, or composition. Unresolved: {json.dumps(unresolved, ensure_ascii=False)}"
        )
    pending = [
        scope.get("id")
        for scope in route.get("background_scopes", [])
        if isinstance(scope, dict) and scope.get("foreground_mode") == "pending-user-choice"
    ]
    if pending:
        raise RuntimeError(f"Route Decision v2 still has pending-user-choice scopes: {', '.join(map(str, pending))}")
    estimated = [
        scope.get("id")
        for scope in route.get("background_scopes", [])
        if isinstance(scope, dict) and scope.get("region_accuracy") != "measured"
    ]
    if estimated:
        raise RuntimeError(f"Background scope coordinates must be measured before composition: {', '.join(map(str, estimated))}")
    canvas = manifest.get("canvas") or {}
    width = float(canvas.get("width") or 0)
    height = float(canvas.get("height") or 0)
    if width <= 0 or height <= 0 or not _validate_route_decision(manifest, width, height):
        raise RuntimeError("Route Decision v2 failed validation; reconstruction is blocked before composition.")


def _write_manifest(out_dir: Path, manifest: dict) -> None:
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_timings(out_dir: Path, invocation_stage: str, durations: dict[str, float]) -> dict:
    path = out_dir / "timings.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        existing = {}
    runs = existing.get("runs") if isinstance(existing.get("runs"), list) else []
    runs.append(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "stage": invocation_stage,
            "durations_seconds": {key: round(value, 4) for key, value in durations.items()},
            "total_seconds": round(sum(durations.values()), 4),
        }
    )
    report = {
        "runs": runs[-100:],
        "counts": {
            "full_compose": sum(1 for run in runs if run.get("stage") == "full"),
            "svg_stage": sum(1 for run in runs if run.get("stage") in {"svg", "full"}),
            "pptx_export": sum(1 for run in runs if run.get("stage") in {"pptx", "full"}),
            "package_stage": sum(1 for run in runs if run.get("stage") in {"package", "full"}),
            "native_pptx_render": int((existing.get("counts") or {}).get("native_pptx_render", 0)),
        },
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _svg_stage(manifest_path: Path, out_dir: Path) -> tuple[dict, dict[str, float]]:
    durations: dict[str, float] = {}
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require_ready_route(manifest)
    for asset in manifest.get("assets", []):
        if asset.get("source_mode") == "external":
            asset_path = Path(asset["file"])
            if not asset_path.is_absolute():
                asset["file"] = str((manifest_path.parent / asset_path).resolve())
    _copy_measurement_artifacts(manifest, manifest_path, out_dir)
    _copy_background_artifacts(manifest, manifest_path, out_dir)
    _copy_generation_artifacts(manifest, manifest_path, out_dir)
    ascii_source = _ensure_ascii_source(manifest, manifest_path, out_dir)
    durations["prepare_package_evidence"] = time.perf_counter() - started

    # Use the ASCII source for script operations, but keep original source path
    # in a provenance field so Windows Unicode paths are not damaged.
    manifest.setdefault("provenance", {})["original_source_image"] = manifest["source_image"]
    manifest["source_image"] = str(ascii_source)
    _write_manifest(out_dir, manifest)

    started = time.perf_counter()
    crop_manifest_assets(out_dir / "manifest.json", out_dir)
    durations["crop_assets"] = time.perf_counter() - started
    started = time.perf_counter()
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    svg = build_svg(manifest)
    (out_dir / "editable.svg").write_text(svg, encoding="utf-8")
    durations["build_svg"] = time.perf_counter() - started
    started = time.perf_counter()
    embed(out_dir / "editable.svg", out_dir, out_dir / "editable_embedded.svg")
    _draw_placement_overlay(ascii_source, manifest, out_dir / "diagnostics" / "placement_overlay.png")
    durations["embed_and_overlay"] = time.perf_counter() - started
    started = time.perf_counter()
    gates = audit_and_write(out_dir)
    durations["quality_audit_and_preview"] = time.perf_counter() - started
    preview_path = out_dir / "preview.png"
    if preview_path.exists():
        started = time.perf_counter()
        try:
            from visual_compare_qa import compare as visual_compare  # type: ignore

            qa = visual_compare(Image.open(ascii_source), Image.open(preview_path), out_dir / "diagnostics" / "visual_qa")
            gates["visual_qa"] = {
                "status": "ok",
                "note": "report-only",
                "mean_delta_e": qa["mean_delta_e"],
                "p95_delta_e": qa["p95_delta_e"],
                "worst_tiles": qa["worst_tiles"][:5],
            }
        except Exception as exc:
            gates["visual_qa"] = {"status": "unavailable", "message": repr(exc)}
        durations["visual_compare"] = time.perf_counter() - started

        # Same difference, addressed to elements instead of tiles: the tile grid
        # says a region is wrong, this says which id is wrong and how, which is
        # what the next edit needs.
        started = time.perf_counter()
        try:
            from fix_worklist import build as build_worklist, draw_sheet as draw_fix_sheet  # type: ignore

            worklist = build_worklist(Path(ascii_source), preview_path, out_dir / "manifest.json")
            diag = out_dir / "diagnostics"
            diag.mkdir(parents=True, exist_ok=True)
            (diag / "fix_list.json").write_text(json.dumps(worklist, ensure_ascii=False, indent=2), encoding="utf-8")
            draw_fix_sheet(worklist, diag / "fix_sheet.png")
            gates["fix_worklist"] = {
                "status": "ok",
                "note": "report-only",
                "flagged": worklist["flagged"],
                "checked": worklist["checked"],
                "top": [{k: it[k] for k in ("id", "mean_delta_e", "hint")} for it in worklist["items"][:8]],
                "path": str(diag / "fix_list.json"),
            }
        except Exception as exc:
            gates["fix_worklist"] = {"status": "unavailable", "message": repr(exc)}
        durations["fix_worklist"] = time.perf_counter() - started
    started = time.perf_counter()
    editability = audit_editability(out_dir / "manifest.json", out_dir / "ocr_results.json" if (out_dir / "ocr_results.json").exists() else None)
    write_editability_report(out_dir, editability)
    leak_count = int(editability.get("formula_text_leak_count") or 0)
    gates["formula_text_leakage"] = {
        "status": "review" if leak_count else "ok",
        "count": leak_count,
        "samples": editability.get("formula_text_leak_samples", [])[:20],
    }
    svg_advisory = analyze_svg_stage(manifest)
    svg_advisory_path = out_dir / "diagnostics" / "svg_stage_report.json"
    svg_advisory_path.parent.mkdir(parents=True, exist_ok=True)
    svg_advisory_path.write_text(json.dumps(svg_advisory, ensure_ascii=False, indent=2), encoding="utf-8")
    gates["svg_stage_advisory"] = {"status": "ok", "note": "report-only", "count": svg_advisory["count"], "path": str(svg_advisory_path)}
    durations["editability_and_svg_advisory"] = time.perf_counter() - started
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["quality_gates"] = {**(manifest.get("quality_gates") or {}), **gates, "editability": editability}
    _write_manifest(out_dir, manifest)
    write_quality_report(out_dir, gates)
    return gates, durations


def _pptx_stage(out_dir: Path) -> tuple[dict, dict[str, float]]:
    editable_svg = out_dir / "editable.svg"
    manifest_path = out_dir / "manifest.json"
    if not editable_svg.exists() or not manifest_path.exists():
        raise FileNotFoundError("SVG stage outputs are missing; run --stage svg first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require_ready_route(manifest)
    gates = dict(manifest.get("quality_gates") or {})
    durations: dict[str, float] = {}

    started = time.perf_counter()
    try:
        pptx_path = out_dir / "editable.pptx"
        trace_path = out_dir / "editable.pptx.trace.json"
        export_native_pptx(editable_svg, out_dir, pptx_path, trace_path=trace_path)
        gates["pptx_export"] = {"status": "ok", "path": str(pptx_path), "trace": str(trace_path)}
        math_report_path = pptx_path.with_name(pptx_path.name + ".math_report.json")
        if math_report_path.exists():
            gates["pptx_math_export"] = json.loads(math_report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gates["pptx_export"] = {"status": "review", "message": repr(exc)}
    durations["export_native_pptx"] = time.perf_counter() - started

    started = time.perf_counter()
    text_fit = audit_pptx_text_fit(manifest)
    text_fit_path = out_dir / "diagnostics" / "pptx_text_fit.json"
    text_fit_path.parent.mkdir(parents=True, exist_ok=True)
    text_fit_path.write_text(json.dumps(text_fit, ensure_ascii=False, indent=2), encoding="utf-8")
    gates["pptx_text_fit"] = {
        "status": "ok",
        "note": "report-only; advisory_status is not a quality gate",
        "advisory_status": text_fit["status"],
        "risk_count": text_fit["risk_count"],
        "recommended_validation_tier": text_fit["recommended_validation_tier"],
        "path": str(text_fit_path),
    }
    durations["pptx_text_fit"] = time.perf_counter() - started

    manifest["quality_gates"] = gates
    _write_manifest(out_dir, manifest)
    write_quality_report(out_dir, gates)
    return gates, durations


def _package_stage(manifest_path: Path, out_dir: Path) -> tuple[dict, dict[str, float]]:
    editable_svg = out_dir / "editable.svg"
    pptx_path = out_dir / "editable.pptx"
    if not editable_svg.exists() or not pptx_path.exists():
        raise FileNotFoundError("Package stage requires editable.svg and editable.pptx.")
    if pptx_path.stat().st_mtime < editable_svg.stat().st_mtime:
        raise RuntimeError("editable.pptx is older than editable.svg; run --stage pptx before packaging.")
    started = time.perf_counter()
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require_ready_route(source_manifest)
    _copy_measurement_artifacts(source_manifest, manifest_path, out_dir)
    _copy_background_artifacts(source_manifest, manifest_path, out_dir)
    _copy_generation_artifacts(source_manifest, manifest_path, out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    gates = dict(manifest.get("quality_gates") or {})
    write_quality_report(out_dir, gates)
    return gates, {"refresh_package_artifacts": time.perf_counter() - started}


def compose(manifest_path: Path, out_dir: Path, stage: str = "full") -> dict:
    all_durations: dict[str, float] = {}
    gates: dict = {}
    if stage in {"svg", "full"}:
        gates, durations = _svg_stage(manifest_path, out_dir)
        all_durations.update({f"svg.{key}": value for key, value in durations.items()})
    if stage in {"pptx", "full"}:
        gates, durations = _pptx_stage(out_dir)
        all_durations.update({f"pptx.{key}": value for key, value in durations.items()})
    if stage in {"package", "full"}:
        gates, durations = _package_stage(manifest_path, out_dir)
        all_durations.update({f"package.{key}": value for key, value in durations.items()})
    timings = _append_timings(out_dir, stage, all_durations)
    return {"out_dir": str(out_dir), "stage": stage, "quality_gates": gates, "timings": timings["runs"][-1]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stage", choices=["svg", "pptx", "package"], help="Run only one stage; omit for the backward-compatible full pipeline.")
    args = parser.parse_args()
    result = compose(args.manifest.resolve(), args.out.resolve(), args.stage or "full")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
