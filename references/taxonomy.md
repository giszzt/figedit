# Figure Taxonomy and Reconstruction Modes

## Classification Dimensions

### Layout Topology

Use the closest category:

- `linear-flow`: ordered sequence, usually left-to-right or top-to-bottom
- `multi-column`: parallel columns or stages
- `card-grid`: modular grid of cards or boxes
- `panel-composite`: several large panels with internal substructures
- `radial-network`: central node with surrounding relationships
- `hierarchical-tree`: parent-child or branching structure
- `ui-screen`: interface, dashboard, or software mockup
- `hand-drawn-explainer`: sketch-like explanatory figure
- `image-heavy-composite`: poster, cover, social card, or visual scene with overlays
- `mixed-complex`: multiple topology types combined

### Element Complexity

- `low`: text, boxes, arrows, simple icons
- `medium`: text, boxes, arrows, icons, simple charts, small diagrams
- `high`: screenshots, maps, photos, dense thumbnails, complex icons, multiple nested panels

### Style Type

- `academic-grayscale`
- `academic-color`
- `benchmark-color`
- `flat-infographic`
- `hand-drawn`
- `ui-schematic`
- `technical-blueprint`
- `continuous-visual-field`
- `mixed-style`

### Reconstruction Intent

- `exact-layout`: preserve layout closely
- `editable-layout`: prioritize editability with close visual similarity
- `asset-preserving-hybrid`: preserve source-specific assets while lifting text/structure
- `clean-plate-plus-editable-overlay`: use AI only to repair an unrecoverable continuous background
- `semantic-redraw`: preserve meaning and relationships, allow visual cleanup
- `redesign`: keep content, improve visual system

## Reconstruction Modes

Every mode produces the same package: editable SVG (`editable.svg`, `editable_embedded.svg`) plus a native PowerPoint `editable.pptx`. The mode only changes the balance between redrawn vector structure and preserved raster assets.

### Mode A: Structure-First Full Vector

Use when:

- most elements are text, lines, shapes, arrows, and simple icons
- figure is clean and structured
- user needs high editability

Typical balance:

- mostly editable SVG
- no or minimal raster assets

Examples:

- academic workflow diagrams
- black-and-white process figures
- technical method diagrams
- architecture line diagrams

### Mode B: Asset-Preserving Hybrid Reconstruction

Use when:

- figure includes complex visual content
- structure and text should remain editable
- original icons, pictograms, illustrations, photos, screenshots, maps, thumbnails, or logos should remain visually faithful
- replacing source-specific objects with generic vector drawings would reduce fidelity

Typical balance:

- editable SVG structure/text
- source-preserved raster assets
- contact sheet for crop review

Examples:

- image-heavy infographics
- diagrams containing maps or screenshots
- dataset figures with example images
- figures with custom pictorial icons or hand-crafted visual marks

### Mode C: Panel-Wise Reconstruction

Use when:

- figure contains multiple large panels
- each panel has a distinct internal layout
- direct full-canvas reconstruction would be difficult to manage

Procedure:

1. Identify outer panel boundaries.
2. Reconstruct each panel as a separate group.
3. Reassemble panels in the global SVG.
4. Normalize typography, stroke widths, and spacing.

Combine with Mode B when panels contain custom icons, pictograms, screenshots, maps, photos, or thumbnails.

### Mode D: Semantic Redraw

Use when:

- figure is hand-drawn or heavily stylized
- original edges are irregular
- exact pixel matching is less important than clear editable meaning
- source image is low-resolution or compressed

Typical balance:

- clean editable SVG
- approximate style preservation
- simplified shapes and icons

Do not use Mode D for source-specific logos, screenshots, maps, evidence images, or distinctive icons unless the user explicitly accepts approximation.

### Mode E: AI Clean-Plate Background Hybrid

Use when the Background Gate selects `ai-clean-plate` (authoritative criteria in `background_reconstruction.md`): a continuous visual field that is not mechanically recoverable from simple primitives or clean crops, with foreground marks hiding pixels in it.

Typical balance:

- one canvas-aligned AI-generated clean background plate
- editable text, formulas, connectors, and structural geometry
- extracted foreground assets per `background_plan.foreground_mode`: chroma-regenerated transparent objects, keyed apart from a generated sheet (full-extract/selective), or none (flatten)
- provenance and candidate review for the accepted plate and regenerated assets

Mode E uses `E-ai`. Select it when the Background Gate reaches the `ai-clean-plate` category. Do not wait until after a failed SVG attempt when the source already shows strong AI-route signals. Do not create a local mask-repaired source plate as a Mode E variant.

## Mode Selection Rules

- Use Mode A when the figure is mostly structure and contains few source-specific pictorial assets.
- Use Mode B by default when the figure combines editable structure with any source-specific visual assets.
- Use Mode C when the figure has multiple major panels. Combine with Mode B if panels contain custom icons, pictograms, screenshots, maps, photos, or thumbnails.
- Use Mode D only when semantic clarity and style approximation are more important than exact source visual fidelity.
- Use Mode E when the Background Gate in `background_reconstruction.md` selects `ai-clean-plate`; do not select it by density, genre, or visual appeal.
- If a figure has many pictorial icons that look custom or source-specific, do not treat them as simple icons; use Mode B or C+B unless the background itself needs Mode E.
- Combine E with B only for the few foreground assets that genuinely need clean, independent source-preserved crops.
- Combine modes when necessary, but keep the route explanation short and tied to visual evidence.
