# Reconstruction Workflow

## 1. Intake and Intent

Determine the user's intent before reconstruction:

- pixel-faithful reconstruction
- editable structural reconstruction
- asset-preserving hybrid reconstruction
- semantic redraw
- publication cleanup or redesign

If the user does not specify, default to asset-preserving hybrid reconstruction.

Background-aware reconstruction extends the standard FigEdit workflow. It does not replace OCR review, structure redraw, formula reconstruction, asset preservation, native PPTX export, or visual repair.

## 2. Recognition and Measurement Pass

Run `scripts/prepare_measurements.py` for every figure before manifest authoring. Inspect:

- OCR candidates and `diagnostics/ocr_overlay.png`
- detected primitives and `diagnostics/structure_overlay.png`
- sampled style tokens and `diagnostics/style_overlay.png`
- `measurement_report.md`
- `draft_manifest.json`
- source image copied to the task workspace

Use diagnostics for measurement and verification only. Do not use `draft_manifest.json` as the final manifest. Do not bulk-import OpenCV segments, false arrows, or OCR fallback text into `elements`.

## 3. Classify the Figure

Record:

- layout topology
- content complexity
- style type
- reconstruction mode
- expected asset fidelity level

Use `taxonomy.md` when the type is unfamiliar. The default route remains conventional FigEdit; the background route is decided only by the Background Gate in `background_reconstruction.md`.

## 4. Build Inventories

### Structure inventory

Include panels, cards, frames, table/grid structures, separators, background blocks, connectors, and arrows.

Default decision: `redraw`.

### Text and formula inventory

Include titles, section headers, labels, annotations, legends, captions, mathematical formulas, equations, and inline math spans.

Default decision: ordinary prose labels use `retype`; math-bearing spans use editable `math` with normalized LaTeX. For dense figures, record the source slot, baseline, and neighboring collision constraints before final placement. OCR boxes are hints; verify each tight label or formula against the source crop or tile.

### Asset inventory

Include icons, pictograms, illustrations, logos, maps, screenshots, thumbnails, photos, hand-drawn objects, model outputs, UI fragments, and other source-specific visuals.

Default decision: `crop` unless the object passes the redraw eligibility test in `asset_preservation_policy.md`.

Do not redraw source-specific icons, logos, screenshots, custom pictograms, evidence thumbnails, technical symbols, or distinctive decorative marks just because they are small. If uncertain, crop.

### Background inventory

Identify the visual field behind foreground text and marks:

- flat fills and simple single-zone gradients
- clean crop regions
- photographs, illustrations, rendered scenes, textures, grain, stars, terrain, atmosphere, water, clouds, glow, lighting, collage, or painterly fields
- regions where foreground labels hide unknown pixels
- text-like material that may be background detail rather than editable foreground

Then ask the Background Gate question from `background_reconstruction.md`: can clean crops plus simple deterministic SVG faithfully reconstruct the background field without inventing scene pixels?

## 5. Decide Element Strategy

Apply these gates:

1. Formula Gate: formulas and inline math become `math`.
2. Text Gate: readable foreground text becomes SVG text.
3. Structure Gate: panels, connectors, simple marks, and primitives are redrawn.
4. Raster Asset Gate: source-specific visuals are cropped when exact identity matters.
5. Background Gate: continuous scene-like backgrounds with foreground overlays become `ai-clean-plate` unless mechanically recoverable.

Record decisions and reasons in the manifest. Keep optional summaries concise; do not add fields as ceremony.

## 6. Prepare Background and Assets

### Conventional route

No `background_plan`. Use this only when the background is mechanically recoverable: ordinary SVG fills, simple regular gradients, measured geometric regions, or clean source crops. Prepare assets normally:

- create source bounding boxes
- add padding
- crop to `assets/` as rectangles (`crop_assets.py`); a standalone transparent asset comes from chroma regeneration per `chroma_regeneration.md`, not from salient-object matting
- record target placement
- generate contact sheet
- verify crops are not clipped, dirty, or missing

### AI clean-plate route

Use this after the Background Gate selects `ai-clean-plate`, or when the user's own words request the AI route regardless of the gate's default (record `route_decision.source: "user-directive"`).

1. Build the foreground inventory and make the Foreground Depth Decision (`background_reconstruction.md`). This is a hard checkpoint: unless the user's own words state a depth preference, stop and present the mode options (with inventory, cost, and a recommendation) before any generation call. Record `background_plan.foreground_mode` and `foreground_mode_source`.
2. Write a dynamic generation brief using `ai_clean_plate_prompting.md`; its remove list mirrors the extraction scope.
3. Invoke a reference-capable image backend according to `image_backend_policy.md` — the agent's own built-in image tool first, scriptable backends as fallback.
4. Accept only a full-canvas clean plate that removes the in-scope foreground and preserves the declared visual identity.
5. Add the accepted plate as the bottom background asset.
6. Regenerate the in-scope foreground objects on a chroma sheet and key them apart (`chroma_regeneration.md`) — the whole inventory on one sheet, split only if a single sheet visibly fails. Do not crop these objects from the original and do not run salient-object matting or improvised cutout scripts.
7. Overlay editable text, formulas, simple marks, and the extracted assets.

Do not crop large rectangular blocks from the original source over the plate. Do not crop old labels, leaders, or callout residue back into the final output. If an object is inseparable and low-edit-value even for regeneration, leave it in the clean plate.

If no acceptable clean plate can be produced, report a blocker rather than downgrading silently.

## 7. Rebuild Structural SVG

Draw:

- canvas background or clean plate placement
- panel outlines
- cards and content blocks
- separators
- arrows and connectors
- table/grid lines
- simple structural symbols

Use semantic groups and IDs.

## 8. Retype Text and Rebuild Formulas

Retype text as SVG text:

- preserve visual hierarchy
- use readable fallback fonts
- manually split long lines
- preserve source-region fit, alignment, and baseline for dense labels
- mark uncertain text in the manifest

For formulas, use `type: "math"` and a normalized `latex` string. Do not approximate formulas with plain text, and do not crop formulas as images to avoid layout work. Every detected formula should remain editable in PPTX unless the user explicitly waives formula editability for that specific item.

For formula-heavy or small-text-dense figures:

1. place each formula/text element into a measured source slot
2. render SVG preview and repair local collisions
3. export native PPTX
4. inspect or render the PPTX and repair PowerPoint-specific reflow, baseline, and overflow issues

Passing `pptx_math_export` means the formulas are editable; it does not prove that the PowerPoint layout is visually correct.

Before finalizing, scan text elements for formula cues, OCR artifacts, and fallback garbage.

## 9. Place Assets

Place cropped assets using `<image>` elements.

- Preserve aspect ratio.
- Use masks or clipping only when necessary.
- Do not stretch assets unless the source itself is stretched.
- Align assets to the recreated structure.
- Mark generated assets as approximate.
- Keep source-specific assets source-preserved when exact identity matters.

## 10. Generate Deliverables

Create:

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `quality_report.md`
- `editability_report.md`
- `assets/`

The `editable.pptx` is a native PowerPoint export of the same reconstruction. Formula elements should appear as editable Office Math objects when `pptx_math_export` is `ok`. Ordinary layer/layout groups are flattened during PPTX export so users can select text, shapes, connectors, and cropped assets directly; preserve only explicit atomic groups that need to stay together for fidelity.

For tight text or formula layouts, treat PPTX export as another render target, not as a packaging afterthought. Native PPT text and Office Math may reflow differently from SVG; repair the manifest until both deliverables are acceptable.

## 11. Validate and Repair

Use `quality_checklist.md`.

Repair order:

1. raw detector candidates, OCR fallback text, or OpenCV noise leaked into SVG
2. missing information
3. wrong structure or arrow direction
4. missing or wrongly redrawn source-specific assets
5. contaminated, clipped, haloed, or misplaced crops
6. background route errors, ghosts, seams, or patchwork source blocks
7. unreviewed generated content
8. formula and text editability problems
9. formula/text placement problems in SVG or PPTX
10. visual polish
