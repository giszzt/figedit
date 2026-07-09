# Reconstruction Quality Report

## Summary

- Project: sciscover-cover-background-aware
- Source image: assets\source.jpg
- Canvas: 1240 x 1654
- OCR status: ok (47 text candidates)
- OpenCV status: ok ({'lines': 1231, 'rectangles': 50, 'arrowheads': 13, 'dashed_groups': 33})
- Recognition summary: OCR=ok primitives=ok assets=reviewed
- Asset decision policy: route=E-ai+B asset-preserving hybrid crop_preserve=3 redraw_allowed=3
- Assets: 4
- Background strategy: ai-clean-plate
- Flattened groups: 4
- Generated assets or plates: 2
- Editability targets: {'min_editable_text': 12, 'min_editable_structure': 3, 'min_movable_assets': 4, 'rationale': 'Enable editing of main title, masthead, issue metadata, sponsor text, footer structure, and source-preserved brand/logo blocks.'}
- Elements: 19
- SVG text elements: 13
- SVG math elements: 0
- Formula-like text leaks: 0
- PPTX editable formula objects: 0/0
- Structural SVG elements: 3

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- background_plate: `ok`
- background_plate_difference: `ok`
- recognition_summary: `ok`
- asset_decision_policy: `ok`
- route_decision: `ok`
- text_layer_policy: `ok`
- foreground_asset_policy: `ok`
- editability_targets: `ok`
- generation_provenance: `ok`
- generated_content_review: `ok`
- pptx_export: `ok`
- pptx_math_export: `skipped`
- formula_text_leakage: `ok`
- editability: `review` text_lift_ratio=0.3 asset_text_risks=28

## Items Needing Review

- No high-priority review items detected by automated checks.

## Diagnostics

- `diagnostics/ocr_overlay.png`
- `diagnostics/structure_overlay.png`
- `diagnostics/crop_overlay.png`
- `diagnostics/background_mask.png` when a background plan is used
- `diagnostics/background_mask_overlay.png` when a background plan is used
- `diagnostics/style_overlay.png`
- `diagnostics/rejected_candidates.png`
- `editability_report.md`

## Notes

- Content category does not determine the route; use the method that achieves the highest-fidelity reconstruction.
- Generated backgrounds and assets are approximate unless the manifest explicitly proves a stricter fidelity class.
- Low-confidence OCR text should be checked against the source image before publication use.
