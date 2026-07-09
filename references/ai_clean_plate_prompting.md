# AI Clean Plate Prompting

## Purpose

FigEdit, not the image model, decides what the editable reconstruction needs.
Before invoking an image backend, inspect the source and write a structured
generation brief. The image model receives a precise edit specification, not a
generic request to remove every character.

Read `text_layer_policy.md` when the source contains formulas, code,
handwriting, low-contrast equations, UI microtext, or schematic glyphs embedded
in the background.

Read `image_backend_policy.md` before submitting the brief to an image backend.

## Generation Brief

Record these fields in `background_plan.generation_brief`.

### Task

State that the reference must be transformed into a clean visual plate for a
later editable annotation overlay. Clarify that this is not a redesign.

Frame it as a **cleanup edit of the provided source image**, not as generating a
new scene. For a photograph, say "Remove the typographic overlay and translucent
color bands from this photograph and reconstruct the pixels they covered,
keeping the photograph otherwise unchanged." For an illustration or technical
infographic, say "Remove the foreground labels, arrows, and annotation marks from
this provided illustration and reconstruct the covered background pixels while
keeping the composition, objects, color zones, and visual style unchanged." This
editing framing is what keeps a reference-capable backend focused on clean plate
repair instead of redesign.

### Preserve

List every major object or visual relationship that must remain:

- object identity and count
- left, center, and right placement
- view angle, orientation, pose, and scale
- overlaps and depth ordering
- crop at canvas edges
- background color field, texture, lighting, shadows, and grain
- source-classified background inscriptions such as formulas, code,
  handwriting, graph ticks, or schematic glyph fields only when analysis shows
  they function as integrated visual content rather than editable foreground
- intentional empty zones needed for later labels

Use concrete source descriptions. Do not say only "preserve the composition."

### Preserve Background Inscriptions

List text-like material that should remain rasterized in the generated plate
after source-specific analysis:

- faint equations in a technical backdrop
- code panes, terminal text, or data tables embedded inside an object
- low-contrast diagram glyphs and graph notations
- handwritten scrawl or formulas used as visual texture

These are not automatically preserved just because they look like formulas or
code. Preserve them only when their visual role is background atmosphere,
pictorial surface detail, or low-edit-value context. Ask the model to preserve
their visual density, placement, and source-like character while avoiding new
readable hallucinated words.

### Remove

List all content that must disappear:

- titles, captions, body copy, and labels
- leader lines, arrows, dots, brackets, legends, and markers
- logos or dates only when the reconstruction will replace them
- annotation fragments crossing visual objects
- pseudo-text or accidental glyph-like marks that are not present in the source

Do not write "remove all text" unless the source analysis finds no text-like
content worth preserving in the plate.

### Reconstruct

Describe how hidden pixels should be completed:

- continue the object's material, texture, or structure beneath removed marks
- continue the local gradient or background grain
- preserve plausible occlusion and shadows
- leave clean negative space where editable text will later be placed

Do not instruct the model to erase an object merely because text crosses it.

### Constraints

State what must not happen:

- no redesign or beautification
- no new objects
- no missing major objects
- no duplicated parts
- no changed camera angle or orientation
- no invented labels, symbols, logos, or pseudo-text
- do not erase text-like regions declared as background inscriptions
- no border, frame, watermark, or decorative typography
- no scientific or technical details invented beyond the allowed fidelity class

### Output

Specify:

- same aspect ratio and landscape/portrait orientation
- full-bleed plate with no margins
- no alpha requirement unless supported
- target fidelity: `layout-locked` or `approximate`
- clean zones required for later editable overlays

### Reject

Write candidate rejection conditions before generation. At minimum:

- residual text or annotation marks
- missing or over-smoothed background formulas, code, or glyph fields that were
  declared for preservation
- missing, duplicated, or materially altered major objects
- composition drift that breaks later label placement
- generated pseudo-text
- changed aspect ratio or added margins

## Prompt Construction

Build an English prompt with labeled sections:

```text
TASK:
...

PRESERVE EXACTLY:
- ...

PRESERVE BACKGROUND INSCRIPTIONS:
- ...

REMOVE COMPLETELY:
- ...

RECONSTRUCT:
- ...

DO NOT:
- ...

OUTPUT:
- ...
```

Image backends differ, but the brief remains model-independent. Store backend
adaptations separately from the semantic brief.

## Backend Routing

Use `image_backend_policy.md` to choose and invoke the backend. In Codex, try
`image_gen` / built-in image editing first, following the built-in invocation
protocol there: display the source image into the conversation first so it
becomes the visible edit target, then invoke with a prompt naming that
just-displayed image as the sole edit target. The reference travels through
the conversation context, not through a tool parameter, so a parameter schema
without reference options is not a fallback reason. Scriptable fallback order is Labnana GPT-Image-2, Labnana
Gemini/Nano Banana, official OpenAI/Gemini APIs, then configured command
adapters. Keep the same generation brief across providers. Record backend,
model, submitted prompt, references actually received by the job, requested and
recorded aspect ratio, output path, and failure or rejection reason.

After the brief is written, the next step is an actual image-generation call.
Do not convert the brief into a local script that paints, blurs, fills, clones,
or otherwise repairs the source pixels. Local scripts may prepare masks or copy
accepted generated files only.

## Reference Policy

Use the full source as the primary reference. Optional additional references:

- a mask overlay showing removal regions
- crops of major objects that must remain recognizable
- a color-only or texture reference when the source is compressed

Do not provide unrelated style references unless redesign is intended.

## Candidate Review

Inspect the clean plate before assembling the editable figure:

1. Compare major object count, placement, orientation, and silhouette.
2. Confirm foreground labels, leaders, and legends to be rebuilt are gone.
3. Confirm declared background inscriptions remain visually present.
4. Scan the entire plate for invented pseudo-text or duplicated labels.
5. Check former annotation crossings at high zoom.
6. Verify empty label zones and overall color balance.
7. Record accepted deviations and rejection reasons.

Only an accepted candidate may become `plate_asset_id`.
