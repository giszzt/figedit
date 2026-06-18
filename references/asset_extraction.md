# Asset Extraction Rules

## Purpose

Asset extraction preserves source-specific visual content in raster figures. Use it for pictorial objects that should look like the source, not like a newly invented SVG substitute.

## Assets to Extract

Extract as assets when content is:

- photographic
- screenshot-based
- map or remote-sensing imagery
- dense thumbnail grids
- complex icon groups
- custom pictograms or source-specific icons
- detailed illustrations that are not central to editability
- hand-drawn characters or props when style fidelity matters
- logos or model marks where visual fidelity matters
- product, clothing, person, object, terrain, city, drone, camera, database, document, folder, route, or avatar imagery

## Cropping Scope

Prefer cropping only the pictorial asset, not the whole surrounding tile, when surrounding components should remain editable.

Typical split:

- rounded tile/background: redraw
- label: retype
- icon/thumbnail/screenshot: crop
- arrow/connector: redraw

## Cropping Rules

1. Use source image coordinates.
2. Prefer `source_region` in the manifest.
3. Add padding:
   - small icons: 3–8 px
   - medium icons and thumbnails: 6–12 px
   - large screenshots/maps: 0–16 px depending on visual boundary
   - assets with shadow or blur: include the full shadow/blur region
4. Avoid clipping strokes, shadows, texture, and edge pixels.
5. Preserve original aspect ratio unless the target SVG intentionally masks or crops the asset.
6. If an object sits on a colored card, include enough surrounding pixels to avoid edge artifacts or remove the background only when reliable.

## Precision Requirements

For each crop, verify:

- the whole object is visible
- no important edge is cut off
- no unrelated neighboring object is included
- the crop can be placed back at the target size without visible distortion
- text that should remain editable is not unnecessarily baked into the crop

## Contact Sheet

Generate a contact sheet after cropping. The sheet should show:

- asset ID
- filename
- source bounding box
- cropped preview
- optional status: `ok`, `needs-padding`, `wrong-region`, `background-issue`

Use it to catch:

- clipped assets
- wrong region
- missing edge pixels
- accidental duplicate crops
- crops with excessive surrounding background
- visual assets that were not extracted but should have been

## Background Handling

If an asset has a non-transparent background:

- preserve it if it is part of the original visual design
- remove it only if background removal is reliable
- otherwise crop with safe padding and align it onto the recreated panel
- document uncertain background handling in the manifest

## Replacement Readiness

Every asset should be replaceable by editing:

- its file in `assets/`
- its `<image>` dimensions and position
- its manifest entry

## Common Failure Modes

Avoid these failures:

- redrawing a source-specific pictogram as a generic icon
- cropping too tightly and cutting the object edge
- including labels inside icon crops when labels should be editable
- missing repeated icons because they looked simple
- replacing a hand-drawn or paper-textured object with a flat SVG substitute
- using one generic icon to replace multiple distinct source icons
