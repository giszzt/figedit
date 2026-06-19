# Reconstruction Quality Report

## Summary

- Project: transitlm-framework-figure
- Source image: `source.png`
- Canvas: 3455 x 1614
- OCR status: missing (0 text candidates)
- OpenCV status: missing ({})
- Assets: 15
- Elements: 233
- SVG text elements: 114
- Structural SVG elements: 104

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `review`
- pptx_export: `ok`
- editability: `ok` text_lift_ratio=None asset_text_risks=0

## Items Needing Review

- Asset `asset-phone` crop review: {'status': 'needs-padding', 'edge_density': 0.2947} status=needs-padding
- Asset `asset-qwen-logo` crop review: {'status': 'needs-padding', 'edge_density': 0.9816} status=needs-padding
- Asset `asset-person-icon` crop review: {'status': 'needs-padding', 'edge_density': 1.0} status=needs-padding
- Asset `asset-robot-icon` crop review: {'status': 'needs-padding', 'edge_density': 0.9922} status=needs-padding
- Gate `crop_edge_checks` needs review: {'status': 'review', 'count': 4}

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
