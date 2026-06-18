# Asset Preservation Policy

## Purpose

This policy prevents over-vectorization. Many raster figures contain source-specific icons, pictograms, screenshots, maps, thumbnails, logos, or custom illustrations. These objects should usually be preserved by accurate cropping rather than replaced with newly drawn SVG approximations.

The default for non-structural visual objects is:

> **Crop first. Redraw only when the object is clearly generic, structurally simple, and safe to approximate.**

## Definitions

### Structural elements

Elements whose main function is layout, grouping, or relationship expression:

- panels
- cards
- frames
- rules and separators
- grid lines
- table borders
- arrows and connector lines
- simple flow indicators
- background blocks

Structural elements should normally be redrawn as editable SVG.

### Visual assets

Elements whose main function is pictorial identity, visual evidence, iconographic meaning, or source-specific appearance:

- pictorial icons
- custom icons
- UI screenshots
- maps and remote-sensing imagery
- photos and thumbnails
- logos and marks
- inserted illustrations
- hand-drawn characters or objects
- detailed chart screenshots
- product images
- collage images
- model outputs or example images

Visual assets should normally be cropped from the source image and embedded with `<image>`.

## Default Decision Rule

Use this rule for every non-text visual object:

1. If the element is structural, redraw it.
2. If the element is pictorial, source-specific, or visually distinctive, crop it.
3. If the element is a simple generic primitive, redraw it.
4. If uncertain, crop it.

## Redraw Eligibility Test

A visual object may be redrawn only if all of the following are true:

- It can be recreated with a small number of basic SVG primitives.
- Its exact silhouette, texture, shading, or icon style is not important.
- It is not a brand/logo/source-specific pictogram.
- It is not a screenshot, map, photo, thumbnail, or model output.
- It does not contain embedded raster detail.
- Replacing it with a clean SVG equivalent will not change the perceived source figure.

If any condition fails, crop the object instead.

## Strong Crop Triggers

Always prefer cropping when an element has any of these properties:

- custom silhouette or non-generic drawing style
- hand-drawn or paper-like texture
- realistic shading, gradient, blur, grain, or shadow
- embedded mini image, thumbnail, screenshot, or map
- brand mark, application icon, institutional logo, or model logo
- pictorial object such as clothing, person, drone, database illustration, camera, folder, city model, mountain model, vehicle, chart screenshot, phone UI, route map, or face/avatar
- visual identity that would be degraded by approximation
- repeated source image asset whose consistency matters across the figure

## Weak Redraw Candidates

These may be redrawn when doing so improves editability:

- plain circles, squares, rectangles, rounded rectangles
- simple plus, minus, check, cross, bullet, dot
- simple line arrows
- plain dashed boxes
- simple table/grid structures
- basic geometric placeholder icons used only as structural markers

## Composite Elements

Many visual regions contain both editable and non-editable subparts.

Recommended split:

- crop pictorial icon or screenshot
- retype nearby label
- redraw surrounding card or panel
- redraw connector lines and arrows

Example:

- A rounded gray tile containing a custom cloud icon and a label should usually become:
  - SVG rounded tile
  - cropped cloud icon asset
  - editable text label

## Integrated Text in Assets

If text is integrated into a small icon, screenshot, or logo and is not intended for editing, keep it inside the cropped asset.

If the text functions as a readable label or annotation, retype it separately and crop only the pictorial component.

## Background Handling

When cropping a visual asset:

- preserve the original background if it is visually part of the asset
- remove the background only if this can be done cleanly
- otherwise crop with slight surrounding background and align it onto the recreated panel
- record the handling in the manifest

## Asset Inventory Requirement

Before SVG authoring, create an asset inventory for all pictorial objects. Each entry should include:

- asset ID
- element type
- source bounding box
- target bounding box
- decision reason
- crop padding
- background handling
- verification status

## Prohibited Behavior

Do not:

- replace source-specific icons with generic invented SVG icons
- redraw complex pictorial assets merely because they look simple at first glance
- omit small pictorial objects without documenting the omission
- simplify custom icons when visual fidelity is a user priority
- redraw logos unless the user explicitly requests logo vectorization and licensing permits it
- crop labels together with icons when labels should remain editable, unless the text is unreadable or integrated into the icon

## Review Questions

Before finalizing an element decision, ask:

1. Is this object part of the diagram structure or a visual source asset?
2. Would a user expect this object to look like the original?
3. Would redrawing it create a visibly different or generic substitute?
4. Can it be accurately cropped with acceptable padding?
5. Does the label need to be editable separately?

If the answer favors original visual fidelity, crop it.
