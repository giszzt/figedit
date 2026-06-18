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

## Accessibility and Maintainability

Where practical:

- add `<title>` to major groups
- use semantic IDs
- keep source order close to reading order
- keep complex paths readable or documented
