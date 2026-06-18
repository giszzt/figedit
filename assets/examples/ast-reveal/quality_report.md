# Reconstruction Quality Report

## Summary

- Project: ast_reveal_editable
- Source image: `source.jpg`
- Canvas: 2048 x 1149
- OCR status: ok (146 text candidates)
- OpenCV status: ok ({'lines': 467, 'rectangles': 28, 'arrowheads': 6, 'dashed_groups': 29})
- Assets: 0
- Elements: 390
- SVG text elements: 106
- SVG math elements: 50
- Formula-like text leaks: 0
- PPTX editable formula objects: 50/50
- Structural SVG elements: 234

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- pptx_export: `ok`
- pptx_math_export: `ok`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=0.7377 asset_text_risks=0

## Items Needing Review

- No high-priority review items detected by automated checks.

## Diagnostics

- `diagnostics/ocr_overlay.png`
- `diagnostics/structure_overlay.png`
- `diagnostics/crop_overlay.png`
- `diagnostics/style_overlay.png`
- `diagnostics/rejected_candidates.png`
- `editability_report.md`

## Notes

- Dense maps, heatmaps, screenshots, and charts remain source-preserved raster assets unless explicitly vectorized.
- Low-confidence OCR text should be checked against the source image before publication use.
