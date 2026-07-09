# Manifest Specification

The manifest records the reconstruction plan and enables reproducible updates.

## Required Sections

- `project`: project slug
- `source_image`: original image path
- `canvas`: source dimensions and background
- `classification`: figure type and selected mode
- `panels`: major layout regions
- `assets`: cropped or generated raster assets
- `elements`: editable SVG elements and embedded asset placements

Conventional FigEdit manifests do not require `background_plan`. Add `background_plan` when the Background Gate selects `ai-clean-plate`, or when the user explicitly requests the AI route for a figure the gate would route conventionally.

## Coordinate System

Use source image pixel coordinates.

```json
{ "x": 120, "y": 80, "w": 300, "h": 180 }
```

## Recommended Fields

### Classification

```json
{
  "layout_topology": "panel-composite",
  "complexity": "high",
  "style_type": "benchmark-color",
  "reconstruction_mode": "C+B",
  "reconstruction_intent": "editable-layout"
}
```

Use `reconstruction_mode: "E-ai"` only when `background_plan.strategy` is `ai-clean-plate`.

### Panel

```json
{
  "id": "panel-left",
  "label": "Data Source",
  "x": 8,
  "y": 12,
  "w": 565,
  "h": 992,
  "strategy": "panel-wise rebuild"
}
```

### Asset

```json
{
  "id": "asset-route-map",
  "file": "assets/route_map.png",
  "source_region": { "x": 70, "y": 171, "w": 270, "h": 362 },
  "x": 70,
  "y": 171,
  "w": 270,
  "h": 362,
  "pad": 4,
  "panel_id": "panel-left",
  "kind": "screenshot",
  "decision": "crop"
}
```

`pad` may be negative to inset the crop inside the region — the standard fix
for flush-mounted assets whose eyeballed box would otherwise catch slivers of
a neighboring border (see `asset_extraction.md`).

For generated background plates:

```json
{
  "id": "asset-clean-plate",
  "file": "work/generated/clean-plate.png",
  "source_mode": "external",
  "x": 0,
  "y": 0,
  "w": 1920,
  "h": 1080,
  "kind": "background-plate",
  "decision": "generate-replacement",
  "crop_status": "verified"
}
```

### Element

```json
{
  "type": "text",
  "id": "title-main",
  "decision": "retype",
  "x": 900,
  "y": 60,
  "source_region": { "x": 895, "y": 42, "w": 260, "h": 38 },
  "text": "Figure Title",
  "font_size": 32,
  "font_weight": "700",
  "review_status": "verified"
}
```

### Math Element

```json
{
  "type": "math",
  "id": "eq-loss",
  "decision": "reconstruct-math",
  "x": 420,
  "y": 260,
  "w": 220,
  "h": 48,
  "source_region": { "x": 418, "y": 255, "w": 224, "h": 52 },
  "latex": "L = \\sum_i \\ell(y_i, f(x_i))",
  "font_size": 22,
  "layout_lock": "source-slot",
  "review_status": "verified"
}
```

For ordinary sparse figures, `source_region`, `w`, `h`, `baseline_y`, and
`layout_lock` are optional. For dense text/formula figures, use them whenever a
label or equation must fit a tight visual slot. They make it clear that
editability and placement are both required.

## Element Types

Supported by the helper scripts:

- `rect`
- `text`
- `math`
- `line`
- `path`
- `circle`
- `ellipse`
- `polygon`
- `polyline`
- `image`

Additional types may be hand-authored in SVG when the compose scripts support them.

## Asset Fidelity Fields

For every cropped visual asset, include fidelity metadata when possible:

```json
{
  "asset_fidelity": "source-preserve",
  "decision_reason": "custom pictorial icon; preserve original appearance",
  "background_handling": "tight-crop",
  "crop_status": "verified"
}
```

Recommended values:

- `asset_fidelity`: `source-preserve`, `source-close`, `approximate-ok`, `semantic-only`
- `decision_reason`: brief explanation for `crop`, `redraw`, `flatten`, `regenerate-chroma`, or `generate-replacement`

Assets produced by chroma regeneration use `source_mode: "external"`,
`decision: "regenerate-chroma"`, and a `generation_provenance` object; the
full entry shape and workflow are in `chroma_regeneration.md`.

Conventional-route assets are coordinate-cropped rectangles from the source
(`scripts/crop_assets.py` reads each asset's `source_region`); they carry
`decision: "crop"`.
- `background_handling`: `tight-crop`, `transparent`, `preserve-background`, `remove-background`, `mask`, `full-canvas`, `uncertain`
- `crop_status`: `pending`, `verified`, `needs-padding`, `wrong-region`, `background-issue`, `dirty-residue`
- `text_policy`: `extract-editable`, `preserve-raster`, `allow-embedded-text`, `review`

## Decision Audit

The manifest should make inappropriate redraws easy to find. For each visual object that is redrawn instead of cropped, include a reason:

```json
{
  "type": "path",
  "id": "simple-plus-marker",
  "decision": "redraw",
  "decision_reason": "generic primitive marker; not source-specific"
}
```

If a redrawn object is pictorial, source-specific, brand-specific, evidence-bearing, or visually distinctive, the decision should be considered suspect and reviewed.

## Optional Evidence Fields

These fields are useful on difficult cases but are not required for ordinary tasks:

- `recognition_summary`: OCR/CV/style diagnostics inspected and how they informed the manifest
- `asset_decision_policy`: short summary of which objects were cropped, redrawn, flattened, or generated
- `editability_targets`: minimum expected editable text/structure/assets for a difficult reconstruction
- `layout_fidelity_targets`: dense text/formula regions that must be visually checked in SVG and PPTX
- `pptx_visual_review`: summary of the PPTX render/open review for tight text and formula layout

Do not add these fields as ceremony. Use them when they prevent ambiguity.

## Background Plan

`background_plan` exists only for `ai-clean-plate`.

Conventional route:

```json
{
  "classification": {
    "reconstruction_mode": "C+B"
  }
}
```

No `background_plan` is present.

AI clean-plate route:

```json
{
  "background_plan": {
    "strategy": "ai-clean-plate",
    "route_decision": {
      "reason": "Foreground labels sit on a continuous illustrated field; crop + SVG cannot reconstruct the hidden pixels.",
      "crop_svg_recoverable": false
    },
    "plate_asset_id": "asset-clean-plate",
    "generation_provenance": {
      "role": "primary-clean-plate",
      "backend": "Codex Image Gen",
      "fallback_policy": "Codex Image Gen -> Labnana GPT-Image-2 -> Labnana Gemini/Nano Banana -> official provider API -> configured command",
      "prompt_file": "work/clean-plate-prompt.txt",
      "references": ["work/assets/source.png"],
      "output": "work/generated/clean-plate.png"
    },
    "candidate_review": {
      "accepted": true,
      "checks": {
        "foreground_text_removed": true,
        "major_visual_identity_preserved": true,
        "aspect_ratio_and_alignment_usable": true
      },
      "notes": "Brief visual review of the accepted candidate."
    },
    "review_status": "verified"
  }
}
```

Minimum requirements:

- `strategy` is exactly `ai-clean-plate`
- `route_decision.reason` states why crop + SVG cannot faithfully reconstruct the background, or quotes the user's route request
- `route_decision.source` is `background-gate` or `user-directive` (user's own words chose the route)
- `foreground_mode` is `full-extract`, `selective`, or `flatten`, and `foreground_mode_source` is `user-choice`, `explicit-request` (quote the user's wording in `route_decision`), or `auto-default` (unattended runs only) — see the Foreground Depth Decision in `background_reconstruction.md`
- `plate_asset_id` points to a full-canvas `background-plate` asset
- `generation_provenance` records the actual generation path and output
- `candidate_review.accepted` is true

Detailed `text_layer_policy`, `foreground_asset_policy`, and `generation_brief` objects are optional. Store them when useful, but do not require them for every clean-plate manifest.

## AI Clean-Plate Foreground Assets

After a clean plate is accepted, source-specific assets are still decided by the normal Raster Asset Gate.

Crop an asset over the plate only when:

- exact identity matters
- independent movement or replacement is useful
- the crop is clean

Do not crop large rectangular patches of original background over the clean plate. Do not crop old labels, leaders, or callout fragments back into the final package.
