# Reconstruction Quality Report

## Summary

- Project: tryon-pipeline-editable
- Source image: `source.png`
- Canvas: 2514 x 1268
- OCR status: ok (62 text candidates)
- OpenCV status: ok ({'lines': 1566, 'rectangles': 3, 'arrowheads': 0, 'dashed_groups': 63})
- Assets: 37
- Elements: 142
- SVG text elements: 52
- SVG math elements: 1
- Formula-like text leaks: 0
- PPTX editable formula objects: 1/1
- Structural SVG elements: 52

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- pptx_export: `ok`
- pptx_math_export: `ok`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=1.0 asset_text_risks=0

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
