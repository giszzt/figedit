---
name: figedit
description: Convert raster figures into high-fidelity editable SVG and native PowerPoint packages. Use for screenshots, paper figures, workflow diagrams, architecture diagrams, infographics, UI schematics, charts/maps, posters, covers, and image-heavy technical figures when labels, formulas, structure, source-specific assets, and complex continuous backgrounds must be reconstructed with useful editability.
---

# FigEdit

Use this skill to rebuild a non-editable raster figure as a high-fidelity editable graphics package. It keeps the base FigEdit workflow as the default, and adds one extra decision gate for complex continuous backgrounds.

The goal is not "vectorize everything," "crop everything," or "send everything to AI." Route each part of the source image to the representation that preserves both fidelity and useful editability:

- structural elements become editable SVG shapes
- readable labels become editable SVG text
- formulas become normalized `math` elements and editable PowerPoint equations
- source-specific raster visuals become cropped assets placed with `image` elements
- dense charts, maps, screenshots, thumbnails, and pictorial evidence are cropped unless the user explicitly needs them rebuilt
- a complex continuous background becomes an AI clean plate when crop + simple, deterministic SVG cannot faithfully reconstruct it

OpenCV and OCR evidence can guide measurements and validation, but they do not decide what enters the final SVG. Do not dump all OpenCV candidates, OCR boxes, or draft-manifest objects into the final package.

## Working Location

Run every command from the user's project directory, not from the skill folder. Create one task directory per figure in the user's workspace, and write all intermediates and outputs there. Never write run artifacts back into the skill directory.

The examples below use `figure-task/work` for evidence and `figure-task/out` for the final package.

## Default Workflow

### 1. Prepare Measurement Evidence

Run:

```powershell
python scripts/prepare_measurements.py input.png --out figure-task/work
```

Use forward slashes in all script arguments; trailing backslashes are swallowed by some shells.

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

OCR defaults to PaddleOCR's PP-OCRv6 medium profile when available. Use smaller profiles for fast drafts, not for final small-text review. OCR is never ground truth: verify high-confidence confusions, code tokens, CJK near-neighbor characters, and formula symbols against the source.

### 2. Route The Figure

Inspect the source image and diagnostics before authoring the manifest. Classify the semantic figure route first; do not choose an AI background route merely because the image is visually dense, and do not reject it merely because the background could be redrawn by a skilled illustrator. The question is whether FigEdit can reconstruct it reliably from simple SVG primitives and clean source crops.

- **Simple text/shape diagram**: mostly labels, boxes, arrows, grids, and basic geometric marks. Usually redraw structure and retype text.
- **Workflow, architecture, method, or infographic composite**: mixed panels, text, formulas, connectors, icons, screenshots, logos, document/folder graphics, or pictorial marks. Decompose panel-by-panel and apply the element gates below.
- **Screenshot, UI, map, photo, chart, thumbnail, or dense visual body**: preserve the visual body as a raster asset unless the user explicitly asks for a data/editable rebuild; lift surrounding readable labels separately.
- **Formula-heavy figure**: route every equation and inline math span through editable `math` reconstruction, with source-bbox and baseline constraints so formulas remain visually aligned after SVG and PPTX export.
- **Design-led or image-heavy figure**: posters, covers, social cards, illustrated scenes, rendered scenes, and other visuals whose labels sit on a continuous visual field. This may need AI clean plate, but the Background Gate decides by background recoverability, not by genre.

Reference loading is route-based:

- Always use `references/manifest_spec.md`, `references/svg_authoring.md`, and `references/quality_checklist.md`.
- If the figure type is unfamiliar or mixed, read `references/taxonomy.md` and `references/workflow.md`.
- If any formula or inline math appears, read `references/formula-reconstruction.md`.
- If any pictorial, raster, screenshot, logo, map, chart body, thumbnail, avatar, hand-drawn object, model mark, document/folder graphic, or source-specific icon appears, read `references/element_decision_matrix.md`, `references/asset_preservation_policy.md`, and `references/asset_extraction.md`.
- If any asset routes to `regenerate-chroma` (contaminated, entangled, or continuous-background elements), read `references/chroma_regeneration.md` and `references/image_backend_policy.md`.
- If the background is not plainly mechanical, or if labels/marks/assets sit over a continuous visual field, read `references/background_reconstruction.md`.
- If the Background Gate selects `ai-clean-plate`, also read `references/ai_clean_plate_prompting.md` and `references/image_backend_policy.md`.

### 3. Apply Element Decision Gates

Author the manifest by deciding every significant element through these gates. These rules are peers; none is a universal first step.

#### Structure Gate

Redraw structural elements as editable SVG shapes:

- panels, cards, frames, section headers, dividers, rules, grids, table borders
- simple arrows, connectors, dashed boxes, brackets, axes, and plain geometric markers
- simple flat color backgrounds

Use OpenCV coordinates as measurement hints, not as automatic truth. Reject detector-only texture lines, compression edges, false arrowheads, duplicate hatching, and raw contour noise.

#### Text Gate

Retype readable labels, titles, captions, legends, axis labels, callouts, and ordinary annotations as SVG text. Use OCR only as candidate evidence. Mark uncertain text in the manifest; do not accept OCR fallback text merely because it exists.

For dense paper figures, architecture diagrams, and formula-heavy composites, text placement is part of the reconstruction, not a cosmetic pass. Record or infer the source region, line breaks, alignment anchor, and baseline for small labels before writing the final text element. A label is not complete just because the characters are correct; it must fit the same visual slot without colliding with boxes, arrows, formulas, or neighboring labels in both SVG preview and native PPTX.

#### Formula Gate

Mathematical formulas are first-class semantic objects. Author equations, inequalities, fractions, sums, Greek symbols, scripts, recurrences, and inline math spans as `math` elements with normalized LaTeX, never as formula strings inside `type: "text"`.

For mixed prose/formula regions, split the prose into `text` and the formula span into a separate adjacent `math` element. Before finalizing, scan text elements for formula cues and repair leaks.

Formula editability is a core requirement. Do not solve formula density by cropping equations as images or by leaving formula-like strings as plain text. The correct repair for a misplaced editable formula is better measurement and layout control: source bounding box, width/height, font size, anchor, baseline, and local collision checks.

Treat PPTX formula export as a two-part requirement:

- the formula must become an editable Office Math object
- the resulting Office Math object must still occupy the intended visual slot after PowerPoint reflows it

If PowerPoint's equation layout changes the formula size, baseline, or spacing, adjust the manifest and rerun composition. Do not mark the result complete merely because `editable.pptx.math_report.json` shows a successful conversion.

#### Raster Asset Gate

Crop source-specific raster visuals as assets. This includes pictorial icons, logos, application/model marks, screenshots, maps, chart bodies, thumbnails, photos, UI fragments, avatars, robots, hand-drawn props, document/folder graphics, and dense visual examples.

Do not replace source-specific visual objects with generic invented SVG. Redraw only when the object is a clearly generic primitive or the user explicitly requests editable vectorization. When uncertain, crop.

How a raster asset is obtained depends on the route, and there are exactly two methods — no salient-object matting anywhere. The route sets the default method; the user's explicit request can send any individual asset to either method (e.g. regenerate a crop-eligible asset for cleaner edges, or keep a crop the user prefers):

- **Conventional route — coordinate crop.** Crop the smallest visually meaningful rectangle from the source (`crop_assets.py` from the manifest's `source_region`), keeping surrounding labels, frames, and arrows editable. Do not drag unrelated background, old labels, callout lines, or neighboring objects into the crop. The asset is placed as a rectangular `image`; assets on flat/white/simple backgrounds need no alpha at all. This is the default for screenshots, chart bodies, maps, logos on flat fields, and any figure whose assets sit on a separable background.
- **AI route — generate, then key.** When the Background Gate selects `ai-clean-plate` with `full-extract`/`selective`, the foreground is not cropped from the original at all. A reference-capable image model reproduces the in-scope elements on a solid chroma sheet chosen by `probe_palette.py`; `chroma_key.py` + `slice_grid.py` then separate each element as a clean transparent PNG. This "generate a clean foreground sheet, then key it apart" path is the only way in-scope objects become transparent assets on this route. Record `decision: "regenerate-chroma"`, `asset_fidelity: "approximate-ok"`, and `generation_provenance`.

Anything can be AI-regenerated — photos, people, illustrations, icons, badges, logos, screenshots, charts, maps, composite objects — with no content-category approval gate; quality is a function of the model and prompt, so hard cases call for a sharper preserve-the-element prompt, not a refusal. Put the whole foreground inventory on **one sheet** (`chroma_regeneration.md`) and only split when the model visibly cannot fit or resolve them all; regenerate each distinct element once and place repeats by shared `asset_id`. Never improvise GrabCut/difference/threshold/rembg matting scripts to separate objects from a natural background — on the AI route the sheet background is already flat and keys exactly; on the conventional route a rectangle crop is enough.

#### Background Gate

Apply this gate after the structure, text, formula, and asset gates have claimed everything they can faithfully represent. It answers one question:

**Can the base FigEdit hybrid route, using clean source crops plus simple deterministic SVG primitives, faithfully reconstruct the background field without asking the model to invent or hand-paint scene pixels?**

- **Yes: use the conventional FigEdit route.** Do not add `background_plan` unless the user explicitly requests the AI route. Redraw structure and text as SVG, crop source-specific visuals as raster assets, and mix them panel-by-panel. This is the default for regular paper figures, workflow diagrams, architecture diagrams, white/light-background diagrams, charts, maps, UI screenshots, and cleanly framed visual assets whose background is flat, regular, or mechanically reproducible.
- **No: use `ai-clean-plate`.** Use this when foreground text, labels, leader lines, markers, or icons are embedded in a continuous photograph, illustration, rendering, texture, irregular/multi-zone gradient, scene-like infographic, magazine-cover field, poster scene, or technical scene where crop + simple SVG cannot reveal or reproduce the hidden pixels.

The gate decides the default; an explicit route request in the user's own words overrides it in either direction — a user may send a regular figure to `ai-clean-plate` for extraction precision, or keep a scene figure conventional after hearing the fidelity cost. Record `route_decision.source: "user-directive"` and keep the full quality bar (see User Route Directive in `references/background_reconstruction.md`).

This gate is about background recoverability, not content category, visual density, or genre. Do not count hand-recreating a scene as faithful SVG reconstruction; approximate SVG scenery is a redesign, not a high-fidelity rebuild. The authoritative definition of this gate — the recoverability test, the strong-signal list, and the foreground policy after an accepted plate — is `references/background_reconstruction.md`; read it whenever the answer is not obviously "yes".

For `ai-clean-plate`, the clean plate is a complete non-editable visual bottom layer. It must be an **edit of the source that removes the foreground-to-rebuild and reconstructs the pixels behind it, while keeping the original background otherwise unchanged** — same tone, gradient/haze zones, texture, star/grain density, lighting, and structure as the source. It is not a fresh scene: a plate that resynthesizes the background into a visibly different field (different haze placement, different star pattern density, restyled colors) is a redesign and must be rejected and regenerated, even though behind-foreground fill inevitably differs pixel-for-pixel. Overlay editable text, `math`, and simple marks on top. Under `full-extract`/`selective`, in-scope pictorial objects come back as transparent assets from the generated foreground sheet (never as source rectangle crops); under `flatten` they stay in the plate. Prefer a clean flattened plate over a patchwork of dirty source crops.

Before generating the plate, make the **Foreground Depth Decision** (`background_reconstruction.md`): full-extract (all pictorial objects become independent assets), selective (user-named subset), or flatten (objects stay in the plate). The modes need different plates, so decide first. **This is a hard checkpoint: unless the user's own words state a depth preference, stop and present the options — inventory, what each mode buys, relative cost and time, plus your recommendation — before any generation call.** The figure's characteristics inform the recommendation, never a silent choice. Record the mode and its origin in `background_plan.foreground_mode` / `foreground_mode_source`.

If `ai-clean-plate` is selected but no reference-capable image backend is available or accepted, stop and report the blocker. Do not silently downgrade to a conventional reconstruction, keep the untouched source as the plate, or fake a clean plate with local blur/clone/inpaint scripts.

#### Composite Split Rule

Do panel-by-panel semantic decomposition. Do not crop a whole panel merely because it is dense, and do not redraw a whole panel merely because the structure is regular. Split each panel by function:

- structural shell: redraw
- readable label: retype
- formula span: `math`
- flow relation: redraw connector
- source-specific visual evidence: crop asset
- complex continuous background: AI clean plate only if the Background Gate requires it
- tiny chart/map/screenshot-internal text: preserve inside raster unless the user needs it editable

Layer carefully:

- Put canvas fills and clean plates on `layer: background`.
- Put raster evidence on `layer: assets`.
- Put panel borders and box borders on `layer: panels` with `fill: none`.
- Put raster assets that sit **on top of** filled panels or cards (icon tiles inside info cards, badges on banners) on `layer: icons` — it is drawn after `panels`, while `layer: assets` is drawn before and would be hidden by any filled panel.
- Put arrows/connectors on `layer: connectors`.
- Put labels and rendered formulas on `layer: texts`.

Draw order is background → assets → panels → sections → icons → connectors → texts → annotations. Do not draw a filled panel rectangle above an image asset; it will hide the asset in the preview.

### 4. Compose The SVG Package

Run:

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out
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
- `diagnostics/placement_overlay.png`
- `diagnostics/visual_qa/` (side_by_side, blend, diff_heatmap, per-tile scores)

The PPTX is a native DrawingML export. Prefer it when the user needs to edit the figure in PowerPoint. By default, the export uses semantic top-level ungrouping: layer/layout groups are flattened so text, shapes, connectors, and cropped assets can be selected directly, while formulas, masks, filters, rotations, and explicitly atomic groups remain grouped for fidelity.

PowerPoint can reflow text boxes and Office Math differently from the SVG preview. This is expected and must be validated. For formula-heavy or small-text-dense figures, inspect the exported PPTX or a PPTX-rendered preview before delivery and repair any formula/text drift, overflow, baseline shift, or collision.

### 5. Validate And Repair

Inspect:

- `preview.png`
- `contact_sheet.png`
- `editable.pptx` when PowerPoint editability is requested
- a PPTX-rendered visual check when the figure has dense labels, many formulas, or tight text/connector spacing
- `quality_report.md`
- `editability_report.md`
- `diagnostics/placement_overlay.png`
- `diagnostics/visual_qa/diff_heatmap.png` and the worst-tile scores in `quality_report.md` (report-only: high-difference tiles are review triggers, not automatic failures)
- regenerated-asset contact sheets and `chroma_key` reports when `regenerate-chroma` is used
- clean-plate candidates and prompt/provenance records when `ai-clean-plate` is used

Repair against `references/quality_checklist.md` before delivery; its High-Priority Failure Conditions section is the authoritative list. The most frequent blockers: missing panels or wrong arrows, detector/OCR noise in the final SVG, editable content baked into rasters, formula-like text not split into `math`, source-specific visuals replaced by generic redraws or missing entirely (`Assets: 0` without a documented reason), clipped or contaminated crops, clean-plate results patched with dirty source crops, and PPTX exports whose math or tight text has not been visually checked.

## Role Split

### Model Responsibilities

- Classify figure route and reconstruction mode.
- Decide semantic groups and reading order.
- Decide crop vs redraw vs retype vs math by element gate.
- Decide the Background Gate only after element gates have been considered.
- Author final `manifest.json`.
- Keep the final SVG clean and interpretable.

### PaddleOCR Responsibilities

- Provide text candidates, bounding boxes, and confidence.
- Help locate labels and estimate font sizes.
- Flag low-confidence text for review.
- OCR is not ground truth; verify against the source image.

### OpenCV Responsibilities

- Provide candidate lines, rectangles, arrowheads, and dashed groups.
- Sample colors and style tokens.
- Help verify crop boundaries and structure alignment.

OpenCV candidates are never automatically final. They must be accepted, merged, ignored, or replaced by the model-authored manifest.

### Image Generation Responsibilities

Image generation is used after the Background Gate selects `ai-clean-plate`, or when the user's own words request an AI generation route. It creates an accepted clean visual plate from the source image and the model-authored preserve/remove/reconstruct brief.

Before touching any scriptable backend, inventory your own tools: if the agent environment has any built-in image generation/editing tool (Codex `image_gen`, a bundled image tool, an image MCP), use it first. Built-in tools take the reference image from the visible conversation context, not from parameters: display the source image into the conversation (e.g. `view_image`) so it becomes the edit target, then invoke the tool with a prompt that names the just-displayed image as the sole edit target, and collect the output from the tool's save location (Codex: `~/.codex/generated_images/<session>/`). A parameter schema without reference-image or output-path options is normal for built-in tools and is never a reason to skip them; the full protocol is in `references/image_backend_policy.md`. Only when the built-in tool is genuinely absent or an actual invocation fails, fall through the scriptable order in that file: Labnana GPT-Image-2 first, Labnana Gemini/Nano Banana second, then official OpenAI/Gemini APIs or a configured command adapter. A positive `--precheck` only means scriptable fallbacks exist; it is not permission to skip the built-in tool. Backend adapters execute the brief; they do not decide the figure route or foreground asset strategy.

## Quality Standard

Acceptable output preserves all information from the source (titles, labels, panels, arrows, source-specific visuals), keeps ordinary text and every detected formula editable in both SVG and native PPTX, holds their placement after PPTX reflow, and contains no detector noise, no formula-text leakage, and no editable content baked into rasters. For AI clean plate, the deliverable is a clean visual plate plus an editable foreground overlay, never a patchwork of source blocks. The full acceptance dimensions live in `references/quality_checklist.md`.

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
- `references/background_reconstruction.md`: Background Gate and AI clean-plate foreground policy. Read when a continuous visual field may be unrecoverable by crop + SVG.
- `references/ai_clean_plate_prompting.md`: dynamic prompt framework. Required only when `ai-clean-plate` is selected.
- `references/image_backend_policy.md`: environment-neutral image backend policy. Required only when image generation is needed.
- `references/chroma_regeneration.md`: regenerate-then-key pipeline for contaminated or entangled assets. Required when any asset routes to `regenerate-chroma`.
- `references/contaminated_asset_recovery.md`: recovery decisions for assets overlapped by labels, leader lines, or neighbors. Read when a wanted asset cannot be cropped cleanly.
- `references/text_layer_policy.md`: text handling over continuous visual fields. Read when the source has formulas, code, or dense text sitting on a scene or plate.

## Script Map

- `scripts/prepare_measurements.py`: OCR/CV/style evidence only.
- `scripts/compose_svg_package.py`: compose a package from a model-authored manifest.
- `scripts/crop_assets.py`: coordinate-crop rectangular assets from the source using each asset's `source_region`; the conventional-route asset method.
- `scripts/probe_palette.py`: pick a chroma-key color guaranteed far from the source palette, per regeneration sheet.
- `scripts/chroma_key.py`: key a solid chroma background out of a regenerated sheet; decontaminates edges, cast shadows, and enclosed holes; reports edge quality.
- `scripts/slice_grid.py`: slice a keyed sheet into individual transparent assets by connected components, absorbing small detached parts.
- `scripts/visual_compare_qa.py`: pixel-level source-vs-preview comparison (side-by-side, blend, diff heatmap, worst tiles); compose runs it automatically as a report-only gate.
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
- `scripts/quality_audit.py`: XML/render/report checks plus route-appropriate review gates.
- `scripts/validate_manifest.py`: manifest validation.
- `scripts/generate_clean_plate.py`: optional reference-capable image backend adapter. Use only after the model has selected `ai-clean-plate` and written the prompt brief.
- `scripts/prepare_clean_plate_mask.py`: optional mask/overlay preparation for image-generation prompts. It does not create a final clean plate.

`build_svg_from_manifest.py`, `embed_svg_assets.py`, `math_renderer.py`, and `api_keys.py` are internal helpers imported by the scripts above; do not run them directly.
