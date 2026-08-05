#!/usr/bin/env python3
"""Batch-edit a FigEdit manifest. The official repair channel.

Replaces hand-editing large manifests and one-off patch scripts. Every run
backs up the manifest (manifest.json.bak, single overwriting copy), applies
the requested operations, then re-validates with validate_manifest.py; on
validation failure the backup is restored and the run exits non-zero.

Operations (combinable; applied in the order given below):

  --set "id1,id2:field=value"     assign; += -= *= for numeric fields;
                                  dotted paths reach nested dicts (source_region.x)
  --select "type=text&layer=labels" --set "fill=#333"
                                  assign to every element matching all pairs
  --apply-snap snap_report.json [--only clean,clean-on-fill]
                                  write crop_window verdict + snapped window into
                                  matching assets; contaminated items are listed
                                  on stderr for re-routing, never written
  --apply-fit fit_report.json     write font_size / x / baseline_y from
                                  fit_text.py output into matching text elements
  --ops ops.json                  file with [{"ids": [...], "set": {"field": value}}, ...]
  --dry-run                       print planned changes, write nothing

Targets are looked up by id across elements, assets, panels and
background_plans. A missing id is an error, not a silent skip.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

CONTAINERS = ("elements", "assets", "panels", "background_plans")


def _index_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for container in CONTAINERS:
        for item in manifest.get(container) or []:
            if isinstance(item, dict) and item.get("id"):
                index.setdefault(str(item["id"]), item)
    return index


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _resolve_path(item: dict[str, Any], path: str, create: bool = False) -> tuple[dict[str, Any], str]:
    parts = path.split(".")
    node = item
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            if not create:
                raise KeyError(f"path '{path}' not found (stopped at '{part}')")
            nxt = {}
            node[part] = nxt
        node = nxt
    return node, parts[-1]


def _apply_assign(item: dict[str, Any], path: str, op: str, raw_value: str, changes: list[str], item_id: str) -> None:
    value = _parse_value(raw_value)
    node, key = _resolve_path(item, path, create=(op == "="))
    old = node.get(key)
    if op == "=":
        new = value
    else:
        if not isinstance(old, (int, float)) or isinstance(old, bool):
            raise ValueError(f"{item_id}.{path} is not numeric (value: {old!r}); cannot apply '{op}'")
        if not isinstance(value, (int, float)):
            raise ValueError(f"operand for {item_id}.{path} {op} must be numeric, got {value!r}")
        new = old + value if op == "+=" else old - value if op == "-=" else old * value
        if isinstance(old, int) and isinstance(new, float) and new.is_integer():
            new = int(new)
    node[key] = new
    changes.append(f"{item_id}.{path}: {old!r} -> {new!r}")


def _split_assignment(spec: str) -> tuple[str, str, str]:
    for op in ("+=", "-=", "*="):
        if op in spec:
            path, raw = spec.split(op, 1)
            return path.strip(), op, raw.strip()
    if "=" in spec:
        path, raw = spec.split("=", 1)
        return path.strip(), "=", raw.strip()
    raise ValueError(f"assignment '{spec}' must contain =, +=, -= or *=")


def apply_set(index: dict[str, dict[str, Any]], spec: str, changes: list[str]) -> None:
    if ":" not in spec:
        raise ValueError(f"--set expects 'id1,id2:field=value', got '{spec}'")
    ids_part, assignment = spec.split(":", 1)
    path, op, raw = _split_assignment(assignment)
    for item_id in [part.strip() for part in ids_part.split(",") if part.strip()]:
        if item_id not in index:
            raise KeyError(f"id '{item_id}' not found in manifest")
        _apply_assign(index[item_id], path, op, raw, changes, item_id)


def apply_select(manifest: dict[str, Any], selector: str, assignments: list[str], changes: list[str]) -> None:
    pairs = []
    for clause in selector.split("&"):
        if "=" not in clause:
            raise ValueError(f"selector clause '{clause}' must be field=value")
        key, value = clause.split("=", 1)
        pairs.append((key.strip(), value.strip()))
    matched = 0
    for container in CONTAINERS:
        for item in manifest.get(container) or []:
            if not isinstance(item, dict):
                continue
            if all(str(item.get(key)) == value for key, value in pairs):
                matched += 1
                item_id = str(item.get("id", f"<{container} item>"))
                for assignment in assignments:
                    path, op, raw = _split_assignment(assignment)
                    _apply_assign(item, path, op, raw, changes, item_id)
    if matched == 0:
        raise KeyError(f"selector '{selector}' matched nothing")
    changes.append(f"(selector '{selector}' matched {matched} items)")


def apply_snap(index: dict[str, dict[str, Any]], report_path: Path, only: set[str], changes: list[str]) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    skipped_contaminated: list[str] = []
    for entry in report.get("objects", []):
        verdict = entry.get("verdict")
        item_id = str(entry.get("id", ""))
        if verdict in ("skipped", "snap-failed", None):
            continue
        if verdict == "contaminated":
            skipped_contaminated.append(f"{item_id} ({', '.join(entry.get('reasons', []))})")
            continue
        if verdict not in only:
            continue
        if item_id not in index:
            raise KeyError(f"snap report id '{item_id}' not found in manifest")
        item = index[item_id]
        window = entry.get("suggested_crop_window") or entry.get("snapped_bbox")
        if not window:
            continue
        x, y, w, h = window
        old_region = item.get("source_region")
        item["source_region"] = {"x": x, "y": y, "w": w, "h": h}
        item["crop_window"] = verdict
        changes.append(f"{item_id}.source_region: {old_region!r} -> {item['source_region']!r} (crop_window={verdict})")
    if skipped_contaminated:
        print(
            "contaminated, not written (re-route these to regenerate-chroma/flatten):\n  "
            + "\n  ".join(skipped_contaminated),
            file=sys.stderr,
        )


def apply_fit(index: dict[str, dict[str, Any]], report_path: Path, changes: list[str]) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for entry in report.get("items", []):
        item_id = str(entry.get("id", ""))
        if not item_id:
            continue
        if item_id not in index:
            raise KeyError(f"fit report id '{item_id}' not found in manifest")
        item = index[item_id]
        for source_key, target_key in (("font_size", "font_size"), ("x", "x"), ("baseline_y", "y")):
            if source_key in entry:
                old = item.get(target_key)
                item[target_key] = entry[source_key]
                changes.append(f"{item_id}.{target_key}: {old!r} -> {entry[source_key]!r}")


def apply_ops_file(index: dict[str, dict[str, Any]], ops_path: Path, changes: list[str]) -> None:
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    if not isinstance(ops, list):
        raise ValueError("--ops file must be a JSON array")
    for op in ops:
        ids = op.get("ids") or []
        for item_id in ids:
            if str(item_id) not in index:
                raise KeyError(f"ops id '{item_id}' not found in manifest")
            for path, value in (op.get("set") or {}).items():
                node, key = _resolve_path(index[str(item_id)], path, create=True)
                old = node.get(key)
                node[key] = value
                changes.append(f"{item_id}.{path}: {old!r} -> {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--set", dest="sets", action="append", default=[], metavar="SPEC")
    parser.add_argument("--select", dest="selector", metavar="FILTER")
    parser.add_argument("--apply-snap", dest="snap", type=Path)
    parser.add_argument("--only", default="clean,clean-on-fill")
    parser.add_argument("--apply-fit", dest="fit", type=Path)
    parser.add_argument("--ops", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-validate", action="store_true", help="skip re-validation (tests only)")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    original_text = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original_text)
    working = copy.deepcopy(manifest)
    index = _index_manifest(working)
    changes: list[str] = []

    try:
        if args.selector:
            if not args.sets:
                raise ValueError("--select requires at least one --set 'field=value'")
            apply_select(working, args.selector, args.sets, changes)
        else:
            for spec in args.sets:
                apply_set(index, spec, changes)
        if args.snap:
            apply_snap(index, args.snap.resolve(), {v.strip() for v in args.only.split(",")}, changes)
        if args.fit:
            apply_fit(index, args.fit.resolve(), changes)
        if args.ops:
            apply_ops_file(index, args.ops.resolve(), changes)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not changes:
        print("no changes")
        return 0
    print("\n".join(changes))
    if args.dry_run:
        print(f"(dry run: {len(changes)} changes not written)")
        return 0

    backup = manifest_path.with_suffix(manifest_path.suffix + ".bak")
    shutil.copyfile(manifest_path, backup)
    manifest_path.write_text(json.dumps(working, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_validate:
        validator = Path(__file__).parent / "validate_manifest.py"
        proc = subprocess.run(
            [sys.executable, str(validator), str(manifest_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            manifest_path.write_text(original_text, encoding="utf-8")
            print("validation failed, manifest restored:\n" + (proc.stdout + proc.stderr).strip(), file=sys.stderr)
            return 2
    print(f"wrote {len(changes)} changes (backup: {backup.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
