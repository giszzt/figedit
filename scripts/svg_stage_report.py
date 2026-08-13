#!/usr/bin/env python3
"""Advisory checks that should surface before PPTX export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def analyze(manifest: dict[str, Any]) -> dict[str, Any]:
    advisories: list[dict[str, Any]] = []
    for element in manifest.get("elements", []):
        element_id = str(element.get("id") or "")
        typ = element.get("type")
        joined = " ".join(str(element.get(key, "")) for key in ("id", "class", "decision_reason", "notes")).lower()
        if typ == "polygon" and ("arrow" in joined or "connector" in joined):
            advisories.append({"id": element_id, "kind": "manual-arrow", "message": "polygon appears to be a hand-drawn arrow; prefer marker_start/marker_end"})
        if typ in {"line", "path", "polyline"}:
            has_marker = any(element.get(field) for field in ("marker_start", "marker_end", "marker_mid", "arrow_start", "arrow_end"))
            if "arrow" in joined and not has_marker:
                advisories.append({"id": element_id, "kind": "missing-marker", "message": "arrow-like connector has no marker declaration"})
        if typ == "text":
            if "var(--font-" in str(element.get("font_family", "")):
                advisories.append({"id": element_id, "kind": "font-variable", "message": "font variable should be resolved before PPTX export"})
            source_slot = element.get("source_region") or element.get("source_bbox")
            if not source_slot:
                advisories.append({"id": element_id, "kind": "missing-source-slot", "message": "text has no source slot; review only when layout is dense"})
            slot_has_bounds = isinstance(source_slot, dict) and source_slot.get("w") and source_slot.get("h")
            if (not element.get("w") or not element.get("h")) and not slot_has_bounds:
                advisories.append({"id": element_id, "kind": "missing-text-bounds", "message": "text has no explicit width/height for static fit audit"})
    return {"status": "advisory", "count": len(advisories), "items": advisories}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.manifest.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
