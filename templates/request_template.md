# Editable Graphics Reconstruction Request

Convert the provided raster figure into an editable graphics package: editable SVG plus a native PowerPoint `.pptx` with real text boxes and shapes.

## Reconstruction intent

Default intent: asset-preserving hybrid reconstruction.

Prioritize:

1. information completeness
2. original visual asset fidelity
3. editable structure and text
4. accurate layout and connector relationships
5. maintainable SVG organization

## Asset preservation requirement

Do not replace source-specific icons, pictograms, illustrations, screenshots, maps, thumbnails, logos, or custom shapes with newly invented SVG drawings.

Only redraw elements that are clearly structural or generic primitives, such as panels, cards, frames, separators, arrows, table lines, simple plus/check/cross markers, and plain geometric shapes.

For each visual asset:

- crop it from the source image
- preserve adequate padding
- retype nearby labels separately when possible
- document crop coordinates and decision reason in the manifest
- generate a contact sheet for verification

## Deliverables

Create a package containing:

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `README.md`
- `assets/`

## Notes

If a visual object cannot be cleanly cropped, document the limitation and use the closest maintainable alternative.
