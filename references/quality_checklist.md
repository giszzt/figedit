# Quality Checklist

## Acceptance Dimensions

Evaluate the reconstruction across seven dimensions:

1. information completeness
2. structural accuracy
3. text editability
4. connector correctness
5. visual asset fidelity
6. crop precision
7. engineering maintainability

## Information Completeness

- [ ] Main title is present.
- [ ] Section and panel titles are present.
- [ ] Key labels and annotations are present.
- [ ] Important visual examples, thumbnails, icons, screenshots, maps, or logos are present.
- [ ] No major object from the source figure is silently omitted.

## Structural Accuracy

- [ ] Layout topology matches the source figure.
- [ ] Panels, cards, groups, and nesting relationships are correct.
- [ ] Alignment and spacing are close enough to preserve reading order.
- [ ] Table/grid structures are clear.

## Text Editability

- [ ] Ordinary labels and annotations are SVG text, not image-only text.
- [ ] Text is not converted to paths unless explicitly required.
- [ ] Long labels do not overflow containers.
- [ ] Uncertain text is marked in the manifest or report.

## Formula Rendering

- [ ] Every detected mathematical formula is a `math` element with normalized LaTeX.
- [ ] Inline formulas inside titles, labels, captions, legends, nodes, and axis labels are split into separate `math` elements.
- [ ] Plain text elements do not contain TeX syntax, Unicode super/subscripts, compact Greek-variable formulas, or formula operators unless explicitly marked `formula_policy: "not-formula"`.
- [ ] Fractions, summations, scripts, Greek symbols, hats, and bars render as formula layout, not plain text.
- [ ] Rendered formula groups retain `data-latex` for traceability.
- [ ] The quality report lists the expected count of SVG math elements.
- [ ] `quality_report.md` shows `formula_text_leakage: ok`.
- [ ] `editable.pptx` contains editable Office Math objects for converted formulas.
- [ ] `quality_report.md` shows `pptx_math_export: ok` when formula editability is required.
- [ ] Any formula listed in `editable.pptx.math_report.json` as a failure is repaired or explicitly accepted as vector-only.

## Connector Correctness

- [ ] Arrow directions match the source.
- [ ] Connector endpoints point to the correct objects.
- [ ] Dashed/solid line semantics are preserved when meaningful.
- [ ] Feedback loops or branching structures are clear.

## Visual Asset Fidelity

- [ ] The figure route was identified: simple text/shape, composite workflow,
      screenshot/UI/map/photo/chart body, formula-heavy, or mixed.
- [ ] If the route includes pictorial/raster/source-specific visual objects,
      an asset inventory exists for every icon, logo, screenshot, thumbnail,
      avatar, hand-drawn object, document/folder graphic, chart body, map body,
      model mark, or other source-specific visual object.
- [ ] If the route is pure text/shape, `Assets: 0` is acceptable and documented
      by the route decision.
- [ ] Source-specific icons and pictorial objects are preserved as cropped assets unless explicitly approved for redraw.
- [ ] Custom visual objects were not replaced by generic approximations.
- [ ] Logos/model marks retain source appearance.
- [ ] Photos, screenshots, maps, thumbnails, and collages are preserved.
- [ ] Repeated assets are visually consistent with the source.
- [ ] If `Assets: 0` or `Image elements: 0` appears for a route that contains
      raster/source-specific visuals, the manifest documents a clear
      `no-assets-needed` rationale; otherwise the result is not accepted.

## Crop Precision

- [ ] Asset crops are not visibly clipped.
- [ ] Asset crops do not include unrelated neighboring elements.
- [ ] Padding is sufficient for strokes, shadows, and texture.
- [ ] Assets are not stretched or distorted.
- [ ] Contact sheet has been reviewed.

## Engineering Maintainability

- [ ] SVG groups have semantic IDs.
- [ ] Assets have meaningful filenames.
- [ ] Manifest records element decisions and source/target boxes.
- [ ] External and embedded SVG variants are generated when possible.
- [ ] Native `editable.pptx` is generated, and `quality_report.md` shows `pptx_export: ok` when PowerPoint editability is requested.
- [ ] Native `editable.pptx` formula export is checked separately from general PPTX export.
- [ ] Preview image is generated when rendering tools are available.

## High-Priority Failure Conditions

Fix before delivery if any of these occur:

- missing panel or major visual group
- wrong arrow direction or relationship
- source-specific icon replaced with invented generic SVG
- pictorial/raster/source-specific visual objects were not inventoried before
  manifest authoring
- a route containing raster/source-specific visuals has `Assets: 0` or
  `Image elements: 0` without a documented reason
- a pure text/shape route incorrectly performs unnecessary asset extraction
- important crop clipped or misplaced
- user-relevant text baked into raster when it should be editable
- detected formulas represented as plain text approximations instead of math elements
- formula-like content remains inside `type: "text"` and appears under `formula_text_leakage`
- PPTX formulas visible only as vector artwork when the user requires editable equations
- SVG cannot open in common tools

## Repair Order

1. Restore missing information.
2. Correct structure and connectors.
3. Replace inappropriate redraws with cropped source assets.
4. Fix clipped or inaccurate crops.
5. Fix text overflow and alignment.
6. Improve visual polish.
