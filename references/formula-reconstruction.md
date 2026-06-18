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
quality gate. Repair the LaTeX and rerun composition until every important
formula is editable.
