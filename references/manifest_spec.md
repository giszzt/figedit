# Manifest Specification

The manifest records the reconstruction plan and enables reproducible updates.

## Required Sections

- `project`: project slug
- `source_image`: original image path
- `canvas`: source dimensions and background
- `classification`: figure type and selected mode
- `panels`: major layout regions
- `assets`: cropped raster assets
- `elements`: editable SVG elements and embedded asset placements

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

### Element

```json
{
  "type": "text",
  "id": "title-main",
  "decision": "retype",
  "x": 900,
  "y": 60,
  "text": "Figure Title",
  "font_size": 32,
  "font_weight": "700"
}
```

## Element Types

Supported by the helper script:

- `rect`
- `text`
- `line`
- `path`
- `circle`
- `ellipse`
- `polygon`
- `polyline`
- `image`

Additional types may be hand-authored in SVG.

## Asset Fidelity Fields

For every cropped visual asset, include fidelity metadata when possible:

```json
{
  "asset_fidelity": "source-preserve",
  "decision_reason": "custom pictorial icon; preserve original appearance",
  "background_handling": "preserve-card-background-pixels",
  "crop_status": "verified"
}
```

Recommended values:

- `asset_fidelity`: `source-preserve`, `approximate-ok`, `semantic-only`
- `decision_reason`: brief explanation for `crop`, `redraw`, or `semantic-redraw`
- `background_handling`: `transparent`, `preserve-background`, `remove-background`, `mask`, `uncertain`
- `crop_status`: `pending`, `verified`, `needs-padding`, `wrong-region`, `background-issue`

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

If a redrawn object is pictorial or source-specific, the decision should be considered suspect and reviewed.
