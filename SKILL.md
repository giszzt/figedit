---
name: figedit
description: Convert raster figures into editable graphics packages with semantic SVG and native PowerPoint output. Use when the user wants a screenshot, paper figure, workflow diagram, architecture diagram, infographic, UI schematic, chart/map composite, or other image-based figure rebuilt so its layout, labels, formulas, shapes, and preserved raster visuals can be edited, relabeled, rearranged, or restyled.
---

# FigEdit

Use this skill to rebuild a non-editable raster figure as a high-fidelity editable graphics package. A single compose step produces `editable.svg`, `editable_embedded.svg`, and a native `editable.pptx`, so the result can be re-laid-out and restyled in a vector editor or in PowerPoint.

The goal is not "vectorize everything" or "crop everything." Route each part of the source image to the representation that preserves both editability and fidelity:

- structural elements become editable SVG shapes
- readable labels become editable SVG text
- formulas become normalized `math` elements and editable PowerPoint equations
- source-specific raster visuals become cropped assets placed with `image` elements
- dense charts, maps, screenshots, thumbnails, and pictorial evidence are cropped unless the user explicitly needs them rebuilt

OpenCV and OCR evidence can guide measurements and validation, but they do not decide what enters the final SVG. Do not dump all OpenCV candidates into the final SVG.

## Working Location

Run every command from the user's project directory, not from the skill folder.
Create one task directory per figure in the user's workspace, and write all
intermediates and outputs there. Never write run artifacts back into the skill
directory. The examples below use `figure-task/work` for evidence and
`figure-task/out` for the final package.

## Default Workflow

### 1. Prepare Measurement Evidence

Run:

```powershell
python scripts\prepare_measurements.py input.jpg --out figure-task\work
```

This creates:

- `ocr_results.json`
- `detected_primitives.json`
- `style_tokens.json`
- `draft_manifest.json`
- `measurement_report.md`
- `diagnostics/ocr_overlay.png`
- `diagnostics/structure_overlay.png`
- `diagnostics/style_overlay.png`
- `assets/source.*`

Treat these files as evidence only.

OCR defaults to PaddleOCR's PP-OCRv6 medium profile when available. Use
`--ocr-profile v6_small` or `--ocr-profile v6_tiny` for faster draft evidence,
and `--ocr-profile v5_mobile` only as a compatibility fallback. The OCR JSON
records both the requested profile and the profile actually selected, because
older environments may fall back when PP-OCRv6 is unavailable.

### 2. Route The Figure

Inspect the source image and diagnostics before authoring the manifest. Classify the figure into one or more routes, then load the relevant references:

- **Simple text/shape diagram**: mostly labels, boxes, arrows, grids, and basic geometric marks. Usually redraw structure and retype text; raster assets may be unnecessary.
- **Workflow, architecture, method, or infographic composite**: mixed panels, text, formulas, connectors, icons, screenshots, logos, document/folder graphics, or pictorial marks. Decompose panel-by-panel and apply the element gates below.
- **Screenshot, UI, map, photo, chart, thumbnail, or dense visual body**: preserve the visual body as a raster asset unless the user explicitly asks for a data/editable rebuild; lift surrounding readable labels separately.
- **Formula-heavy figure**: route every equation and inline math span through `math` reconstruction.

Reference loading is route-based:

- Always use `references/manifest_spec.md`, `references/svg_authoring.md`, and `references/quality_checklist.md`.
- If the figure type is unfamiliar or mixed, read `references/taxonomy.md` and `references/workflow.md`.
- If any formula or inline math appears, read `references/formula-reconstruction.md`.
- If any pictorial, raster, screenshot, logo, map, chart body, thumbnail, avatar, hand-drawn object, model mark, document/folder graphic, or source-specific icon appears, read `references/element_decision_matrix.md`, `references/asset_preservation_policy.md`, and `references/asset_extraction.md`.

### 3. Apply Element Decision Gates

Author the manifest by deciding every significant element through these gates. These rules are peers; none is a universal first step.

#### Structure Gate

Redraw structural elements as editable SVG shapes:

- panels, cards, frames, section headers, dividers, rules, grids, table borders
- simple arrows, connectors, dashed boxes, brackets, axes, and plain geometric markers
- simple flat color backgrounds

Use OpenCV coordinates as measurement hints, not as automatic truth.

#### Text Gate

Retype readable labels, titles, captions, legends, axis labels, callouts, and ordinary annotations as SVG text. Use PaddleOCR only as candidate evidence; verify text against the source. Mark uncertain text in the manifest.

#### Formula Gate

Mathematical formulas are first-class semantic objects. Author equations, inequalities, fractions, sums, Greek symbols, scripts, recurrences, and inline math spans as `math` elements with normalized LaTeX, never as formula strings inside `type: "text"`.

For mixed prose/formula regions, split the prose into `text` and the formula span into a separate adjacent `math` element. This applies to titles, captions, legends, axis labels, callouts, and node labels.

Before finalizing, scan every `type: "text"` element for formula cues: TeX commands, scripts, Greek variables, operators, relation symbols, fractions, indexed variables, hats, bars, and recurrence notation. If a converted formula fails to become editable OMML, the exporter records it in `editable.pptx.math_report.json` and the `pptx_math_export` gate; repair the LaTeX and recompose rather than marking it done.

#### Raster Asset Gate

Crop source-specific raster visuals as assets. This includes pictorial icons, logos, application/model marks, screenshots, maps, chart bodies, thumbnails, photos, UI fragments, avatars, robots, hand-drawn props, document/folder graphics, and dense visual examples.

Do not replace source-specific visual objects with generic invented SVG. Redraw only when the object is a clearly generic primitive or the user explicitly requests editable vectorization. When uncertain, crop.

Before writing final `image` elements, create an asset inventory for all raster/source-specific visuals. Each asset should include `source_region`, target placement, `decision_reason`, `text_policy`, `background_handling`, and `crop_status`. Use the smallest visually meaningful crop: crop the icon, screenshot, chart body, or visual evidence, while keeping surrounding labels, frames, and arrows editable whenever possible.

Use `text_policy`:

- `extract-editable`: readable text around the asset is lifted into SVG text
- `preserve-raster`: tiny, logo-internal, screenshot-internal, or data-bound text remains inside the asset
- `allow-embedded-text`: some readable text intentionally remains rasterized, with a reason

Use `edge_policy: allow-border-touch` only for intentional panel crops where touching border pixels are expected.

#### Composite Split Rule

Do panel-by-panel semantic decomposition. Do not crop a whole panel merely because it is dense, and do not redraw a whole panel merely because the structure is regular. Split each panel by function:

- structural shell: redraw
- readable label: retype
- formula span: `math`
- flow relation: redraw connector
- source-specific visual evidence: crop asset
- tiny chart/map/screenshot-internal text: preserve inside raster unless the user needs it editable

Layer carefully:

- Put backgrounds and filled panel rectangles on `layer: background`.
- Put raster evidence on `layer: assets`.
- Put panel borders and box borders on `layer: panels` with `fill: none`.
- Put arrows/connectors on `layer: connectors`.
- Put labels and rendered formulas on `layer: texts`.

Do not draw a filled panel rectangle above an image asset; it will hide the asset in the preview.

### 4. Compose The SVG Package

Run:

```powershell
python scripts\compose_svg_package.py manifest.json --out figure-task\out
```

This creates:

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `manifest.json`
- `contact_sheet.png`
- `quality_report.md`
- `editability_report.md`
- `assets/`
- `diagnostics/crop_overlay.png`

The PPTX is a native DrawingML export produced by this skill's bundled
SVG-to-PPTX converter. Prefer this file when the user needs to edit the figure
in PowerPoint. Do not ask the user to import `editable.svg` into PowerPoint and
then use "Convert to Shape" as the primary workflow: PowerPoint's SVG parser
reinterprets SVG text baselines, `text-anchor`, `tspan dy`, line spacing, and
CJK font fallback, which can shift or overlap labels. The native PPTX path
writes positioned PPT text boxes and shapes directly, and writes formulas as
editable Office Math equation objects when conversion succeeds.

### 5. Validate And Repair

Inspect:

- `preview.png`
- `contact_sheet.png`
- `editable.pptx` when PowerPoint editability is requested
- `quality_report.md`
- `diagnostics/crop_overlay.png`

Repair before delivery if:

- a major panel or flow relation is missing
- a cropped visual asset is clipped
- OpenCV candidate noise appears in the final SVG
- a source-specific icon, logo, pictorial mark, avatar, hand-drawn object, screenshot, thumbnail, chart body, or map body was replaced by a generic redraw without an explicit, defensible reason
- a figure route that contains raster/source-specific visuals finishes with `Assets: 0` or `Image elements: 0` without a documented `no-assets-needed` rationale
- OCR text is wrong but treated as certain
- important labels are rasterized when they should be editable
- formula-like content remains inside `type: "text"` instead of being split into `math`
- `editability_report.md` shows low text lift ratio or many asset text risks
- `quality_report.md` shows `pptx_export` is not `ok` when a PPTX was expected
- `quality_report.md` shows `pptx_math_export` is not `ok` for any important formula that must remain editable in PowerPoint

## Role Split

### Model Responsibilities

- Classify figure route and reconstruction mode.
- Decide semantic groups and reading order.
- Decide crop vs redraw vs retype vs math by element gate.
- Author final `manifest.json`.
- Keep the final SVG clean and interpretable.

### PaddleOCR Responsibilities

- Provide text candidates, bounding boxes, and confidence.
- Help locate labels and estimate font sizes.
- Flag low-confidence text for review.
- Prefer PP-OCRv6 medium evidence for final reconstruction runs when the local
  environment supports PaddleOCR 3.7 or newer. Use smaller v6 profiles for
  speed-sensitive drafts, not for final small-text review.
- OCR is still not ground truth: high-confidence confusions such as `I/l/1`,
  `O/0`, CJK near-neighbor characters, code tokens, paths, and formula symbols
  must be checked against the source image.

### OpenCV Responsibilities

- Provide candidate lines, rectangles, arrowheads, and dashed groups.
- Sample colors and style tokens.
- Help verify crop boundaries and structure alignment.

OpenCV candidates are never automatically final. They must be accepted, merged, ignored, or replaced by the model-authored manifest.

## Experimental Script

`scripts/reconstruct_editable_svg.py` is retained as an experimental auto-reconstruction path. Do not use it as the default high-quality route. It is useful for stress-testing detectors, but it can over-vectorize maps and charts.

## Quality Standard

Acceptable output must include:

- main titles, section headers, and key labels
- correct major panels and grouping relationships
- correct major arrows and flow direction
- source-preserved visual assets for maps/charts/screenshots when those objects exist in the source
- editable text for ordinary labels
- vector-rendered math for all detected formulas, with normalized LaTeX recorded in each `math` element
- editable Office Math equations in `editable.pptx` for every converted formula
- no formula-like text leakage in `quality_report.md`
- a route-appropriate asset inventory: optional for pure text/shape diagrams, required when the source contains pictorial/raster/source-specific visuals
- source-preserved crops for distinctive icons, logos, screenshots, thumbnails, avatars, hand-drawn objects, document/folder graphics, chart bodies, and map bodies unless the manifest documents why each one is a generic redraw
- clean SVG without detector noise
- manifest fields documenting `decision`, `detector`, `confidence`, and `review_status` where relevant
- high editability: most readable labels outside dense chart/map bodies are SVG text
- asset purity: raster assets should not contain large titles, flow labels, arrows, or editable frames unless explicitly marked with `text_policy`
- structure coverage: major boxes, frames, separators, and arrows are SVG primitives when their geometry is stable

Use `scripts/audit_editability.py manifest.json` after composing. Treat these as review triggers:

- text lift ratio below roughly `0.45` when OCR evidence is available
- more than a dozen likely-editable OCR boxes trapped inside assets
- many large assets with `text_policy: review`

## Reference Files

Read reference files according to the route and element gates:

- `references/manifest_spec.md`: manifest field reference. Use for every task.
- `references/svg_authoring.md`: SVG authoring conventions, layering, and fonts. Use for every task.
- `references/quality_checklist.md`: validation checklist before delivery. Use for every task.
- `references/workflow.md`: detailed end-to-end reconstruction workflow. Read for complex, unfamiliar, or mixed-route figures.
- `references/taxonomy.md`: figure classification and reconstruction modes. Read before deciding the reconstruction approach for an unfamiliar figure type.
- `references/formula-reconstruction.md`: full `math` element schema and inline-math splitting rules. Required when formulas or inline math appear.
- `references/element_decision_matrix.md`: element-level redraw vs crop vs retype decisions. Required when the figure contains both editable structure and non-structural visual objects.
- `references/asset_preservation_policy.md`: rules for preserving source visual objects as raster assets. Required when the figure contains icons, logos, screenshots, thumbnails, pictorial objects, maps, chart bodies, or source-specific marks.
- `references/asset_extraction.md`: cropping and asset boundary verification rules. Required when assets are needed or when deciding whether raster/source-specific visuals can be safely redrawn.

## Script Map

- `scripts/prepare_measurements.py`: OCR/CV/style evidence only.
- `scripts/compose_svg_package.py`: compose a package from a model-authored manifest.
- `scripts/export_pptx_from_svg.py`: export `editable.svg` to native PPTX.
- `scripts/pptx_math.py`: convert manifest LaTeX to editable PPTX Office Math.
- `scripts/formula_text_detection.py`: detect formula-like content left in text elements.
- `scripts/svg_to_pptx/`: bundled SVG-to-DrawingML converter used for PPTX output.
- `scripts/svg_finalize/flatten_tspan.py`: bundled text-layout helper for PPTX-safe multi-line SVG text.
- `scripts/pptx_animations.py`: bundled optional transition/animation XML helpers used by the PPTX converter.
- `scripts/audit_editability.py`: audit text lift ratio, asset text risk, and SVG editability.
- `scripts/detect_ocr_paddle.py`: PaddleOCR adapter.
- `scripts/detect_primitives_cv.py`: OpenCV diagnostics.
- `scripts/sample_styles.py`: color/style sampling.
- `scripts/infer_assets.py`: experimental asset inference utilities.
- `scripts/generate_diagnostics.py`: diagnostic overlays.
- `scripts/quality_audit.py`: XML/render/report checks.
- `scripts/reconstruct_editable_svg.py`: experimental full-auto path, not default.
- `scripts/build_svg_from_manifest.py`: SVG generator.
- `scripts/embed_svg_assets.py`: embedded SVG generator.
- `scripts/validate_manifest.py`: manifest validation.
