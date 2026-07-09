# Contaminated Asset Recovery

## Definition

A contaminated asset is a useful visual object whose source pixels include
unwanted material such as:

- labels or captions printed across the object
- leader lines, arrowheads, dots, or callout markers
- neighboring objects or panel boundaries
- partial occlusion
- background color trapped inside thin structures
- glow, shadow, reflection, smoke, or transparency tied to the scene

Direct cropping preserves the contamination. Naive background removal often
damages the object.

## Recovery Gate

### Crop Clean

Use when the object has a complete boundary and the crop contains no unwanted
overlay. Preserve background pixels only when they are part of the asset.

### Transparent Cutout

When a contaminated object must become a movable transparent asset,
regeneration (AI-Assisted Cleanup, below) is the method: reproduce the object
on a flat chroma sheet and key it apart (`chroma_regeneration.md`). There is
no salient-object matting step — cutting the object out of its natural,
contaminated source background with rembg / U2-Net or hand-rolled
GrabCut/difference/threshold scripts is exactly what produced the clipped,
ghosted assets this gate exists to avoid. If the object sits on a flat or
separable background and simply needs a rectangle, coordinate-crop it instead
(`crop_assets.py`); no alpha is needed.

### AI-Assisted Cleanup

Use when annotations cross an object that should remain movable and exact
cropping would preserve the contamination.

Preferred order:

1. Try a cleaner source crop if the object boundary allows it.
2. If the object does not need movement, flatten it in the clean plate.
3. If movement matters, regenerate the object on a solid chroma background and
   key it out (`chroma_regeneration.md`). This is the standard execution path
   for generation-based recovery: it produces a clean transparent asset with
   no halo, no residue, and no manual matting.

Do not use clone painting or local inpainting as a final asset recovery path.
Preserve the object's silhouette and internal geometry in the generation brief.

### Flatten Background

Use when independent editing is not valuable enough to justify a fragile
cutout. This is often best for:

- objects with hundreds of fine intersections
- large transparent or reflective surfaces
- strongly integrated shadows and atmospheric effects
- elements partly hidden behind multiple labels
- decorative objects that never need to move

Remove editable labels and leaders from the plate, but leave the object itself.

### Generate Replacement

Use only when:

- the original cannot be cleaned adequately
- the candidate can be independently reviewed

Record the generated origin separately from the requested fidelity target.
Generated assets must never be misreported as untouched source crops.

For tasks targeting stricter fidelity, generation is still eligible. Expand the
preserve constraints and reject candidates that alter identity, geometry,
values, boundaries, or source-specific relationships beyond the task tolerance.

## Whole-Plate Alternative

Before restoring many contaminated assets independently, ask whether the user
actually needs them to move. If most large visuals can remain fixed, use one AI
clean plate and rebuild only the annotation layer. This is usually superior
when:

- five or more pictorial objects are crossed by annotations
- thin structures make alpha extraction fragile
- shadows and glows bind objects to the background
- restoring every object would create visible seams
- editability is mainly needed for text and callouts

## Generation Targets

### Clean Asset

Generate the object alone on a solid chroma background chosen by
`probe_palette.py`, then extract it with `chroma_key.py` (full workflow and
prompt framework in `chroma_regeneration.md`). Use a tight source crop as
reference. Ask for:

- the same view and orientation
- the same approximate proportions and lighting
- an exactly flat key-color background, no cast shadows onto it
- no labels, lines, arrows, dots, logos, or text
- no extra parts

For many small contaminated objects, batch them into one grid sheet and slice
with `slice_grid.py` instead of generating one by one.

### Repair Patch

Generate only the damaged region plus context. Composite it into a
source-locked crop. This is safer than regenerating the entire object when
shape fidelity matters.

### Background Plate

Generate a full plate only when coordinate drift is acceptable. For
coordinate-sensitive work, generate patches and preserve unaffected source
pixels.

## Manifest Requirements

Record:

- `contamination`: types of unwanted overlap
- `separation_strategy`
- `edit_value`: high, medium, or low
- `fidelity_requirement`
- `generation_provenance` when used
- `review_status`

Document why flattening or generation was chosen over extraction.

## Rejection Conditions

Reject a candidate when:

- silhouette or orientation changes materially
- missing parts are invented
- labels or pseudo-text appear
- scientific or technical structure changes
- highlights and shadows conflict with the final background
- the edge still shows a source-colored halo
- the candidate is cleaner but no longer represents the source object
