# Text Layer Policy

## Purpose

Classify text-like content by visual role and editability value. Do not erase
all characters from a complex clean plate, and do not preserve all formulas,
code, or background-looking words. Decide what to remove, preserve, or rebuild
from how the content functions in the source.

## Text Classes

### Editable Foreground

Remove from the background plate and rebuild as editable text, math, or shapes:

- titles and subtitles
- node labels, callouts, captions, and legends
- leader-line labels and marker labels
- axis labels or table text intended to remain readable and editable
- formulas that the user will likely edit as content
- code snippets, UI labels, or equation blocks that are primary explanatory
  content rather than visual texture

### Integrated Background Inscriptions

Preserve inside the plate when they are part of the scene, texture, or visual
semantics:

- faint formulas or equations written into a chalkboard, glass, wall, sky,
  hologram, or technical backdrop
- code windows, terminal-like snippets, and dense microtext used as a visual
  object
- schematic glyphs, diagram fragments, graph ticks, and mathematical scrawl
  that create domain identity
- low-contrast or partially occluded writing that is not a primary label
- marks whose exact editability is less important than preserving visual density

These inscriptions may remain rasterized. They do not need to become editable
unless the user explicitly asks or the figure's meaning depends on editing them.

### Background-Looking But Editable

Some text is visually embedded but still should be rebuilt:

- a large readable formula block that communicates the figure's main method
- code shown as the central data or algorithm rather than atmosphere
- labels printed inside a diagram object when they define the object
- table values, chart labels, or map names that support interpretation
- any inscription the user is likely to update independently

For these cases, remove it from the plate only if the area can be repaired
cleanly, then rebuild it as editable text or math. If removal would damage the
visual object, keep a rasterized copy and add an editable overlay only when
necessary.

### Suppressed Artifacts

Remove or avoid generating:

- pseudo-text invented by the model
- garbled foreground labels where the source label will be rebuilt
- duplicated labels, watermark-like hallucinations, and random letter clusters
- source OCR noise outside visible text regions

## Decision Cues

Classify each text-like region with these cues:

- **Reading role**: primary explanation, label, legend, or data value implies
  editable foreground.
- **Visual integration**: low contrast, partial occlusion, perspective,
  lighting, blur, glow, or being painted onto an object implies plate
  preservation.
- **Edit value**: likely user edits imply rebuild; atmospheric density implies
  preserve.
- **Exactness**: exact formula/code/data matters implies rebuild or
  source-preserved crop; approximate technical texture may stay rasterized.
- **Layer relation**: text connected to leaders, markers, nodes, axes, or a
  legend is usually foreground even when the background is complex.
- **Repair risk**: if removing embedded text would damage an important object,
  preserve it and document the tradeoff.

If unsure, choose the option that loses less source meaning: preserve visual
density for atmospheric marks; rebuild editable content for primary readable
information.

## Prompt Requirements For AI Clean Plates

Every AI clean plate prompt for text-dense sources must include source-specific
decisions, not a fixed rule:

- foreground text to remove and rebuild
- integrated background inscriptions to preserve
- artifact text to suppress
- rejection criteria for both missing preserved inscriptions and invented
  pseudo-text

Use language like:

```text
PRESERVE BACKGROUND INSCRIPTIONS:
- Keep only the source-classified background inscriptions, such as faint
  equations, code fragments, graph ticks, or schematic glyphs that function as
  background texture or pictorial detail. They may remain rasterized and do not
  need to be perfectly editable, but their density, placement, and visual role
  should stay close to the reference.

REMOVE FOREGROUND TEXT:
- Remove the main title, node labels, callout labels, legends, and any labels
  that will be rebuilt as editable overlays.

DO NOT:
- Do not remove the ambient formulas or code-like texture that was explicitly
  classified for preservation.
- Do not invent new readable words or random pseudo-text.
```

## Manifest Fields

Record the decision in `background_plan.text_layer_policy`:

```json
{
  "editable_foreground": ["title", "node labels", "legend"],
  "preserve_in_plate": ["faint formulas at right", "code panel inside globe"],
  "suppress_or_reconstruct": ["model-invented pseudo-text", "garbled duplicate labels"],
  "ambiguous_handling": "preserve in plate unless it conflicts with editable overlays"
}
```

The same policy should be reflected in `generation_brief.preserve`,
`generation_brief.remove`, `generation_brief.constraints`, and
`generation_brief.reject_if`.
