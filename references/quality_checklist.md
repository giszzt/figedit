# Quality Checklist

## Acceptance Dimensions

Evaluate the reconstruction across nine dimensions:

1. information completeness
2. structural accuracy
3. text editability
4. connector correctness
5. visual asset fidelity
6. crop precision
7. background route integrity
8. text and formula layout fidelity
9. engineering maintainability

## Information Completeness

- [ ] Main title is present.
- [ ] Section and panel titles are present.
- [ ] Key labels and annotations are present.
- [ ] Important visual examples, thumbnails, icons, screenshots, maps, logos, or source-specific marks are present.
- [ ] No major object from the source figure is silently omitted.

## Structural Accuracy

- [ ] Layout topology matches the source figure.
- [ ] Panels, cards, groups, and nesting relationships are correct.
- [ ] Alignment and spacing are close enough to preserve reading order.
- [ ] Table/grid structures are clear.
- [ ] OpenCV candidate noise, texture lines, compression edges, duplicate segments, and false arrowheads are not present in the final SVG.

## Text Editability

- [ ] Ordinary labels and annotations are SVG text, not image-only text.
- [ ] Text is not converted to paths unless explicitly required.
- [ ] Long labels do not overflow containers.
- [ ] Uncertain text is marked in the manifest or report.
- [ ] OCR fallback text is not accepted without source-image verification.

## Formula Rendering

- [ ] Every detected mathematical formula is a `math` element with normalized LaTeX.
- [ ] Inline formulas inside titles, labels, captions, legends, nodes, and axis labels are split into separate `math` elements.
- [ ] Plain text elements do not contain TeX syntax, Unicode super/subscripts, compact Greek-variable formulas, or formula operators unless explicitly marked `formula_policy: "not-formula"`.
- [ ] Fractions, summations, scripts, Greek symbols, hats, and bars render as formula layout, not plain text.
- [ ] Rendered formula groups retain `data-latex` for traceability.
- [ ] `quality_report.md` shows formula leakage and PPTX math export gates.
- [ ] Any formula listed in `editable.pptx.math_report.json` as a failure is repaired unless the user explicitly waives formula editability for that item.
- [ ] Formula-heavy figures have been checked for visual placement after native PPTX export, not only for successful Office Math conversion.

## Text and Formula Layout Fidelity

- [ ] Small text and formulas occupy the same visual slots as the source image.
- [ ] Dense labels, formulas, code snippets, and node captions do not overlap boxes, arrows, or neighboring text.
- [ ] Mixed prose/formula lines share a consistent baseline.
- [ ] Text boxes in PPTX do not overflow, wrap unexpectedly, or shift relative to SVG preview.
- [ ] Office Math objects remain inside their intended bounding boxes after PowerPoint reflows them.
- [ ] Formula editability is preserved; formulas are not replaced with raster crops to avoid layout work.
- [ ] For high-density figures, the final PPTX has been opened or rendered for visual review before delivery.

## Connector Correctness

- [ ] Arrow directions match the source.
- [ ] Connector endpoints point to the correct objects.
- [ ] Dashed/solid line semantics are preserved when meaningful.
- [ ] Feedback loops or branching structures are clear.

## Visual Asset Fidelity

- [ ] The figure route was identified: simple text/shape, composite workflow, screenshot/UI/map/photo/chart body, formula-heavy, image-heavy/continuous background, or mixed.
- [ ] If the route includes pictorial/raster/source-specific visual objects, an asset inventory exists for every icon, logo, screenshot, thumbnail, avatar, hand-drawn object, document/folder graphic, chart body, map body, model mark, or other source-specific visual object that must retain identity.
- [ ] If the route is pure text/shape, `Assets: 0` is acceptable and documented by the route decision.
- [ ] Source-specific icons and pictorial objects are preserved as cropped assets unless explicitly approved for redraw.
- [ ] Custom visual objects were not replaced by generic approximations.
- [ ] Logos/model marks retain source appearance.
- [ ] Photos, screenshots, maps, thumbnails, and collages are preserved or intentionally flattened inside an accepted clean plate.
- [ ] If `Assets: 0` or `Image elements: 0` appears for a route that contains raster/source-specific visuals, the manifest documents a clear `no-assets-needed` rationale; otherwise the result is not accepted.

## Crop Precision

- [ ] Asset crops are not visibly clipped.
- [ ] Asset crops do not include unrelated neighboring elements.
- [ ] Padding is sufficient for strokes, shadows, and texture.
- [ ] Assets are not stretched or distorted.
- [ ] Contact sheet has been reviewed.
- [ ] AI clean-plate overlays do not use large dirty source crops, old labels, callout residues, or rectangular patch seams.

## Regenerated Assets (regenerate-chroma)

- [ ] Every regenerated asset has `generation_provenance` (backend, prompt file, reference, sheet) and `asset_fidelity` of `approximate-ok` or reviewed `source-close`; none is labeled `source-preserve`.
- [ ] Each element was compared side by side against its source counterpart: same silhouette, orientation, colors, and details; no invented or dropped parts; no baked-in labels or pseudo-text.
- [ ] The `chroma_key.py` report shows no unresolved warnings (fringe, key-colored content, empty sheet), and enclosed holes inside elements are transparent, not tinted.
- [ ] Any content category may be regenerated; there is no approval gate. Where exact source pixels must not drift (a chart read for its values, a compliance logo), the object was kept flattened in the plate or coordinate-cropped as an opaque rectangle, not chased with a fragile cutout.
- [ ] The regeneration scope matches `foreground_mode` (full inventory under full-extract, exactly the named subset under selective, none under flatten), mirrors the clean-plate remove list, and repeated elements were regenerated once and placed by shared `asset_id`.
- [ ] In-scope foreground objects were regenerated on a chroma sheet and keyed apart, not cropped from the original or separated with salient-object matting (rembg/U2-Net) or improvised GrabCut/difference/threshold scripts. `chroma_key.py` reports show no unresolved fringe/eaten-content warnings.
- [ ] Foreground regeneration put the whole inventory on one sheet unless a single sheet visibly failed (elements dropped, merged, or too coarse to read). An absolute element-count cap or a per-element pixel budget is not a valid split reason.

## Background Route Integrity

- [ ] Conventional figures have no `background_plan`, unless `route_decision.source` is `user-directive`.
- [ ] AI clean plate is used when clean crops plus simple deterministic SVG cannot faithfully reconstruct the continuous background field.
- [ ] AI clean plate is not used merely because the figure is dense, icon-heavy, or poster-like; a route explicitly requested by the user and recorded as `route_decision.source: "user-directive"` passes this check.
- [ ] Conventional routing is not justified by saying the agent can manually redraw scenery, texture, lighting, or multi-zone illustrated backgrounds; a user-directed conventional route is recorded with its stated fidelity cost.
- [ ] AI clean plate has an accepted full-canvas plate, generation provenance, candidate review, and canvas alignment.
- [ ] `background_plan.foreground_mode` and `foreground_mode_source` are recorded; the source is `user-choice` or `explicit-request` (quoting the user's wording), and `auto-default` appears only for unattended runs. Selecting a mode from the figure's characteristics while the user was available is a gate violation.
- [ ] The plate's remove list matches the recorded mode.
- [ ] The accepted plate is not the untouched source image with old foreground still visible.
- [ ] The accepted plate is not a local blur/clone/fill/inpaint result disguised as image generation.
- [ ] Foreground overlays after AI clean plate are mostly editable text, formulas, and simple marks.
- [ ] Distinctive assets are cropped back only when identity matters, independent movement is useful, and the crop is clean.
- [ ] Text-like background inscriptions are preserved or removed according to source analysis, not by a blanket "remove all text" rule.

## Engineering Maintainability

- [ ] SVG groups have semantic IDs.
- [ ] Assets have meaningful filenames.
- [ ] Manifest records element decisions and source/target boxes.
- [ ] External and embedded SVG variants are generated when possible.
- [ ] Native `editable.pptx` is generated, and `quality_report.md` shows `pptx_export: ok` when PowerPoint editability is requested.
- [ ] Native `editable.pptx` formula export is checked separately from general PPTX export.
- [ ] Native `editable.pptx` is not delivered as one large grouped object; ordinary text, shapes, connectors, and cropped assets are directly selectable, while only semantic atomic groups remain grouped.
- [ ] Preview image is generated when rendering tools are available.

## High-Priority Failure Conditions

Fix before delivery if any of these occur:

- missing panel or major visual group
- wrong arrow direction or relationship
- source-specific icon replaced with invented generic SVG
- pictorial/raster/source-specific visual objects were not inventoried before manifest authoring
- a route containing raster/source-specific visuals has `Assets: 0` or `Image elements: 0` without a documented reason
- a pure text/shape route incorrectly performs unnecessary asset extraction
- important crop clipped or misplaced
- user-relevant text baked into raster when it should be editable
- detected formulas represented as plain text approximations instead of math elements
- formula-like content remains inside `type: "text"` and appears under `formula_text_leakage`
- PPTX formulas visible only as vector artwork unless the user explicitly waived formula editability for those formulas
- PPTX formulas are editable but visibly misplaced, oversized, baseline-shifted, or colliding with nearby content
- dense text/formula figures are delivered without PPTX visual review
- PPTX output requires the user to manually ungroup the whole figure or major layout layers before selecting normal elements
- SVG cannot open in common tools
- OpenCV raw candidates, OCR fallback garbage, draft-manifest lines, or false arrows appear in the final SVG
- a continuous scene-like background with foreground overlays was routed conventional because the agent planned to approximate it with hand-authored SVG scenery
- `ai-clean-plate` is silently downgraded to conventional after the gate selected it
- `ai-clean-plate` result is a patchwork of large source crops over a generated background
- source crops contain old labels, leader lines, or annotation residue that should have been rebuilt

## Repair Order

1. Restore missing information.
2. Correct structure and connectors.
3. Replace inappropriate redraws with cropped source assets.
4. Remove detector/OCR noise from final elements.
5. Fix clipped or inaccurate crops.
6. Repair background route errors.
7. Fix text, formula, and baseline alignment in SVG and PPTX.
8. Improve visual polish.
