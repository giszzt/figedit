# Formula Reconstruction

Read this when a figure contains equations, inequalities, recurrences, fractions,
summations, script-heavy symbols, Greek-letter expressions, or inline math inside
titles, labels, legends, and captions. It explains how to author `math` elements
so the compose step renders vector SVG math and editable PowerPoint equations.

## Math is a first-class semantic object

If a readable region is primarily an equation, inequality, recurrence, fraction,
summation, script-heavy symbol, or Greek-letter expression, use a `math` element:

```json
{
  "type": "math",
  "id": "episode-advantage-formula",
  "latex": "A^{\\mathrm{ep}}_{u,n,k}=\\frac{R_n-\\mathrm{median}(R_u)}{\\mathrm{MAD}(R_u)+\\epsilon}",
  "x": 1450,
  "y": 500,
  "w": 330,
  "h": 70,
  "font_size": 24,
  "fill": "#111111",
  "text_anchor": "start",
  "dominant_baseline": "middle",
  "decision": "retype-math",
  "detector": "model+ocr",
  "review_status": "verified"
}
```

Do not encode formulas as strings such as `A^{ep}_i` inside `type: "text"`.
That preserves characters but loses the mathematical layout. The compose step
uses `scripts/math_renderer.py` to render math elements as vector SVG paths with
the original LaTeX stored in `data-latex`. For PPTX, `scripts/pptx_math.py`
converts the same normalized LaTeX to MathML, transforms it to Office Math
(OMML), strips the successfully converted SVG formula paths from the PPTX
staging SVG, and injects editable equation objects into `editable.pptx`.
Use plain `text` only for ordinary prose labels, code, file names, legends,
and captions.

## Split inline math from prose

This rule applies to inline formulas as well as standalone formulas. For a
mixed label such as `turn-level scope A^{intent}`, author two elements:

```json
[
  {
    "type": "text",
    "id": "title-turn-label",
    "text": "turn-level scope",
    "x": 622,
    "y": 671,
    "font_size": 34,
    "decision": "retype"
  },
  {
    "type": "math",
    "id": "title-turn-formula",
    "latex": "A^{\\mathrm{intent}}",
    "x": 842,
    "y": 671,
    "w": 120,
    "h": 42,
    "font_size": 34,
    "dominant_baseline": "middle",
    "decision": "retype-math"
  }
]
```

## Scan every text element before finalizing

Before finalizing the manifest, scan every `type: "text"` element for formula
cues: TeX commands, `^`/`_` scripts, Unicode super/subscripts, Greek variables,
large operators, relation symbols, arrows, fractions, recurrences, and indexed
variables. If a symbol-like string is intentionally a literal method name,
filename, code token, or prose label, keep it as text only with
`formula_policy: "not-formula"` and a `formula_decision_reason`.

## Never silently drop a failed conversion

If a formula cannot be converted to editable OMML, do not silently mark it as
done. The PPTX exporter keeps that formula visible as vector artwork and writes
the failure to `editable.pptx.math_report.json` and the `pptx_math_export`
quality gate. Repair the LaTeX and rerun composition until every detected
formula is editable, unless the user explicitly waives formula editability for a
specific item.

## Editable formulas must also stay visually placed

Formula reconstruction has two inseparable requirements:

1. the formula is semantic and editable (`math` in the manifest, editable Office Math in PPTX)
2. the formula occupies the same visual slot as the source after SVG rendering and native PPTX export

Do not raster-crop a formula to avoid layout difficulty. If an editable formula
drifts, grows, shrinks, overlaps a connector, or shifts its baseline in
PowerPoint, treat that as a layout defect and repair the manifest.

For dense figures, record enough layout evidence to make repair reproducible:

- `source_region`: the formula's observed bounding box in source-image pixels
- `x`, `y`, `w`, `h`: the intended placement slot, usually matching the source region after padding decisions
- `font_size`: chosen to fit the slot after render, not merely copied from OCR height
- `text_anchor` and `dominant_baseline`: explicit anchor choices
- `baseline_y` when a formula must align with neighboring prose or a diagram axis
- `layout_lock: "source-slot"` for formulas that must fit a tight region
- `review_status: "verified"` only after visual checking

Example:

```json
{
  "type": "math",
  "id": "formula-episode-advantage",
  "latex": "A^{\\mathrm{ep}}_{u,n,k}=\\frac{R_n-\\mathrm{median}(R_u)}{\\mathrm{MAD}(R_u)+\\epsilon}",
  "source_region": { "x": 804, "y": 237, "w": 104, "h": 30 },
  "x": 804,
  "y": 237,
  "w": 104,
  "h": 30,
  "font_size": 18,
  "text_anchor": "start",
  "dominant_baseline": "middle",
  "baseline_y": 252,
  "layout_lock": "source-slot",
  "decision": "retype-math",
  "review_status": "verified"
}
```

When SVG and PPTX disagree, prefer adjusting the editable formula's layout
constraints over accepting visual drift. Common repairs are reducing
`font_size`, widening the slot if the source allows it, changing the anchor,
splitting a mixed prose/formula line into finer elements, and aligning adjacent
elements to a shared `baseline_y`.

`editable.pptx.math_report.json` proves editability, not placement. A successful
OMML conversion is not sufficient for acceptance on dense formula figures.
