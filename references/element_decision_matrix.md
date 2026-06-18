# Element Decision Matrix

## Decision Types

Use one of these decisions for every significant element:

- `retype`: recreate text as editable SVG text
- `redraw`: recreate with SVG primitives
- `crop`: extract as raster asset from the source image
- `embed`: place a previously extracted asset
- `simplify`: replace with a simpler editable equivalent only when fidelity is not important
- `semantic-redraw`: redraw to preserve meaning rather than exact appearance
- `omit`: exclude only if nonessential and documented

## Primary Rule

For visual objects, preserve source fidelity by default.

- Structural layout elements are usually redrawn.
- Text is usually retyped after any formula-like spans have been split into
  `math` elements.
- Pictorial, source-specific, or custom visual objects are usually cropped.
- Redraw only generic primitives and simple structural symbols.
- When uncertain, crop.

## Matrix

| Element type | Default decision | Use vector redraw when | Use raster crop when |
|---|---|---|---|
| Title, label, annotation | retype + split math spans | Text is readable and functions as a label | Decorative lettering is integral and must visually match |
| Formula, equation, inline math span | retype-math | The region contains variables, scripts, fractions, operators, Greek symbols, equations, or recurrence notation | Only if tiny and explicitly accepted as raster evidence |
| Panel, card, frame | redraw | Almost always | Rarely |
| Background block | redraw | Flat color or simple gradient | Complex texture, paper grain, or image background must be preserved |
| Divider, grid, table rule | redraw | Almost always | Rarely |
| Arrow, connector, flow line | redraw | Almost always | Only if arrow is a distinctive hand-drawn illustration and fidelity matters |
| Plain geometric marker | redraw | Circle, square, dot, plus, minus, check, cross, simple triangle | Rarely |
| Generic simple icon | redraw or simplify | Shape is generic, made of few primitives, and visual fidelity is not important | If the original style, silhouette, or consistency matters |
| Source-specific pictorial icon | crop | Only if user explicitly requests editable redraw | Almost always |
| Custom illustration | crop | Only if semantic redraw is requested | Almost always |
| Brand logo or model logo | crop | Only if user explicitly requests vectorization and it is feasible | Almost always |
| Chart | redraw or crop | Chart is central and data/visual encoding is readable | Chart is small, decorative, complex, or part of a screenshot |
| Table | redraw + retype | Text is readable and editing matters | Dense screenshot table with low edit requirement |
| Map, satellite image, orthophoto | crop | Only if highly simplified symbolic map | Almost always |
| UI screenshot | crop or rebuild | UI itself needs to be edited | UI is illustrative evidence or example content |
| Photo, product image, person | crop | Rarely | Almost always |
| Dense thumbnail grid | crop | Rarely | Almost always |
| Hand-drawn character/object | crop or semantic-redraw | Editable reinterpretation requested | Original style fidelity matters |
| Texture, grain, watercolor | crop or omit | Recreated as simple style | Texture fidelity matters |

## Icon-Specific Rules

Treat a small object as an asset, not a redraw candidate, if it has any of these qualities:

- source-specific pictorial identity
- custom silhouette
- shaded or textured details
- brand/model/institutional identity
- embedded raster fragments
- similarity to a stock icon, paper icon, screenshot, map fragment, or illustration
- repeated use across the source figure where consistency matters

Examples that should usually be cropped:

- cloud/search icon used as a data source symbol
- e-commerce platform/database icon
- drone, camera, folder, document stack, folder-with-card, city model, terrain model
- clothing item, person, avatar, face, phone mockup, route-map screenshot
- model logos, application icons, benchmark icons
- hand-drawn characters and custom props

Examples that may usually be redrawn:

- plain arrows
- boxes and containers
- simple dashed rectangles
- table grid lines
- plus signs and check marks
- simple bullets and node circles
- plain bar placeholders when exact chart values are not important

## Composite Split Rule

For composite regions, split by function:

- panel/card/background: redraw
- label/caption prose: retype
- inline formula span inside a label/caption: retype-math
- pictorial icon/image: crop
- connector/arrow: redraw

Do not crop an entire tile merely to preserve an icon if the tile background and label should remain editable.

## Priority Rules

1. If the user explicitly needs an element editable, prefer `retype`, `redraw`, or `semantic-redraw`.
2. If the element is a source-specific visual object, prefer `crop` even when it looks simple.
3. If the element is a structural affordance, prefer `redraw`.
4. If exact text is uncertain, mark it with `notes: "verify text"` in the manifest.
5. If a crop may be inaccurate, include extra padding and document it.
6. If redrawing would create a different-looking substitute, crop instead.
