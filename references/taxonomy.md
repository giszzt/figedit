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
- `mixed-style`

### Reconstruction Intent

- `exact-layout`: preserve layout closely
- `editable-layout`: prioritize editability with close visual similarity
- `semantic-redraw`: preserve meaning and relationships, allow visual cleanup
- `redesign`: keep content, improve visual system

## Reconstruction Modes

Every mode produces the same package: editable SVG (`editable.svg`, `editable_embedded.svg`) plus a native PowerPoint `editable.pptx`. The mode only changes the balance between redrawn vector structure and preserved raster assets, not the set of output formats. The "Typical outputs" notes below describe that balance, not the file list.

### Mode A: Structure-First Full Vector

Use when:

- most elements are text, lines, shapes, arrows, and simple icons
- figure is clean and structured
- user needs high editability

Typical outputs:

- fully editable SVG
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

Typical outputs:

- editable SVG with external assets
- embedded SVG for sharing
- assets directory and contact sheet

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

Examples:

- benchmark overview figures
- model/data/evaluation composite figures
- multi-section paper figures

### Mode D: Semantic Redraw

Use when:

- figure is hand-drawn or heavily stylized
- original edges are irregular
- exact pixel matching is less important than clear editable meaning
- source image is low-resolution or compressed

Typical outputs:

- clean editable SVG
- approximate style preservation
- simplified shapes and icons

Examples:

- illustrated workflows
- sketch-like process explanations
- informal architecture cartoons

## Mode Selection Rules

- Use Mode A when the figure is mostly structure and contains few source-specific pictorial assets.
- Use Mode B by default when the figure combines editable structure with any source-specific visual assets.
- Use Mode C when the figure has multiple major panels. Combine with Mode B if panels contain custom icons, pictograms, screenshots, maps, photos, or thumbnails.
- Use Mode D only when semantic clarity and style approximation are more important than exact source visual fidelity.
- If a figure has many pictorial icons that look custom or source-specific, do not treat them as simple icons; select Mode B or Mode C + B.
- Combine modes when necessary; for example, Mode C + B for a multi-panel benchmark figure with embedded maps and custom icons.
