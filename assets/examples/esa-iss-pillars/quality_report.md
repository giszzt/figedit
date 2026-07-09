# Reconstruction Quality Report

## Summary

- Project: esa-iss-pillars-full-extract
- Source image: assets\source.png
- Canvas: 1920 x 1400
- OCR status: ok (121 text candidates)
- OpenCV status: failed ({})
- Background strategy: ai-clean-plate
- Assets: 38
- Elements: 177
- SVG text elements: 105
- SVG math elements: 0
- Formula-like text leaks: 0
- PPTX editable formula objects: 0/0
- Structural SVG elements: 35

## Quality Gates

- xml_editable: `ok`
- xml_embedded: `ok`
- preview_render: `ok`
- low_confidence_elements: `ok`
- crop_edge_checks: `ok`
- background_route_consistency: `ok`
- background_plate: `ok`
- ai_patchwork_source_crops: `ok`
- opencv_detector_noise: `ok`
- ocr_fallback_text: `ok`
- text_math_layout_fidelity: `review`
- visual_qa: `ok`
- pptx_export: `ok`
- pptx_math_export: `skipped`
- formula_text_leakage: `ok`
- editability: `ok` text_lift_ratio=0.9587 asset_text_risks=5

## Items Needing Review

- Gate `text_math_layout_fidelity` needs review: dense editable text/math layout requires PPTX visual review
- Gate `text_math_layout_fidelity` sample: `mission-top_guidoni`
- Gate `text_math_layout_fidelity` sample: `date-top_guidoni`
- Gate `text_math_layout_fidelity` sample: `mission-top_haignere`
- Gate `text_math_layout_fidelity` sample: `date-top_haignere`
- Gate `text_math_layout_fidelity` sample: `mission-top_vittori`
- Gate `text_math_layout_fidelity` sample: `date-top_vittori`
- Gate `text_math_layout_fidelity` sample: `mission-top_perrin`
- Gate `text_math_layout_fidelity` sample: `date-top_perrin`
- Gate `text_math_layout_fidelity` sample: `mission-top_dewinne`
- Gate `text_math_layout_fidelity` sample: `date-top_dewinne`
- Gate `text_math_layout_fidelity` sample: `mission-r2_dewinne`
- Gate `text_math_layout_fidelity` sample: `date-r2_dewinne`
- Gate `text_math_layout_fidelity` sample: `mission-r2_eyharts`
- Gate `text_math_layout_fidelity` sample: `date-r2_eyharts`
- Gate `text_math_layout_fidelity` sample: `mission-r2_schlegel`
- Gate `text_math_layout_fidelity` sample: `date-r2_schlegel`
- Gate `text_math_layout_fidelity` sample: `mission-r2_nespoli`
- Gate `text_math_layout_fidelity` sample: `date-r2_nespoli`
- Gate `text_math_layout_fidelity` sample: `mission-r2_fuglesang`
- Gate `text_math_layout_fidelity` sample: `date-r2_fuglesang`

## Diagnostics

- `diagnostics/ocr_overlay.png`
- `diagnostics/structure_overlay.png`
- `diagnostics/placement_overlay.png`
- `diagnostics/style_overlay.png`
- `editability_report.md`

## Notes

- Dense maps, heatmaps, screenshots, and charts remain source-preserved raster assets unless explicitly vectorized.
- AI clean plate is a background repair route, not a foreground patchwork route.
- Source-specific assets should be cropped only when identity matters and the crop is clean.
- Low-confidence OCR text should be checked against the source image before publication use.
