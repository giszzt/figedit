# Reconstruction Workflow

## 1. Intake and Intent

Determine the user's intent before reconstruction:

- pixel-faithful reconstruction
- editable structural reconstruction
- asset-preserving hybrid reconstruction
- semantic redraw
- publication cleanup or redesign

If the user does not specify, default to asset-preserving hybrid reconstruction.

## 2. Classify the Figure

Record:

- layout topology
- content complexity
- style type
- reconstruction mode
- expected asset fidelity level

Use `taxonomy.md`.

## 3. Build Layer Inventory

Create three inventories before authoring SVG.

### Structure inventory

Include:

- panels
- cards
- frames
- table/grid structures
- separators
- background blocks
- connectors and arrows

Default decision: `redraw`.

### Text and formula inventory

Include:

- titles
- section headers
- labels
- annotations
- legends
- captions
- mathematical formulas and equations

Default decision: ordinary prose labels use `retype`; mathematical formulas and
math-bearing text spans use `retype-math` with normalized LaTeX in a `math`
element. A `math` element is the only route that can become an editable
PowerPoint equation.

Treat formulas as spans, not only as whole OCR boxes. A title, caption, legend,
axis label, callout, or node label can contain both prose and inline math. In
that case, split the region into adjacent elements: prose stays `text`, and the
formula span becomes `math`.

### Asset inventory

Include:

- icons
- pictograms
- illustrations
- logos
- maps
- screenshots
- thumbnails
- photos
- hand-drawn visual objects
- model outputs

Default decision: `crop` unless the object passes the redraw eligibility test in `asset_preservation_policy.md`.

## 4. Decide Element Strategy

Apply this order:

1. Does it contain a mathematical formula or formula-like span? Retype that
   span as LaTeX and render it as a `math` element.
2. Does the remaining region contain ordinary text? Retype it as `text`.
3. Is it structural scaffolding? Redraw.
4. Is it a pictorial or source-specific visual object? Crop.
5. Is it a generic primitive? Redraw.
6. Is it uncertain? Crop.

Record the decision and reason in the manifest.

## 5. Establish Coordinate System

Use original image dimensions as:

- SVG `width`
- SVG `height`
- SVG `viewBox`

Use pixel coordinates for all manifest entries.

## 6. Extract Assets First

Before drawing replacement icons, extract all visual assets that should be preserved.

For each asset:

- create a source bounding box
- add padding
- crop to `assets/`
- record target placement
- generate contact sheet
- verify it is not clipped or missing

Do not redraw source-specific icons before trying to crop them.

## 7. Rebuild Structural SVG

Draw:

- canvas background
- panel outlines
- cards and content blocks
- separators
- arrows and connectors
- table/grid lines
- simple structural symbols

Use semantic groups and IDs.

## 8. Retype Text

Retype text as SVG text.

- Preserve visual hierarchy.
- Use readable fallback fonts.
- Manually split long lines.
- Mark uncertain text in the manifest.

For formulas, do not approximate with plain text. Use `type: "math"` and a
normalized `latex` string. The compose step renders the formula as vector paths
and stores the source LaTeX in `data-latex`.

Use math detection cues before finalizing any `type: "text"` element:

- TeX-like syntax: `\frac`, `\sum`, `\sqrt`, `\hat`, `\bar`, `A^{ep}`, `R_u`.
- Unicode math typography: superscripts/subscripts, Greek variables, arrows,
  relation symbols, radicals, large operators, and set operators.
- Equation structure: `=`, `<`, `>`, `<=`, `>=`, fractions, recurrences,
  indexed variables, function calls with variable subscripts, and normalization
  terms.

If a text element intentionally contains a symbolic method name or literal code
that should not become math, set `formula_policy: "not-formula"` and record a
short `formula_decision_reason`. Do not use that escape hatch for actual
equations, variables, or inline formula annotations.

For PPTX output, the compose step converts the same LaTeX to MathML and then to
Office Math (OMML), removes the converted SVG formula paths from the PPTX
staging SVG, and injects editable equation objects. If a formula cannot be
converted, it remains visible as vector artwork and is listed in
`editable.pptx.math_report.json`; fix the LaTeX and rerun if editability is
required.

## 9. Place Assets

Place cropped assets using `<image>` elements.

- Preserve aspect ratio.
- Use masks or clipping only when necessary.
- Do not stretch assets unless the source itself is stretched.
- Align assets to the recreated structure.

## 10. Generate Deliverables

Create:

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `quality_report.md`
- `README.md`
- `assets/`

The `editable.pptx` is a native PowerPoint export of the same reconstruction,
written with positioned text boxes and shapes rather than an imported SVG. It is
produced for every figure, regardless of reconstruction mode. Formula elements
should appear as editable Office Math objects when `pptx_math_export` is `ok`.

## 11. Validate and Repair

Use `quality_checklist.md`.

Repair order:

1. missing information
2. wrong structure or arrow direction
3. missing or wrongly redrawn visual assets
4. clipped or misplaced crops
5. text overflow
6. visual polish
