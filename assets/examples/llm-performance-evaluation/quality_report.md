# Reconstruction Quality Report

## Summary

- Project: llm-performance-evaluation
- Source image: `source.webp`
- Canvas: 4239 x 2799
- OCR status: missing (0 text candidates)
- OpenCV status: missing ({})
- Assets: 6
- Elements: 200
- SVG text elements: 66
- SVG math elements: 0
- Formula-like text leaks: 0
- PPTX editable formula objects: 0/0
- Structural SVG elements: 93

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `review`
- pptx_export: `ok`
- pptx_math_export: `skipped`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=None asset_text_risks=0

## Items Needing Review

- Asset `asset-logo-glm_blue` crop review: {'status': 'needs-padding', 'edge_density': 1.0} status=needs-padding
- Asset `asset-logo-glm_green` crop review: {'status': 'needs-padding', 'edge_density': 1.0} status=needs-padding
- Asset `asset-logo-gemini` crop review: {'status': 'needs-padding', 'edge_density': 0.9334} status=needs-padding
- Gate `crop_edge_checks` needs review: {'status': 'review', 'count': 3}

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
