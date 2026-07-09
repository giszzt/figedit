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

## Transparent Extraction

A standalone transparent PNG is produced by chroma regeneration
(`chroma_regeneration.md`): the object is reproduced on a flat chroma sheet
and keyed apart. This is the method on the `ai-clean-plate` route and handles
composite, entangled, and plain pictorial objects alike. There is no
salient-object matting step — the sheet background is a known flat color, so
keying is exact and a rembg/U2-Net guess would only add failure modes.

On the conventional route, an object that needs to be a raster asset is
coordinate-cropped as a rectangle (`crop_assets.py`); assets on flat, white,
or otherwise separable backgrounds need no alpha at all. Do not hand-roll
GrabCut, color-difference, threshold, or rembg matting scripts to cut an
object out of a natural background.

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
   - small icons: 3-8 px
   - medium icons and thumbnails: 6-12 px
   - large screenshots/maps: 0-16 px depending on visual boundary
   - assets with shadow or blur: include the full shadow/blur region
   - **flush-mounted assets** (tiles, thumbnails, or panels seated directly
     inside another element's border, e.g. icon squares inside a colored
     card): use a **negative pad** (`"pad": -2` to `-4`) to inset the crop
     inside the tile's own boundary. Eyeballed boxes routinely catch a few
     pixels of the neighboring border; insetting is cheaper and more reliable
     than trying to hit the exact edge. Matting does not work here — a flat
     dark tile is not a salient object.
4. Avoid clipping strokes, shadows, texture, and edge pixels. On the contact
   sheet, check the opposite failure too: thin slivers of neighboring borders
   or card fills along any crop edge mean the box needs an inset or shift.
5. Preserve original aspect ratio unless the target SVG intentionally masks or crops the asset.
6. If an object sits on a colored card, include enough surrounding pixels to avoid edge artifacts or remove the background only when reliable.
7. If an annotation crosses the asset, mark the crop as contaminated and do
   not finalize it before applying a recovery strategy.

## Precision Requirements

For each crop, verify:

- the whole object is visible
- no important edge is cut off
- no unrelated neighboring object is included
- the crop can be placed back at the target size without visible distortion
- text that should remain editable is not unnecessarily baked into the crop

The current helper scripts do not perform perfect object segmentation. They
crop rectangular `source_region` boxes supplied by the manifest, or use OpenCV
color/edge density to propose rectangular candidates. `edge_check` is a warning
system: it reports whether the cropped rectangle still has strong visual signal
on the top, bottom, left, or right edge. It does not prove that the box is
semantically exact, and it cannot reliably detect unrelated neighboring objects
inside the crop.

For high-value assets, use a three-pass crop:

1. Set a coarse `source_region` from the source image at high zoom.
2. Run composition and inspect `contact_sheet.png`,
   `diagnostics/placement_overlay.png`, and `edge_check.needs_padding_sides`.
3. Adjust the individual `source_region` edges and `pad`, then rerun until the
   object is complete and neighboring labels, arrows, or icons are excluded.

Do not accept `crop_status: verified` solely because the automated edge check
is green. The final authority is visual comparison against the source and the
source-overlay crop rectangle.

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

External restored or generated assets should use `source_mode: external`. The
compose step copies them into the output assets directory instead of cropping
the source again.

## Common Failure Modes

Avoid these failures:

- redrawing a source-specific pictogram as a generic icon
- cropping too tightly and cutting the object edge
- including labels inside icon crops when labels should be editable
- missing repeated icons because they looked simple
- replacing a hand-drawn or paper-textured object with a flat SVG substitute
- using one generic icon to replace multiple distinct source icons
- calling a contaminated crop complete because the bounding box is accurate
- erasing thin structures during alpha extraction
- leaving source-colored halos around restored or generated assets
