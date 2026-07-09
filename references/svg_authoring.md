# SVG Authoring Conventions

## Canvas

Use source image dimensions as the SVG coordinate system unless rescaling is requested.

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="W" height="H" viewBox="0 0 W H">
```

## File Organization

Recommended group order:

```xml
<g id="background">...</g>
<g id="panels">...</g>
<g id="sections">...</g>
<g id="assets">...</g>
<g id="icons">...</g>
<g id="connectors">...</g>
<g id="texts">...</g>
<g id="annotations">...</g>
```

When `background_plan.plate_asset_id` or `plate_file` is present, the generator
places a full-canvas `<image id="background-plate">` in the background group
with `preserveAspectRatio="none"`. The plate dimensions must already match the
canvas; the attribute prevents accidental letterboxing, not geometry repair.

## PPTX Grouping

Author SVG groups for layer order and maintainability, but do not rely on
ordinary groups staying grouped in PowerPoint. Native PPTX export defaults to
semantic ungrouping: non-semantic layout groups such as `background`, `assets`,
`panels`, `connectors`, and `texts` are flattened after their transforms and
styles are applied, so the final PowerPoint file is directly selectable without
manual ungrouping.

Keep a group atomic only when ungrouping would hurt visual fidelity or
editability. Use one of these explicit markers:

```xml
<g id="logo-mark" data-pptx-group="atomic">...</g>
<g id="equation-main" class="formula" data-latex="...">...</g>
<g id="masked-photo" data-pptx-group="preserve" clip-path="url(#clip)">...</g>
```

The exporter also preserves groups with formulas, group-level clip paths,
masks, filters, opacity, or rotations that require a group wrapper. Avoid
wrapping an entire figure, panel, or asset layer as an atomic group unless the
user explicitly asked for that object to move as one piece.

## Naming

Use stable semantic IDs:

- `panel-data-source`
- `section-evaluation-metrics`
- `arrow-collection-to-processing`
- `label-stage-1`
- `asset-route-map`

Avoid generic names such as `rect1`, `image2`, or `path-final`.

## Text

- Keep text editable with `<text>` and `<tspan>`.
- Use manual line breaks for multi-line labels.
- Use `text-anchor` and `dominant-baseline` for alignment.
- Mark uncertain text in the manifest.
- For dense figures, preserve the source slot and baseline rather than relying on default browser or PowerPoint text metrics.

Recommended font stacks:

```css
--font-sans: "Inter", "Arial", "Helvetica", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
--font-serif: "Georgia", "Times New Roman", "Noto Serif CJK SC", serif;
--font-hand: "Comic Sans MS", "Comic Neue", "Arial Rounded MT Bold", "Microsoft YaHei", sans-serif;
```

Do not convert normal text to outlines unless explicitly requested.

## Math

Use manifest `math` elements for formulas instead of approximating them as
plain text. The generator renders `latex` to vector paths and keeps the source
formula in `data-latex`. The PPTX exporter uses the same `latex` value to
create editable Office Math equations, so malformed or approximate LaTeX should
be treated as a reconstruction defect.

```json
{
  "type": "math",
  "id": "formula-return-normalization",
  "latex": "\\frac{R_n-\\mathrm{median}(R_u)}{\\mathrm{MAD}(R_u)+\\epsilon}",
  "x": 1200,
  "y": 520,
  "w": 260,
  "h": 70,
  "font_size": 24,
  "fill": "#111111"
}
```

Use `math` for fractions, summations, products, integrals, Greek symbols,
scripts, hats/bars, matrix notation, and recurrence formulas. Use ordinary
`text` for prose labels, file names, code snippets, and captions.

Do not use `text` for formulas merely because the source formula is short.
Examples such as `A_i^{tree}`, `\delta_i`, `R^{(m)}`, and
`\sum_{\ell=1}^{G}` still belong in `math` when they function as equations or
mathematical annotations.

Do not rasterize formulas to avoid placement difficulty. If a formula is dense
or small, keep it editable and control its layout with a measured source slot,
explicit width/height, anchor, baseline, and font size.

For mixed prose/formula labels, split the visual line into adjacent elements
that share a baseline. Do not leave TeX syntax, Unicode subscript/superscript,
or compact Greek-variable notation inside `type: "text"`.

```json
[
  {
    "type": "text",
    "id": "label-scope-prefix",
    "text": "episode-level scope",
    "x": 614,
    "y": 480,
    "font_size": 35
  },
  {
    "type": "math",
    "id": "label-scope-formula",
    "latex": "A^{\\mathrm{ep}}",
    "x": 920,
    "y": 480,
    "w": 90,
    "h": 42,
    "font_size": 35,
    "dominant_baseline": "middle"
  }
]
```

If a symbol-like text is intentionally not a formula, add
`formula_policy: "not-formula"` and a short `formula_decision_reason`.

Native PPTX export uses PowerPoint text and Office Math layout, which can differ
from SVG. On tight layouts, verify the exported PPTX visually and adjust the
manifest if equations or labels shift, wrap, overflow, or collide.

## Shapes

Use:

- `rect` for panels, cards, table cells, and background blocks
- `line` or `polyline` for straight connectors
- `path` for curved connectors
- `marker` for arrowheads
- `circle` and `ellipse` for nodes
- `polygon` for simple geometric icons

## Style

Define reusable classes inside `<style>`:

```xml
<style>
  .panel { fill: #fff; stroke: #333; stroke-width: 2; }
  .label { font-family: var(--font-sans); font-size: 18px; fill: #111; }
  .connector { fill: none; stroke: #333; stroke-width: 2; }
</style>
```

## Assets

Use relative paths in `editable.svg`:

```xml
<image href="assets/example.png" x="100" y="120" width="240" height="160" preserveAspectRatio="xMidYMid meet"/>
```

Use base64 data URIs in `editable_embedded.svg`.

For a background plate, prefer the top-level `background_plan` reference rather
than adding a duplicate image element. For coordinate-sensitive foreground
assets, keep normal aspect-ratio preservation and verify placement against the
source overlay.

## Accessibility and Maintainability

Where practical:

- add `<title>` to major groups
- use semantic IDs
- keep source order close to reading order
- keep complex paths readable or documented
