#!/usr/bin/env python3
"""Validate basic reconstruction manifest structure and route-specific invariants.

Usage:
  python scripts/validate_manifest.py manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


_MANIFEST_DIR: str | None = None


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_legacy_background_plan(manifest: dict[str, Any], width: float, height: float) -> bool:
    """Validate only the minimal AI clean-plate contract.

    Conventional FigEdit manifests should not include background_plan. When the
    field is present, it exists only for the ai-clean-plate route.
    """

    plan = manifest.get("background_plan")
    if plan is None:
        return True
    if not isinstance(plan, dict):
        error("background_plan must be an object when present.")
        return False

    ok = True
    strategy = plan.get("strategy")
    if strategy != "ai-clean-plate":
        error("background_plan is only for strategy 'ai-clean-plate'. Conventional routes should omit background_plan.")
        ok = False

    route_decision = plan.get("route_decision")
    if not isinstance(route_decision, dict):
        error("ai-clean-plate requires background_plan.route_decision.")
        ok = False
    else:
        reason = route_decision.get("reason") or route_decision.get("notes")
        if not _nonempty(reason):
            error("background_plan.route_decision must explain why crop + SVG cannot reconstruct the background.")
            ok = False

    plate_asset_id = plan.get("plate_asset_id")
    if not _nonempty(plate_asset_id):
        error("ai-clean-plate requires background_plan.plate_asset_id.")
        ok = False
        plate_asset = None
    else:
        plate_asset = next((asset for asset in manifest.get("assets", []) if asset.get("id") == plate_asset_id), None)
        if not isinstance(plate_asset, dict):
            error("background_plan.plate_asset_id must reference an asset.")
            ok = False

    if isinstance(plate_asset, dict):
        if not _nonempty(plate_asset.get("file")):
            error("ai-clean-plate plate asset must declare a file.")
            ok = False
        if plate_asset.get("kind") != "background-plate":
            error("ai-clean-plate plate asset should use kind='background-plate'.")
            ok = False
        px = _num(plate_asset.get("x"))
        py = _num(plate_asset.get("y"))
        pw = _num(plate_asset.get("w"))
        ph = _num(plate_asset.get("h"))
        if abs(px) > 1 or abs(py) > 1 or abs(pw - width) > max(1.0, width * 0.01) or abs(ph - height) > max(1.0, height * 0.01):
            error("ai-clean-plate plate asset should align to the full canvas.")
            ok = False

    provenance = plan.get("generation_provenance")
    if not isinstance(provenance, dict):
        error("ai-clean-plate requires background_plan.generation_provenance.")
        ok = False
    else:
        if not _nonempty(provenance.get("backend")) and not _nonempty(provenance.get("tool")) and not _nonempty(provenance.get("skill")):
            error("generation_provenance must name the backend, tool, or skill used.")
            ok = False
        if not _nonempty(provenance.get("output")):
            error("generation_provenance.output must point to the accepted clean plate.")
            ok = False
        if _nonempty(plate_asset.get("file") if isinstance(plate_asset, dict) else None) and _nonempty(provenance.get("output")):
            plate_name = Path(str(plate_asset.get("file"))).name.lower() if isinstance(plate_asset, dict) else ""
            output_name = Path(str(provenance.get("output"))).name.lower()
            if plate_name and output_name and plate_name != output_name:
                # The composer may later copy the generated plate into the out/assets
                # folder, but the manifest should not obscure which generated bitmap
                # was accepted. Treat a basename mismatch as an error because it often
                # indicates a stale or unrelated plate asset.
                error("plate asset file basename must match generation_provenance.output basename.")
                ok = False

    review = plan.get("candidate_review")
    if not isinstance(review, dict):
        error("ai-clean-plate requires background_plan.candidate_review.")
        ok = False
    elif review.get("accepted") is not True:
        error("ai-clean-plate candidate_review.accepted must be true for a deliverable manifest.")
        ok = False

    return ok


def _region_ok(region: Any, width: float, height: float, label: str) -> bool:
    if not isinstance(region, dict):
        error(f"{label} must be an object with x/y/w/h.")
        return False
    if not all(key in region for key in ("x", "y", "w", "h")):
        error(f"{label} must include x/y/w/h.")
        return False
    x, y = _num(region.get("x")), _num(region.get("y"))
    w, h = _num(region.get("w")), _num(region.get("h"))
    if w <= 0 or h <= 0:
        error(f"{label} must have positive width and height.")
        return False
    tolerance = 1.0
    if x < -tolerance or y < -tolerance or x + w > width + tolerance or y + h > height + tolerance:
        error(f"{label} must stay inside the canvas.")
        return False
    return True


def _same_region(left: dict[str, Any], right: dict[str, Any], tolerance: float = 1.0) -> bool:
    return all(abs(_num(left.get(key)) - _num(right.get(key))) <= tolerance for key in ("x", "y", "w", "h"))


def _validate_background_plan_v2(
    manifest: dict[str, Any],
    width: float,
    height: float,
    route: dict[str, Any],
) -> bool:
    plans = manifest.get("background_plans")
    if plans is None:
        plans = []
    if not isinstance(plans, list):
        error("background_plans must be an array when present.")
        return False

    ok = True
    scopes = {
        scope.get("id"): scope
        for scope in route.get("background_scopes", [])
        if isinstance(scope, dict) and _nonempty(scope.get("id"))
    }
    assets = {
        asset.get("id"): asset
        for asset in manifest.get("assets", [])
        if isinstance(asset, dict) and _nonempty(asset.get("id"))
    }
    plan_scope_ids: set[str] = set()

    for index, plan in enumerate(plans):
        label = f"background_plans[{index}]"
        if not isinstance(plan, dict):
            error(f"{label} must be an object.")
            ok = False
            continue
        scope_id = plan.get("scope_id")
        if not _nonempty(scope_id) or scope_id not in scopes:
            error(f"{label}.scope_id must reference route_decision.background_scopes[].id.")
            ok = False
            continue
        if scope_id in plan_scope_ids:
            error(f"Duplicate background plan for scope: {scope_id}")
            ok = False
        plan_scope_ids.add(scope_id)
        scope = scopes[scope_id]
        if scope.get("region_accuracy") != "measured":
            error(f"{label} cannot execute until its route scope region_accuracy is measured.")
            ok = False
        if scope.get("strategy") != "ai-clean-plate" or plan.get("strategy") != "ai-clean-plate":
            error(f"{label} must correspond to an ai-clean-plate scope.")
            ok = False

        source_region = plan.get("source_region")
        if not _region_ok(source_region, width, height, f"{label}.source_region"):
            ok = False
        elif not _same_region(source_region, scope.get("source_region", {})):
            error(f"{label}.source_region must match its route scope.")
            ok = False

        mode = plan.get("foreground_mode")
        if mode not in {"full-extract", "selective", "flatten"}:
            error(f"{label}.foreground_mode must be full-extract, selective, or flatten.")
            ok = False
        elif mode != scope.get("foreground_mode"):
            error(f"{label}.foreground_mode must match its route scope.")
            ok = False
        if plan.get("foreground_mode_source") not in {"user-choice", "explicit-request", "auto-default"}:
            error(f"{label}.foreground_mode_source is required.")
            ok = False
        if not _nonempty(plan.get("route_reason")):
            error(f"{label}.route_reason is required.")
            ok = False

        plate_asset_id = plan.get("plate_asset_id")
        plate_asset = assets.get(plate_asset_id)
        if not _nonempty(plate_asset_id) or not isinstance(plate_asset, dict):
            error(f"{label}.plate_asset_id must reference an asset.")
            ok = False
        else:
            if plate_asset.get("kind") != "background-plate" or not _nonempty(plate_asset.get("file")):
                error(f"{label} plate asset must have kind='background-plate' and a file.")
                ok = False
            asset_region = {key: plate_asset.get(key) for key in ("x", "y", "w", "h")}
            if not _same_region(asset_region, source_region if isinstance(source_region, dict) else {}):
                error(f"{label} plate asset placement must match source_region.")
                ok = False

        provenance = plan.get("generation_provenance")
        if not isinstance(provenance, dict):
            error(f"{label}.generation_provenance is required.")
            ok = False
        else:
            if not any(_nonempty(provenance.get(key)) for key in ("backend", "tool", "skill")):
                error(f"{label}.generation_provenance must name the backend, tool, or skill.")
                ok = False
            if not _nonempty(provenance.get("output")):
                error(f"{label}.generation_provenance.output is required.")
                ok = False
            elif isinstance(plate_asset, dict) and _nonempty(plate_asset.get("file")):
                if Path(str(plate_asset["file"])).name.lower() != Path(str(provenance["output"])).name.lower():
                    error(f"{label} plate asset basename must match generation_provenance.output.")
                    ok = False

        review = plan.get("candidate_review")
        if not isinstance(review, dict) or review.get("accepted") is not True:
            error(f"{label}.candidate_review.accepted must be true for a deliverable manifest.")
            ok = False

    ai_scope_ids = {
        scope_id for scope_id, scope in scopes.items() if scope.get("strategy") == "ai-clean-plate"
    }
    if route.get("route_status") == "ready" and ai_scope_ids != plan_scope_ids:
        missing = sorted(ai_scope_ids - plan_scope_ids)
        extra = sorted(plan_scope_ids - ai_scope_ids)
        if missing:
            error(f"Ready route is missing background_plans for scopes: {', '.join(missing)}")
        if extra:
            error(f"background_plans reference non-AI scopes: {', '.join(extra)}")
        ok = False
    return ok


def _validate_reconstruction_plan(manifest: dict[str, Any], width: float, height: float) -> bool:
    """Validate the reconstruction_plan block (the current planning schema)."""

    plan = manifest["reconstruction_plan"]
    if not isinstance(plan, dict):
        error("reconstruction_plan must be an object.")
        return False
    ok = True
    if manifest.get("route_decision") is not None:
        error("manifest has both reconstruction_plan and legacy route_decision; keep only reconstruction_plan.")
        ok = False

    if plan.get("edit_scope") not in {"text-only", "text+structure", "selective-assets", "full-extract"}:
        error("reconstruction_plan.edit_scope must be text-only, text+structure, selective-assets or full-extract.")
        ok = False
    if plan.get("validation_tier") not in {"svg-primary", "pptx-triggered"}:
        error("reconstruction_plan.validation_tier must be svg-primary or pptx-triggered.")
        ok = False

    open_questions = plan.get("open_questions", [])
    if not isinstance(open_questions, list):
        error("reconstruction_plan.open_questions must be an array.")
        ok = False
        open_questions = []
    for index, item in enumerate(open_questions):
        if not isinstance(item, dict) or not _nonempty(item.get("id")) or not _nonempty(item.get("question")):
            error(f"reconstruction_plan.open_questions[{index}] must include a non-empty id and question.")
            ok = False

    closeups = plan.get("closeup_ids", [])
    if not isinstance(closeups, list) or not all(_nonempty(item) for item in closeups):
        error("reconstruction_plan.closeup_ids must be an array of non-empty strings when present.")
        ok = False

    regions = plan.get("background_regions", [])
    if not isinstance(regions, list):
        error("reconstruction_plan.background_regions must be an array when present.")
        ok = False
        regions = []
    region_ids: set[str] = set()
    has_pending = False
    for index, region in enumerate(regions):
        label = f"reconstruction_plan.background_regions[{index}]"
        if not isinstance(region, dict):
            error(f"{label} must be an object.")
            ok = False
            continue
        region_id = region.get("id")
        if not _nonempty(region_id) or region_id in region_ids:
            error(f"{label}.id must be a unique non-empty string.")
            ok = False
        else:
            region_ids.add(region_id)
        if region.get("strategy") not in {"ai-clean-plate", "source-preserve-region"}:
            error(f"{label}.strategy must be ai-clean-plate or source-preserve-region.")
            ok = False
        if not _region_ok(region.get("source_region"), width, height, f"{label}.source_region"):
            ok = False
        if not _nonempty(region.get("reason")):
            error(f"{label}.reason is required.")
            ok = False
        mode = region.get("foreground_mode")
        if region.get("strategy") == "ai-clean-plate":
            if mode not in {"flatten", "selective", "full-extract", "pending-user-choice"}:
                error(f"{label}.foreground_mode is required for ai-clean-plate regions.")
                ok = False
            if mode == "pending-user-choice":
                has_pending = True

    if open_questions:
        if manifest.get("assets") or manifest.get("background_plans"):
            error("reconstruction_plan.open_questions is not empty; assets and background_plans must not exist yet.")
            ok = False
    elif has_pending:
        error("pending-user-choice regions require a matching entry in open_questions.")
        ok = False

    # The plan schema has no estimated/measured flag: rough survey coordinates
    # are tightened in place during measurement, and a background plan only
    # exists once that has happened. Satisfy the shared checker accordingly.
    shim_route = {
        "background_scopes": [
            {**region, "region_accuracy": "measured"} for region in regions if isinstance(region, dict)
        ],
        "route_status": "ready" if not open_questions else "needs-user-input",
    }
    if not _validate_background_plan_v2(manifest, width, height, shim_route):
        ok = False

    inventory_ref = plan.get("inventory")
    if inventory_ref is not None and not _nonempty(inventory_ref):
        error("reconstruction_plan.inventory must be a non-empty path when present.")
        ok = False
    inventory_path = None
    if _nonempty(inventory_ref):
        base = Path(_MANIFEST_DIR) if _MANIFEST_DIR else Path.cwd()
        candidate = (base / str(inventory_ref)).resolve()
        if candidate.exists():
            inventory_path = candidate
    if inventory_path is not None:
        try:
            data = json.loads(inventory_path.read_text(encoding="utf-8"))
            objects = data.get("objects", data) if isinstance(data, dict) else data
            routes = {
                str(obj.get("id")): str(obj.get("route"))
                for obj in objects
                if isinstance(obj, dict) and _nonempty(obj.get("id"))
            }
        except Exception as exc:  # noqa: BLE001
            error(f"reconstruction_plan.inventory could not be read: {exc}")
            return False
        for asset in manifest.get("assets", []):
            if not isinstance(asset, dict):
                continue
            asset_id = str(asset.get("id"))
            route = routes.get(asset_id)
            if route in {"crop", "regenerate-chroma"} and str(asset.get("decision", "")).lower() != route:
                error(f"Asset {asset_id} decision contradicts the inventory route ({route}).")
                ok = False
    return ok


def _validate_route_decision(manifest: dict[str, Any], width: float, height: float) -> bool:
    """Dispatch plan validation: reconstruction_plan first, legacy route_decision otherwise."""

    if "reconstruction_plan" in manifest:
        return _validate_reconstruction_plan(manifest, width, height)

    route = manifest.get("route_decision")
    if route is None:
        return True
    print("note: route_decision is deprecated; new manifests should write reconstruction_plan.", file=sys.stderr)
    if not isinstance(route, dict):
        error("route_decision must be an object when present.")
        return False

    if route.get("schema_version") != 2:
        ok = True
        allowed = {
            "source": {"global-read", "user-directive"},
            "editability_depth": {"text-only", "text+structure", "selective-assets", "full-extract"},
            "reconstruction_route": {"regular-hybrid", "ai-clean-plate"},
            "validation_tier": {"svg-primary", "pptx-triggered"},
        }
        for field, values in allowed.items():
            value = route.get(field)
            if value not in values:
                error(f"route_decision.{field} must be one of: {', '.join(sorted(values))}")
                ok = False

        exceptions = route.get("exception_ids")
        if not isinstance(exceptions, list) or not all(_nonempty(item) for item in exceptions):
            error("route_decision.exception_ids must be an array of non-empty strings.")
            ok = False

        reconstruction_route = route.get("reconstruction_route")
        has_background_plan = isinstance(manifest.get("background_plan"), dict)
        if reconstruction_route == "ai-clean-plate" and not has_background_plan:
            error("route_decision selects ai-clean-plate but background_plan is missing.")
            ok = False
        if reconstruction_route == "regular-hybrid" and has_background_plan:
            error("route_decision selects regular-hybrid but background_plan is present.")
            ok = False
        return ok

    ok = True
    allowed = {
        "source": {"fresh-global-read", "user-directive"},
        "editability_depth": {"text-only", "text+structure", "selective-assets", "full-extract"},
        "route_status": {"ready", "needs-user-input"},
        "base_strategy": {"svg-rebuild"},
        "validation_tier": {"svg-primary", "pptx-triggered"},
    }
    for field, values in allowed.items():
        value = route.get(field)
        if value not in values:
            error(f"route_decision.{field} must be one of: {', '.join(sorted(values))}")
            ok = False

    for field in ("background_scopes", "asset_groups", "unresolved_decisions"):
        if not isinstance(route.get(field), list):
            error(f"route_decision.{field} must be an array in schema_version 2.")
            ok = False

    scopes = route.get("background_scopes") if isinstance(route.get("background_scopes"), list) else []
    scope_ids: set[str] = set()
    inventory_routes: dict[str, str] = {}
    has_pending = False
    for index, scope in enumerate(scopes):
        label = f"route_decision.background_scopes[{index}]"
        if not isinstance(scope, dict):
            error(f"{label} must be an object.")
            ok = False
            continue
        scope_id = scope.get("id")
        if not _nonempty(scope_id) or scope_id in scope_ids:
            error(f"{label}.id must be a unique non-empty string.")
            ok = False
        else:
            scope_ids.add(scope_id)
        if scope.get("strategy") not in {"ai-clean-plate", "source-preserve-region"}:
            error(f"{label}.strategy is unsupported.")
            ok = False
        if scope.get("field_type") not in {"continuous-field", "self-contained-raster"}:
            error(f"{label}.field_type must be continuous-field or self-contained-raster.")
            ok = False
        if scope.get("region_accuracy") not in {"estimated-from-global-read", "measured"}:
            error(f"{label}.region_accuracy must be estimated-from-global-read or measured.")
            ok = False
        if not _region_ok(scope.get("source_region"), width, height, f"{label}.source_region"):
            ok = False
        if not _nonempty(scope.get("reason")):
            error(f"{label}.reason is required.")
            ok = False
        mode = scope.get("foreground_mode")
        if scope.get("strategy") == "ai-clean-plate" and mode not in {"full-extract", "selective", "flatten", "pending-user-choice"}:
            error(f"{label}.foreground_mode is required for ai-clean-plate scopes.")
            ok = False
        if mode == "pending-user-choice":
            has_pending = True
        inventory = scope.get("foreground_inventory", [])
        if not isinstance(inventory, list):
            error(f"{label}.foreground_inventory must be an array when present.")
            ok = False
            inventory = []
        if mode == "pending-user-choice" and not inventory:
            error(f"{label} pending-user-choice requires a concrete foreground_inventory.")
            ok = False
        for item_index, item in enumerate(inventory):
            item_label = f"{label}.foreground_inventory[{item_index}]"
            if not isinstance(item, dict) or not _nonempty(item.get("id")):
                error(f"{item_label}.id is required.")
                ok = False
                continue
            if item.get("kind") != "source-specific-visual":
                error(f"{item_label}.kind must be source-specific-visual.")
                ok = False
            resolved = item.get("resolved_strategy")
            if resolved not in {"pending-user-choice", "flatten", "regenerate-chroma"}:
                error(f"{item_label}.resolved_strategy is unsupported.")
                ok = False
                continue
            if item["id"] in inventory_routes:
                error(f"Foreground inventory id appears in multiple scopes: {item['id']}")
                ok = False
            inventory_routes[item["id"]] = resolved
            if mode == "pending-user-choice" and resolved != "pending-user-choice":
                error(f"{item_label} must remain pending while its scope is pending-user-choice.")
                ok = False
            if mode != "pending-user-choice" and resolved == "pending-user-choice":
                error(f"{item_label} must be resolved before route_status can be ready.")
                ok = False
            if mode == "flatten" and resolved != "flatten":
                error(f"{item_label} must resolve to flatten for a flatten scope.")
                ok = False
            if mode == "full-extract" and resolved != "regenerate-chroma":
                error(f"{item_label} must resolve to regenerate-chroma for a full-extract scope.")
                ok = False
        if (
            scope.get("strategy") == "source-preserve-region"
            and scope.get("field_type") == "continuous-field"
            and not _nonempty(scope.get("user_directive"))
        ):
            error(f"{label} may preserve a continuous field only with an explicit user_directive.")
            ok = False

    unresolved = route.get("unresolved_decisions") if isinstance(route.get("unresolved_decisions"), list) else []
    unresolved_scope_ids: set[str] = set()
    for index, item in enumerate(unresolved):
        label = f"route_decision.unresolved_decisions[{index}]"
        if not isinstance(item, dict) or not _nonempty(item.get("id")) or not _nonempty(item.get("question")):
            error(f"{label} must include a non-empty id and question.")
            ok = False
            continue
        scope_id = item.get("scope_id")
        if _nonempty(scope_id):
            unresolved_scope_ids.add(scope_id)
            if scope_id not in scope_ids:
                error(f"{label}.scope_id must reference a background scope.")
                ok = False

    if route.get("route_status") == "ready" and (has_pending or unresolved):
        error("route_status ready requires no pending-user-choice scopes and no unresolved_decisions.")
        ok = False
    if route.get("route_status") == "needs-user-input" and not unresolved:
        error("route_status needs-user-input requires unresolved_decisions.")
        ok = False
    pending_scope_ids = {
        scope.get("id") for scope in scopes if isinstance(scope, dict) and scope.get("foreground_mode") == "pending-user-choice"
    }
    if pending_scope_ids - unresolved_scope_ids:
        error("Every pending-user-choice scope must have a matching unresolved_decision.")
        ok = False

    groups = route.get("asset_groups") if isinstance(route.get("asset_groups"), list) else []
    grouped_ids: dict[str, str] = {}
    allowed_strategies = {"redraw", "crop", "regenerate-chroma", "flatten", "preserve-raster", "omit"}
    allowed_separability = {"not-applicable", "clean", "clean-on-fill", "contaminated", "embedded-in-continuous-field"}
    assets = {
        asset.get("id"): asset
        for asset in manifest.get("assets", [])
        if isinstance(asset, dict) and _nonempty(asset.get("id"))
    }
    for index, group in enumerate(groups):
        label = f"route_decision.asset_groups[{index}]"
        if not isinstance(group, dict) or group.get("strategy") not in allowed_strategies:
            error(f"{label}.strategy is unsupported.")
            ok = False
            continue
        separability = group.get("separability")
        if separability not in allowed_separability:
            error(f"{label}.separability is required and unsupported values are rejected.")
            ok = False
        if group.get("strategy") == "crop" and separability not in {"clean", "clean-on-fill"}:
            error(f"{label} may crop only a clean or clean-on-fill group.")
            ok = False
        if group.get("strategy") == "regenerate-chroma" and separability != "contaminated":
            error(f"{label} regenerate-chroma requires separability=contaminated.")
            ok = False
        overlaps = group.get("observed_overlap")
        if separability == "contaminated" and (not isinstance(overlaps, list) or not overlaps or not all(_nonempty(item) for item in overlaps)):
            error(f"{label} contaminated groups must list observed_overlap evidence from the whole image.")
            ok = False
        ids = group.get("ids")
        if not isinstance(ids, list) or not ids or not all(_nonempty(item) for item in ids):
            error(f"{label}.ids must be a non-empty string array.")
            ok = False
            continue
        if not _nonempty(group.get("reason")):
            error(f"{label}.reason is required.")
            ok = False
        for asset_id in ids:
            if asset_id in grouped_ids:
                error(f"Asset route id {asset_id} appears in multiple groups.")
                ok = False
            grouped_ids[asset_id] = group["strategy"]
            asset = assets.get(asset_id)
            if not isinstance(asset, dict):
                continue
            decision = str(asset.get("decision", "")).lower()
            if group["strategy"] == "crop":
                if decision != "crop" or asset.get("crop_window") not in {"clean", "clean-on-fill"}:
                    error(f"Asset {asset_id} may use crop only with decision=crop and a clean crop_window.")
                    ok = False
                elif asset.get("crop_window") != separability:
                    error(f"Asset {asset_id} crop_window must match its route separability verdict.")
                    ok = False
            elif group["strategy"] == "regenerate-chroma" and decision != "regenerate-chroma":
                error(f"Asset {asset_id} must use decision=regenerate-chroma.")
                ok = False
            elif group["strategy"] in {"flatten", "preserve-raster", "omit"} and decision != group["strategy"]:
                error(f"Asset {asset_id} decision must match route strategy {group['strategy']}.")
                ok = False

    for asset in assets.values():
        if str(asset.get("decision", "")).lower() == "crop" and str(asset.get("crop_window", "")).lower() == "contaminated":
            error(f"Asset {asset.get('id')} is contaminated and cannot use decision=crop.")
            ok = False
    if route.get("route_status") == "ready":
        for item_id, resolved in inventory_routes.items():
            if grouped_ids.get(item_id) != resolved:
                error(f"Resolved foreground inventory {item_id} must appear in asset_groups with strategy={resolved}.")
                ok = False
    unrouted = sorted(
        asset_id
        for asset_id, asset in assets.items()
        if asset.get("kind") not in {"background-plate", "formula", "math"} and asset_id not in grouped_ids
    )
    if unrouted:
        error(f"Route Decision v2 must classify every non-background asset: {', '.join(unrouted)}")
        ok = False

    if isinstance(manifest.get("background_plan"), dict):
        error("Route schema_version 2 must use background_plans[], not legacy background_plan.")
        ok = False
    if not _validate_background_plan_v2(manifest, width, height, route):
        ok = False
    return ok


def _validate_marker_spec(element: dict[str, Any], field: str) -> bool:
    spec = element.get(field)
    if spec is None:
        return True
    if not isinstance(spec, dict):
        error(f"Element {element.get('id')} {field} must be an object or null.")
        return False

    ok = True
    style = spec.get("style", "solid-triangle")
    if style not in {"solid-triangle", "open-chevron", "circle", "diamond"}:
        error(f"Element {element.get('id')} {field}.style is unsupported: {style}")
        ok = False
    try:
        if float(spec.get("size", 7)) <= 0:
            raise ValueError
    except Exception:
        error(f"Element {element.get('id')} {field}.size must be positive.")
        ok = False
    if "at" in spec:
        try:
            at = float(spec["at"])
            if at < 0 or at > 1:
                raise ValueError
        except Exception:
            error(f"Element {element.get('id')} {field}.at must be between 0 and 1.")
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    global _MANIFEST_DIR
    _MANIFEST_DIR = str(args.manifest.resolve().parent)
    ok = True

    for key in ["project", "source_image", "canvas", "classification", "assets", "elements"]:
        if key not in manifest:
            error(f"Missing required key: {key}")
            ok = False

    canvas = manifest.get("canvas", {})
    width = _num(canvas.get("width"))
    height = _num(canvas.get("height"))
    if width <= 0 or height <= 0:
        error("Canvas width/height must be positive.")
        ok = False

    ids: set[str] = set()
    for group_name in ["panels", "assets", "elements"]:
        for item in manifest.get(group_name, []):
            item_id = item.get("id")
            if item_id:
                if item_id in ids:
                    error(f"Duplicate id: {item_id}")
                    ok = False
                ids.add(item_id)

    for asset in manifest.get("assets", []):
        for k in ["x", "y", "w", "h"]:
            if k not in asset:
                error(f"Asset {asset.get('id')} missing {k}")
                ok = False
        x = _num(asset.get("x"))
        y = _num(asset.get("y"))
        w = _num(asset.get("w"))
        h = _num(asset.get("h"))
        if w <= 0 or h <= 0:
            error(f"Asset {asset.get('id')} has non-positive size.")
            ok = False
        if x > width or y > height or x + w < 0 or y + h < 0:
            error(f"Asset {asset.get('id')} is outside canvas.")
            ok = False
        source_region = asset.get("source_region")
        if source_region:
            for k in ["x", "y", "w", "h"]:
                if k not in source_region:
                    error(f"Asset {asset.get('id')} source_region missing {k}")
                    ok = False
        if "edge_check" in asset and not isinstance(asset["edge_check"], dict):
            error(f"Asset {asset.get('id')} edge_check must be an object.")
            ok = False
        source_mode = asset.get("source_mode")
        if source_mode and source_mode not in {"source-crop", "external", "generated", "embedded", "manual"}:
            error(f"Asset {asset.get('id')} has unsupported source_mode: {source_mode}")
            ok = False

    for element in manifest.get("elements", []):
        typ = element.get("type")
        if typ == "image":
            href = element.get("href")
            asset_id = element.get("asset_id")
            if not href and not asset_id:
                error(f"Image element {element.get('id')} missing href or asset_id.")
                ok = False
        if "confidence" in element:
            try:
                confidence = float(element["confidence"])
                if confidence < 0 or confidence > 1:
                    error(f"Element {element.get('id')} confidence must be between 0 and 1.")
                    ok = False
            except Exception:
                error(f"Element {element.get('id')} confidence must be numeric.")
                ok = False
        source_bbox = element.get("source_bbox")
        if source_bbox:
            for k in ["x", "y", "w", "h"]:
                if k not in source_bbox:
                    error(f"Element {element.get('id')} source_bbox missing {k}")
                    ok = False
        for marker_field in ["marker_start", "marker_end", "marker_mid"]:
            if not _validate_marker_spec(element, marker_field):
                ok = False
        if "connector_clearance" in element:
            try:
                if float(element["connector_clearance"]) < 0:
                    raise ValueError
            except Exception:
                error(f"Element {element.get('id')} connector_clearance must be a non-negative number.")
                ok = False

    for optional_object in ["style_tokens", "diagnostics", "quality_gates", "recognition_summary", "asset_decision_policy"]:
        if optional_object in manifest and not isinstance(manifest[optional_object], dict):
            error(f"{optional_object} must be an object when present.")
            ok = False

    if not _validate_route_decision(manifest, width, height):
        ok = False

    route = manifest.get("route_decision")
    if "reconstruction_plan" not in manifest and (not isinstance(route, dict) or route.get("schema_version") != 2):
        if not _validate_legacy_background_plan(manifest, width, height):
            ok = False

    if ok:
        print("Manifest validation passed.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
