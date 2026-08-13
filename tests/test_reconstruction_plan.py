from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate_manifest  # type: ignore  # noqa: E402
from compose_svg_package import _require_ready_route  # type: ignore  # noqa: E402
from validate_manifest import _validate_route_decision  # type: ignore  # noqa: E402


def base_manifest() -> dict:
    return {
        "canvas": {"width": 1000, "height": 600},
        "assets": [
            {
                "id": "asset-clean",
                "kind": "pictorial-icon",
                "decision": "crop",
                "crop_window": "clean",
                "x": 50,
                "y": 50,
                "w": 100,
                "h": 100,
            }
        ],
        "elements": [],
        "reconstruction_plan": {
            "edit_scope": "text+structure",
            "background_regions": [],
            "validation_tier": "svg-primary",
            "open_questions": [],
            "closeup_ids": [],
        },
    }


def blocked_manifest() -> dict:
    return {
        "canvas": {"width": 1000, "height": 600},
        "elements": [],
        "reconstruction_plan": {
            "edit_scope": "text+structure",
            "background_regions": [
                {
                    "id": "map",
                    "source_region": {"x": 10, "y": 10, "w": 200, "h": 150},
                    "strategy": "ai-clean-plate",
                    "foreground_mode": "pending-user-choice",
                    "reason": "labels overlap continuous map pixels",
                }
            ],
            "validation_tier": "svg-primary",
            "open_questions": [{"id": "map-depth", "question": "flatten or extract?"}],
            "closeup_ids": [],
        },
    }


class ReconstructionPlanTest(unittest.TestCase):
    def test_minimal_plan_passes(self) -> None:
        self.assertTrue(_validate_route_decision(base_manifest(), 1000, 600))

    def test_rejects_unknown_edit_scope(self) -> None:
        manifest = base_manifest()
        manifest["reconstruction_plan"]["edit_scope"] = "everything"
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_rejects_both_plan_and_legacy_route(self) -> None:
        manifest = base_manifest()
        manifest["route_decision"] = {"schema_version": 2}
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_open_questions_forbid_assets(self) -> None:
        manifest = blocked_manifest()
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))
        manifest["assets"] = [{"id": "asset-x", "decision": "crop", "crop_window": "clean"}]
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_ai_region_requires_background_plan(self) -> None:
        manifest = blocked_manifest()
        plan = manifest["reconstruction_plan"]
        plan["open_questions"] = []
        plan["background_regions"][0]["foreground_mode"] = "flatten"
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_pending_region_requires_open_question(self) -> None:
        manifest = blocked_manifest()
        manifest["reconstruction_plan"]["open_questions"] = []
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_compose_blocks_on_open_questions(self) -> None:
        with self.assertRaises(RuntimeError):
            _require_ready_route(blocked_manifest())

    def test_compose_allows_ready_plan(self) -> None:
        _require_ready_route(base_manifest())

    def test_inventory_route_must_match_asset_decision(self) -> None:
        manifest = base_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.json"
            inventory.write_text(
                json.dumps({"objects": [{"id": "asset-clean", "bbox": [1, 2, 3, 4], "route": "regenerate-chroma"}]}),
                encoding="utf-8",
            )
            manifest["reconstruction_plan"]["inventory"] = "inventory.json"
            previous = validate_manifest._MANIFEST_DIR
            validate_manifest._MANIFEST_DIR = tmp
            try:
                self.assertFalse(_validate_route_decision(manifest, 1000, 600))
                agreeing = copy.deepcopy(manifest)
                agreeing["assets"][0]["decision"] = "regenerate-chroma"
                self.assertTrue(_validate_route_decision(agreeing, 1000, 600))
            finally:
                validate_manifest._MANIFEST_DIR = previous


if __name__ == "__main__":
    unittest.main()
