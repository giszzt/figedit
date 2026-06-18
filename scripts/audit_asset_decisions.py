#!/usr/bin/env python3
"""Audit a reconstruction manifest for likely over-vectorization.

This script flags redrawn elements whose subtype/kind/description suggests they may be
source-specific visual assets that should have been cropped instead.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SUSPICIOUS_TERMS = {
    "icon", "pictogram", "logo", "mark", "photo", "screenshot", "map", "thumbnail",
    "illustration", "avatar", "face", "person", "clothing", "drone", "camera",
    "phone", "ui", "route", "city", "terrain", "model", "database", "folder",
    "document", "product", "collage", "hand-drawn", "custom"
}

SAFE_STRUCTURAL_TERMS = {
    "panel", "card", "frame", "divider", "separator", "arrow", "connector",
    "line", "grid", "table", "background", "rect", "circle", "dot", "plus",
    "check", "cross", "rule"
}


def text_blob(obj: dict) -> str:
    values = []
    for key in ("id", "class", "subtype", "kind", "description", "notes", "decision_reason"):
        value = obj.get(key)
        if value:
            values.append(str(value).lower())
    return " ".join(values)


def audit_manifest(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    warnings: list[str] = []

    for element in data.get("elements", []):
        decision = str(element.get("decision", "")).lower()
        if decision not in {"redraw", "simplify", "semantic-redraw"}:
            continue
        blob = text_blob(element)
        has_suspicious = any(term in blob for term in SUSPICIOUS_TERMS)
        has_safe = any(term in blob for term in SAFE_STRUCTURAL_TERMS)
        if has_suspicious and not has_safe:
            warnings.append(
                f"Possible over-vectorization: element '{element.get('id', '<unnamed>')}' "
                f"uses decision='{decision}' but appears pictorial/source-specific. Consider crop."
            )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    warnings = audit_manifest(args.manifest)
    if warnings:
        for warning in warnings:
            print("WARNING:", warning)
        return 1

    print("No likely over-vectorization issues found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
