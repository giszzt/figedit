# Chroma Regeneration

The method for turning in-scope foreground objects into clean transparent PNG
assets on the AI (`ai-clean-plate`) route: ask a reference-capable image model
to reproduce the target elements on a known solid chroma background, then key
the background out and slice the elements apart.

## The Foreground Method on the AI Route

On `ai-clean-plate` with `foreground_mode: full-extract` or `selective`, the
foreground is **generated, then keyed apart** — it is never cropped from the
original image and never passed through salient-object matting:

1. Build a reference sheet: lay the in-scope elements out on a flat chroma
   background in a known grid (their layout is authored, so their cells are
   known).
2. Ask the image model to re-print that sheet cleanly (elements reproduced
   exactly, background pure flat chroma).
3. `chroma_key.py` removes the flat background by color — exact edges,
   decontaminated holes, no guessing — and `slice_grid.py` separates each
   element by connected components.

This works because the sheet background is a single controlled color, so
keying is deterministic and precise. Salient-object matting (rembg / U2-Net)
has no role here: it would *guess* a foreground mask on a background that is
already exactly known, only adding failure modes (eaten thin structures,
ghosted rings). Do not run it, and do not improvise GrabCut/background-
difference/threshold scripts either.

Anything can be AI-regenerated — photos, people, illustrations, icons, badges,
logos, screenshots, charts, maps, composite multi-part objects (a photo inside
a flag-colored ring, a badge overlapping a disc) — with no content-category
approval gate. Quality depends on the model and prompt, so the fix for a hard
element is a sharper preserve-the-element prompt, not a refusal or a detour to
the original image.

On the **conventional** (non-AI) route, in-scope objects that need to be raster
assets are coordinate-cropped as rectangles from the source (`crop_assets.py`),
not matted; assets on flat/white/separable backgrounds need no alpha.

Routing authority stays with `element_decision_matrix.md` and
`contaminated_asset_recovery.md`. This file defines how to execute the
regeneration route once selected.

## Honesty Rules

- A regenerated asset is an approximation. Record `asset_fidelity:
  "approximate-ok"`; upgrade to `"source-close"` only after side-by-side
  review confirms close identity. Never label it `source-preserve`.
- Any foreground content is a valid regeneration target — photos, people,
  illustrations, icons, badges, logos, screenshots, charts, maps. There is no
  content-category approval gate; regeneration quality is a function of the
  model and prompt, so the fix for a hard case is a sharper, more specific
  preserve-the-element prompt, not a refusal. When exact source pixels genuinely
  carry the meaning and must not drift (a data chart read for its values, a
  compliance logo), keep that object flattened in the clean plate or, on a
  conventional route, coordinate-crop it as an opaque rectangle — do not chase
  pixel-exactness with a fragile cutout.
- Every regenerated asset records `generation_provenance` (backend, prompt
  file, reference image, output sheet). A manifest entry without provenance
  fails review.

## Inventory Completeness and Reuse

Always inventory **all** movable foreground pictorial elements — including
small instruments, ground objects, and minor marks — so the extraction scope
can be decided over a concrete list. On clean-plate routes the extraction
scope itself is set by the Foreground Depth Decision in
`background_reconstruction.md` (`full-extract` / `selective` / `flatten`).

Once extraction is chosen for a set of elements, do not cherry-pick within
it, and do not ration elements per sheet: one generation call costs the same
regardless of how many elements the sheet carries. **Default to a single
foreground sheet holding the entire inventory** — the common case is exactly
two generation calls, one clean plate plus one sheet, whether that sheet
carries 5 elements or 40. Lay them out with clear gutters and generate. Split
into a second sheet only if the model visibly fails to reproduce them all on
one — elements dropped, merged, or rendered too coarsely to read — not on a
pre-set count or pixel budget. The plate's remove list and the regeneration
inventory must mirror each other exactly: everything removed from the plate
is either rebuilt as SVG/text or regenerated as an asset, and everything kept
flattened stays out of both lists.

Repeated elements are regenerated **once**. When the same icon or mark appears
in several places in the source, put one instance on the sheet and place it
multiple times with several `image` elements referencing the same `asset_id`.
Never spend sheet slots or crops on duplicates.

## Pipeline

1. **Probe**: `python scripts/probe_palette.py source.png` selects a chroma
   color guaranteed far from the source palette. If no candidate is safe,
   probe only the target asset regions with `--region`, or fall back to
   flatten. The key color is chosen **per sheet**: if one element's own colors
   are close to the sheet's key hue, move that element to a separate sheet
   with a different key color instead of accepting a collision. The keying
   step relies on this guarantee — it removes every key-hued pixel anywhere in
   the sheet (edges, cast shadows, and background showing through enclosed
   holes), so a same-hue element would be damaged.
2. **Brief and generate**: write a prompt file per sheet (see framework
   below) and invoke a reference-capable backend per
   `references/image_backend_policy.md`. The source image must be attached as
   the reference / edit target; a text-only prompt cannot reproduce
   source-specific elements.
3. **Key**: `python scripts/chroma_key.py --input sheet_raw.png --out
   sheet.png --color "<probe result>" --scale 2`. Non-empty `warnings` in the
   report is a review trigger.
4. **Slice** (grid sheets only): `python scripts/slice_grid.py sheet.png
   out_dir --pad 12 --prefix ic`. Inspect the contact sheet: every element
   whole, none merged, none missing.
5. **Review**: compare each keyed element against its source counterpart side
   by side. Apply the rejection criteria below per element; regenerate only
   the rejected ones.
6. **Record**: enter accepted assets in the manifest with `source_mode:
   "external"` pointing at the keyed PNG, `decision: "regenerate-chroma"`,
   fidelity and provenance fields, and normal target placement from the
   source-image bbox of the original element.

## Job Forms

### Single-element re-print

For one large complex asset (an illustration with shadows, a device drawing
entangled with the background). Ask the model to reproduce exactly that
element, alone, filling most of the canvas, on the chroma background. Key the
result and place it directly; no slicing.

**Reference granularity rule**: for single or few-element jobs, attach a
tight region crop of the element (contamination included) as the reference,
not the full source image. With the full figure as reference, models tend to
reproduce the whole layout in miniature instead of the one element — a
repeatedly observed failure. The full source is the right reference only for
the clean plate and for grid sheets covering elements spread across the
figure.

### Grid batch regeneration

For many elements (icons, markers, pictograms, medallions). One generation
call reproduces all of them laid out on the chroma background with clear
gutters (a regular grid is ideal but any layout with separation works —
slicing is connected-component based). Put the whole inventory on one sheet;
do not cap the count. Split into a second sheet only if a single sheet visibly
fails — elements dropped, merged, or too coarse to read.

### Crop transfer

For a single element that needs to be a standalone transparent asset: crop
the element coarsely from the source (dirt and all), then ask the model to
reproduce **the content of this crop** on the chroma background, unchanged.
Because the reference is already isolated, drift risk is the lowest of the
regeneration forms — this is the preferred form for a lone element.

## Prompt Framework

Every sheet prompt is written to a file (recorded in provenance) and contains
these blocks, adapted to the case — never a fixed boilerplate:

**Edit target.** State that the attached source image is the sole reference
and edit target, and identify exactly which element(s) to reproduce, by
position and description ("the astronaut figure at the upper right", "the
five small tower icons along the bottom").

**Reproduction constraints.** Same silhouette, orientation, proportions,
colors, internal details, and rendering style as the source. No
reinterpretation, no style transfer, no added parts, no simplification.

**Background.** The entire background must be exactly the flat color
`#xxxxxx`, with no gradient, texture, shadow cast onto it, or vignette.
Element shadows that belong to the asset itself must be kept attached to the
element, not spread across the background. **Enclosed holes and gaps inside
elements must also show the pure background color** (a ring's center, the
space between tripod legs, negative space in letterforms) — this is what
makes interior transparency possible after keying.

**Edge quality.** This block decides whether the keyed edges are clean;
write it explicitly every time. Ask for crisp, sharply defined element edges
against the background: no glow, no feathered halo, no outer stroke, and no
die-cut sticker border unless the source element actually has one. The
pilot's most common defect was the model adding white sticker outlines that
the source did not have.

**Exclusions.** Do not include surrounding labels, leader lines, callout
dots, arrows, neighboring objects, or any text that is not physically part of
the element. Do not add captions, watermarks, or invented text.

**Layout (grid sheets).** Elements arranged with clear gaps, none touching or
overlapping, each fully inside the canvas, no grid lines drawn.

**Reject-if.** State the rejection criteria in the prompt so the model
optimizes for them, and apply them yourself on review.

## Rejection Criteria

Reject a candidate element when:

- silhouette, orientation, or proportions differ visibly from the source
- colors or internal details are reinterpreted rather than reproduced
- parts are invented, dropped, or duplicated
- labels, arrows, pseudo-text, or neighbor fragments are baked in
- the background is not flat key color (gradients and cast shadows break keying)
- keying leaves fringe or eats content (see `chroma_key.py` report warnings)
- elements on a grid sheet touch, overlap, or run off the canvas

Rejection is per element: keep the good ones, regenerate the rest in a new
sheet. Two failed regeneration rounds for the same element usually mean the
prompt is underspecified, not that regeneration is wrong — tighten the
preserve-the-element wording (name the exact parts, colors, and layout to
reproduce) and retry as a single-element crop transfer. If it still drifts,
fall back to crop-with-documented-dirt or leave the element flattened in the
clean plate.

One frequent partial defect does not require rejection: models often add
labels or captions to the sheet despite the prohibition. If the elements
themselves are clean and separated, keep the sheet and discard the label
components at slicing time (they are rebuilt as editable SVG text anyway) —
`slice_grid.py` output makes them easy to identify on the contact sheet, or
slice by region. Reject only when labels overlap the elements.

## Manifest Entry Example

```json
{
  "id": "asset-astronaut",
  "file": "work/generated/astronaut.png",
  "source_mode": "external",
  "decision": "regenerate-chroma",
  "asset_fidelity": "approximate-ok",
  "x": 1430, "y": 260, "w": 210, "h": 300,
  "source_region": { "x": 1430, "y": 260, "w": 210, "h": 300 },
  "kind": "pictorial-illustration",
  "decision_reason": "figure embedded in continuous star field; crop cannot separate cleanly",
  "generation_provenance": {
    "backend": "labnana-gpt-image-2",
    "prompt_file": "work/prompts/astronaut-sheet.txt",
    "references": ["work/assets/source.png"],
    "sheet": "work/generated/sheet_01_raw.png",
    "chroma_color": "#ff00ff"
  },
  "review_status": "verified"
}
```

Placement (`x/y/w/h`) always comes from the element's bbox in the source
image, measured in source pixels, regardless of the sheet layout.
