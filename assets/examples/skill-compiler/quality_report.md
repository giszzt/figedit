# Reconstruction Quality Report

## Summary

- Project: pipeline_skill_compiler_editable
- Source image: `source.png`
- Canvas: 2580 x 959
- OCR status: ok (89 text candidates)
- OpenCV status: ok ({'lines': 475, 'rectangles': 4, 'arrowheads': 0, 'dashed_groups': 34})
- Assets: 12
- Elements: 190
- SVG text elements: 48
- SVG math elements: 34
- Formula-like text leaks: 0
- PPTX editable formula objects: 34/34
- Structural SVG elements: 96

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- pptx_export: `ok`
- pptx_math_export: `ok`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=0.7344 asset_text_risks=0

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
