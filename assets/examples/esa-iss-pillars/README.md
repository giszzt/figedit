# ESA ISS Pillars FigEdit Reconstruction

This package rebuilds `source.png` as a background-aware editable package.

Route:
- `E-ai`: AI clean background plate with full foreground extraction.
- The continuous starfield is rebuilt as a clean plate.
- Mission labels, dates, arrows, separators, and layout marks are editable SVG/PPT elements.
- ESA/ISS marks and astronaut portraits are preserved as independent image assets.

Key outputs:
- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `quality_report.md`
- `editability_report.md`

Known tradeoff: the clean plate and regenerated foreground assets are visually reconstructed, so this package is best treated as an editable design reconstruction rather than a source-exact archival copy.
