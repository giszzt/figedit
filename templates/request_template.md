# Editable Graphics Reconstruction Request

Convert the provided raster figure into an editable graphics package: editable SVG plus a native PowerPoint `.pptx` with real text boxes and shapes.

## Reconstruction intent

Default intent: inspect the whole figure first, then choose a composite route by region and visual object.

Prioritize:

1. information completeness
2. original visual asset fidelity
3. editable structure and text
4. accurate layout and connector relationships
5. maintainable SVG organization

## Asset preservation requirement

Do not replace source-specific visual assets with newly invented SVG drawings
when their exact appearance, evidence value, texture, or source style matters.
Examples include icons, pictograms, illustrations, screenshots, maps,
thumbnails, logos, UI fragments, scientific symbols, chart/map bodies, and
custom shapes, but the rule is not limited to these examples.

Only redraw elements that are clearly structural or generic primitives, such as panels, cards, frames, separators, arrows, table lines, simple plus/check/cross markers, and plain geometric shapes.

For each visual asset, decide by identity, separability, and editing value:

- redraw generic structural primitives
- crop source-specific assets only when their source window is clean or clean-on-fill
- regenerate source-specific assets that are visibly overlapped or contaminated when they must remain independent
- flatten objects into an AI-cleaned regional background when they do not need independent movement
- document the route group and decision reason in the manifest
- verify crop or regeneration batches with one contact sheet; inspect only exceptions individually

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

If a local or full-canvas continuous visual field contains foreground content that must be editable, use a regional AI clean plate. When the user's requested foreground depth is unclear, stop before OCR, cropping, generation, or composition and ask whether the region should be flattened, selectively extracted, or fully extracted.
