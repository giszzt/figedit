from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from compose_svg_package import _require_ready_route  # type: ignore  # noqa: E402
from build_svg_from_manifest import build_svg  # type: ignore  # noqa: E402
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
        "route_decision": {
            "schema_version": 2,
            "source": "fresh-global-read",
            "route_status": "ready",
            "editability_depth": "text+structure",
            "base_strategy": "svg-rebuild",
            "background_scopes": [],
            "asset_groups": [
                {
                    "strategy": "crop",
                    "ids": ["asset-clean"],
                    "separability": "clean",
                    "reason": "The whole-image read shows an intact object with no foreign pixels in its crop window.",
                }
            ],
            "unresolved_decisions": [],
            "validation_tier": "svg-primary",
            "exception_ids": [],
        },
    }


class RouteDecisionV2Tests(unittest.TestCase):
    def test_clean_crop_route_passes(self) -> None:
        manifest = base_manifest()
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))

    def test_contaminated_object_cannot_remain_crop(self) -> None:
        manifest = base_manifest()
        group = manifest["route_decision"]["asset_groups"][0]
        group["separability"] = "contaminated"
        group["observed_overlap"] = ["card border", "label"]
        manifest["assets"][0]["crop_window"] = "contaminated"
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

    def test_contaminated_object_can_regenerate(self) -> None:
        manifest = base_manifest()
        group = manifest["route_decision"]["asset_groups"][0]
        group.update(
            {
                "strategy": "regenerate-chroma",
                "separability": "contaminated",
                "observed_overlap": ["card border", "label"],
            }
        )
        manifest["assets"][0].update(
            {"decision": "regenerate-chroma", "source_mode": "external", "crop_window": "contaminated"}
        )
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))

    def test_pending_continuous_field_blocks_composition(self) -> None:
        manifest = base_manifest()
        manifest["assets"] = []
        route = manifest["route_decision"]
        route["route_status"] = "needs-user-input"
        route["asset_groups"] = []
        route["background_scopes"] = [
            {
                "id": "map-region",
                "source_region": {"x": 600, "y": 0, "w": 400, "h": 600},
                "region_accuracy": "estimated-from-global-read",
                "field_type": "continuous-field",
                "strategy": "ai-clean-plate",
                "foreground_mode": "pending-user-choice",
                "foreground_inventory": [
                    {
                        "id": "map-person",
                        "kind": "source-specific-visual",
                        "resolved_strategy": "pending-user-choice",
                    }
                ],
                "reason": "Routes and labels obscure continuous map pixels.",
            }
        ]
        route["unresolved_decisions"] = [
            {
                "id": "map-depth",
                "type": "foreground-depth",
                "scope_id": "map-region",
                "question": "Flatten, selectively extract, or fully extract this region?",
            }
        ]
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))
        with self.assertRaises(RuntimeError):
            _require_ready_route(manifest)

    def test_ready_regional_clean_plate_requires_plan(self) -> None:
        manifest = base_manifest()
        manifest["assets"] = []
        route = manifest["route_decision"]
        route["asset_groups"] = []
        route["background_scopes"] = [
            {
                "id": "map-region",
                "source_region": {"x": 600, "y": 0, "w": 400, "h": 600},
                "region_accuracy": "measured",
                "field_type": "continuous-field",
                "strategy": "ai-clean-plate",
                "foreground_mode": "flatten",
                "reason": "Editable labels obscure continuous map pixels.",
            }
        ]
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))

        valid = copy.deepcopy(manifest)
        valid["assets"] = [
            {
                "id": "plate-map",
                "kind": "background-plate",
                "file": "clean-map.png",
                "x": 600,
                "y": 0,
                "w": 400,
                "h": 600,
            }
        ]
        valid["background_plans"] = [
            {
                "scope_id": "map-region",
                "strategy": "ai-clean-plate",
                "source_region": {"x": 600, "y": 0, "w": 400, "h": 600},
                "foreground_mode": "flatten",
                "foreground_mode_source": "user-choice",
                "route_reason": "Editable labels obscure continuous map pixels.",
                "plate_asset_id": "plate-map",
                "generation_provenance": {"backend": "test", "output": "clean-map.png"},
                "candidate_review": {"accepted": True},
            }
        ]
        self.assertTrue(_validate_route_decision(valid, 1000, 600))
        svg = build_svg(valid)
        self.assertIn('x="600" y="0" width="400" height="600"', svg)
        self.assertNotIn('id="background-plate-map-region" href="clean-map.png" x="0"', svg)

    def test_self_contained_raster_can_be_preserved_without_route_override(self) -> None:
        manifest = base_manifest()
        manifest["route_decision"]["background_scopes"] = [
            {
                "id": "screenshot-region",
                "source_region": {"x": 500, "y": 50, "w": 400, "h": 300},
                "region_accuracy": "estimated-from-global-read",
                "field_type": "self-contained-raster",
                "strategy": "source-preserve-region",
                "reason": "The screenshot is complete and has no internal foreground that must be edited.",
            }
        ]
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))

    def test_continuous_field_preserve_requires_user_directive(self) -> None:
        manifest = base_manifest()
        manifest["route_decision"]["background_scopes"] = [
            {
                "id": "photo-field",
                "source_region": {"x": 500, "y": 0, "w": 500, "h": 600},
                "region_accuracy": "estimated-from-global-read",
                "field_type": "continuous-field",
                "strategy": "source-preserve-region",
                "reason": "Editable labels overlap a continuous photo field.",
            }
        ]
        self.assertFalse(_validate_route_decision(manifest, 1000, 600))
        manifest["route_decision"]["background_scopes"][0]["user_directive"] = (
            "Keep the whole photo region rasterized; I accept that its old labels remain uneditable."
        )
        self.assertTrue(_validate_route_decision(manifest, 1000, 600))


if __name__ == "__main__":
    unittest.main()
