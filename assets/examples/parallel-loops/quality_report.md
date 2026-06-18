# Reconstruction Quality Report

## Summary

- Project: parallel-loops-editable-reconstruction
- Source image: `source.png`
- Canvas: 1720 x 818
- OCR status: missing (0 text candidates)
- OpenCV status: missing ({})
- Assets: 0
- Elements: 433
- SVG text elements: 82
- SVG math elements: 7
- Formula-like text leaks: 0
- PPTX editable formula objects: 7/7
- Structural SVG elements: 344

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- pptx_export: `ok`
- pptx_math_export: `ok`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=None asset_text_risks=0

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
