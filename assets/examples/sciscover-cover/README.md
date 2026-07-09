# Sciscover Cover FigEdit Reconstruction

This package rebuilds `source.jpg` as a background-aware editable package.

Route:
- `E-ai+B`: AI clean background plate plus source-preserved logo crops and editable text overlays.
- The dense blue fiber/circuit background is flattened into the clean plate.
- Main cover typography, issue metadata, and sponsor text are SVG/PPT editable text.
- Brand-specific logo blocks are source crops rather than approximate vector redraws.

Key outputs:
- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `quality_report.md`
- `editability_report.md`

Known tradeoff: the clean background plate is generated and therefore approximate, not source-exact. It is suitable as an editable cover reconstruction background, but not as evidence-preserving scientific data.
