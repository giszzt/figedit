# Background Reconstruction

Use this reference only when a continuous background field may not be faithfully recoverable by the normal FigEdit hybrid route.

This file is the single authoritative definition of the Background Gate. Other documents (SKILL.md, taxonomy, workflow, quality checklist) summarize or check against it; when wording differs, this file wins, and criteria changes are made here only.

## First Principle

Background handling is not a separate reconstruction workflow. It is one extra gate inside FigEdit:

**Can clean source crops plus simple deterministic SVG primitives faithfully reconstruct the background field without inventing scene pixels?**

If yes, use the conventional FigEdit route and do not add `background_plan`.

If no, use `ai-clean-plate`.

The gate is about mechanical recoverability, not visual density, genre, or how many objects the image contains. A background is mechanically recoverable only when it can be rebuilt from measured geometry, flat fills, regular gradients, repeatable patterns, or clean source crops. If the plan requires painting a plausible scene, texture, or illustration, it is not mechanically recoverable.

## User Route Directive

The gate answers the default question for figures where the user has not chosen a route. An explicit route request in the user's own words overrides the gate, in both directions:

- **User asks for the AI route on a figure the gate would route conventionally** ("走清版路线", "regenerate the background", "don't crop it, generate it clean"). Honor it. Add `background_plan`, run the full clean-plate workflow, and record `route_decision.source: "user-directive"` with the user's wording in `route_decision.reason`. This is a legitimate choice, not an error to argue away: coordinate crops can carry compression artifacts, contaminated edges, or tight-boundary losses that a regenerated plate and regenerated assets avoid. All clean-plate acceptance standards still apply — the directive changes the route, never the quality bar.
- **User insists on the conventional route for a figure the gate would send to `ai-clean-plate`**. Honor that too. State the expected fidelity cost in one or two sentences (approximate SVG scenery or visible crop patchwork), then proceed as directed and record `route_decision.source: "user-directive"`.

A directive must come from the user's own words in this task. Do not infer one from the figure's genre, and do not use this section to skip the gate when the user has not spoken. When the gate decides, record `route_decision.source: "background-gate"`.

## Conventional Route

Use the conventional route for backgrounds that can be rebuilt by ordinary FigEdit methods without visual invention:

- flat fills
- simple single-zone gradients with measurable endpoints
- regular geometric regions
- clean screenshot, chart, map, or photo crops
- white or light diagram backgrounds
- diagrams with many icons but separable backgrounds and assets

The manifest has no `background_plan`. Treat the background as ordinary shapes and assets. Continue to crop source-specific visuals, retype text, rebuild formulas, and redraw structure by the normal element gates.

## AI Clean Plate Route

Use `ai-clean-plate` when the background is a continuous visual field and the foreground is embedded in it, so removing text, marks, or foreground assets reveals unknown pixels that clean crops and simple SVG primitives cannot reproduce.

Common examples:

- photographs under titles or labels
- illustrated, painterly, rendered, or collage fields
- irregular or multi-zone gradients, especially when they represent a scene rather than a plain style fill
- layered visual fields such as sky, space, water, land, terrain, atmosphere, clouds, glow, bokeh, smoke, lighting, and painterly or rendered surfaces
- magazine covers, posters, and social cards with typography over imagery
- technical scenes where labels, leaders, or legends cross a continuous visual field

Strong AI-route signals:

- the same continuous field runs behind many labels or icons
- labels, arrows, leader lines, callout dots, legend blocks, or icon shadows overlap the field
- removing those foreground elements would require reconstructing hidden pixels
- foreground assets are visually entangled with glows, shadows, transparency, or background texture
- the conventional plan would say "redraw the background as SVG" but cannot describe it as a small set of measured primitives

When these signals appear, select `ai-clean-plate` early. Do not downgrade because a determined illustrator could approximate the scene in SVG.

This route creates a clean non-editable visual bottom layer. It should remove foreground annotations that will be rebuilt, while preserving visual content that belongs to the background.

## Foreground Depth Decision

Once the gate selects `ai-clean-plate`, there are two overlay strategies, and
they require **different plates**, so this decision must be made before plate
generation:

- **full-extract**: every movable foreground pictorial object is regenerated
  as an independent transparent asset (`chroma_regeneration.md`) and layered
  over a plate that has them all removed. Maximum editability; each object can
  be moved, replaced, or reused. Costs extra generation sheets and review.
- **flatten**: all pictorial objects stay baked into the plate; only text,
  formulas, and simple SVG marks are editable. One plate call, fast and cheap.
- **selective**: user-named objects are extracted, the rest stay flattened.
  The plate's remove list contains exactly the extracted subset.

**This is a hard checkpoint, not a judgment call.** Asking the user is the
default action. The only condition that skips the question is an explicit
preference in the user's own words — "我要能拖动/替换里面的元素" implies
full-extract, "只改文字/翻译一下" implies flatten, naming specific objects
implies selective. What the figure looks like (many objects, fiddly edges,
entangled boundaries) may shape which option you *recommend*; it never
authorizes choosing for the user. An agent that selects a mode from its own
reading of the figure while the user is available has violated this gate.

Procedure:

1. Build the foreground inventory first (all movable pictorial objects), so
   the choice is made over a concrete list, not an abstraction.
2. Scan the user's request for explicit depth wording. Found: record it and
   proceed. Not found: **stop and ask**, before any generation call.
3. Present the options with what each buys and costs, over the concrete
   inventory. A serviceable framing (adapt names and detail to the user):

   - **完全打散 (full-extract)** — every listed object becomes an
     independent movable/replaceable asset. Highest editability; costs one
     plate + one foreground-sheet generation (usually a single sheet for the
     whole inventory) + per-element review; slowest.
   - **指定提取 (selective)** — you name the objects worth extracting, the
     rest stay in the background. Middle cost; good when only a few objects
     will ever move.
   - **仅文字可编辑 (flatten)** — objects stay baked into the clean plate;
     text, formulas, and annotations become editable. One plate call;
     fastest and cheapest.

   Attach your recommendation and the reason, and note that the choice fixes
   the plate: switching later means regenerating it.
4. Record the choice in `background_plan.foreground_mode`
   (`full-extract` | `selective` | `flatten`) and its origin in
   `background_plan.foreground_mode_source`
   (`user-choice` | `explicit-request` | `auto-default`) before writing the
   plate brief. The plate remove list and the regeneration inventory must
   both match the recorded mode.

`auto-default` (flatten, the cheaper lower-risk deliverable) is legitimate
only when no user can respond — an unattended batch run. In an interactive
session it is a gate violation, and the report must say that full-extract
would require a new plate.

## Foreground Policy After AI Clean Plate

Do not treat AI clean plate as permission to recrop every object. After the plate is accepted, restore only what needs to be editable or source-exact.

Default overlay:

- editable titles, labels, captions, legends, and ordinary text
- `math` elements for formulas
- simple leader lines, arrows, dots, frames, rules, and markers

Crop a source asset over the plate only when all three conditions hold:

1. exact source identity matters
2. independent movement, replacement, or editing is useful
3. the crop can be clean, without old text, callouts, halos, seams, or a large rectangular patch of original background

Under `full-extract` and `selective`, every in-scope object is obtained by
`regenerate-chroma` (`chroma_regeneration.md`): reproduced on a chroma sheet
and keyed apart. This handles composite, entangled, and plain pictorial
objects alike. Do not crop these objects from the original image and do not
run salient-object matting on them — the whole point of this route is that the
hidden pixels behind the foreground are unrecoverable from the source, so the
foreground is rebuilt by the model, not extracted from it. No rectangle-crop
attempts, no improvised local matting. Scope follows the Foreground Depth Decision: the whole inventory under
`full-extract` (one regeneration sheet carries many elements at no extra
cost), exactly the user-named subset under `selective`, none under `flatten`.
A clean flattened plate is still better than a visibly patched
reconstruction — but a regenerated transparent asset is not a patch.

## Background Text-Like Content

Do not blindly remove every formula, code fragment, handwriting mark, glyph, or faint label. Classify text-like content by role:

- **Foreground to rebuild**: titles, labels, captions, legends, callouts, explanatory text, primary formulas, readable code panels, and annotations that users may edit.
- **Background to preserve**: faint formulas, code texture, graph ticks, schematic glyphs, handwriting, or microtext that functions as visual atmosphere, surface detail, or low-edit-value context.

The same visual token can be foreground in one image and background in another. Decide from reading role, contrast, layering, edit value, and whether removing it would damage the visual identity.

## Prompt Brief

When `ai-clean-plate` is selected, write a dynamic brief before invoking any backend. Read `ai_clean_plate_prompting.md`.

The brief must specify:

- what to preserve
- what to remove
- what hidden pixels to reconstruct
- which text-like background inscriptions, if any, should remain
- what would cause candidate rejection

Do not delegate this classification to the image model.

## Minimal Manifest Requirements

Conventional route:

- no `background_plan`

AI clean plate route:

- `background_plan.strategy: "ai-clean-plate"`
- route reason explaining why crop + SVG cannot faithfully reconstruct the background
- accepted clean plate asset aligned to the canvas
- generation provenance for the accepted plate
- candidate review showing why the plate was accepted

`recognition_summary`, `asset_decision_policy`, and detailed text/asset policy objects are optional. Use them when they clarify a difficult case, not as required ceremony.

## Failure Conditions

Reject or repair the output if:

- the untouched source image is used as the clean plate while old foreground text remains visible
- local blur, clone, mask-fill, or OpenCV/PIL inpaint is presented as an AI clean plate
- large rectangular source crops cover the generated plate
- source crops contain old labels, leaders, or annotation residue that should have been rebuilt
- editable text or simple marks were left baked into a raster asset without justification
- the clean plate changes major object count, orientation, placement, or visual identity beyond the declared tolerance
- the final result looks like a collage of patches instead of one coherent background plus editable foreground

If no acceptable clean plate can be generated, stop and report a blocker rather than downgrading silently.
