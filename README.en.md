<div align="center">
  <img src="./assets/figedit-logo.png" alt="FigEdit Logo" width="220">

  <h1>FigEdit · 图易编</h1>

  <p><strong>Make flattened figures editable again.</strong></p>

  <p>Rebuild screenshots, paper figures, diagrams, and AI-generated graphics as editable SVG and native PowerPoint.</p>

  <p>
    <a href="./README.md">中文</a> ·
    <a href="./README.en.md">English</a>
  </p>

  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
    <a href="./VERSION"><img src="https://img.shields.io/badge/Version-0.1.0-2563EB?style=flat-square" alt="Version 0.1.0"></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-F97316?style=flat-square" alt="MIT License"></a>
  </p>

  <p>
    <a href="#examples">Examples</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#how-it-works">How it works</a> ·
    <a href="#acknowledgments-and-third-party-code">Acknowledgments</a>
  </p>
</div>

---

## What it does

FigEdit, also known in Chinese as 图易编, is an agent skill for rebuilding flattened images as editable graphics packages. Give it a screenshot, a paper figure, an AI-generated slide, a technical architecture diagram, or almost any other raster graphic. It separates the image into meaningful parts and reconstructs each part in the form that is most useful to edit:

- labels become real text;
- panels, borders, arrows, and connectors become vector shapes;
- formulas become semantic math and editable PowerPoint equations;
- photos, maps, screenshots, logos, and distinctive visual elements remain replaceable cropped assets.

The result is not merely an auto-traced image. It is a structured package that can be relabeled, rearranged, and restyled.

## Where it helps

### AI-generated graphics that look good but cannot be edited

Image generators can produce polished slides and diagrams, but everything is baked into pixels. FigEdit reconstructs the layout as actual PowerPoint elements, so text boxes can be edited, shapes can be moved, and backgrounds can be replaced.

### Paper figures worth adapting

When a published figure has a useful layout, color system, or visual structure, FigEdit can rebuild that structure without forcing you to redraw the whole figure by hand. Labels and components can then be changed directly.

### Lost or unavailable source files

If an infographic only survives as a PNG or screenshot, FigEdit can recover much of its editable structure. Frames become vectors, readable labels become text, and source-specific icons or imagery are preserved as clean crops.

## Examples

Each image below compares the source figure with the FigEdit reconstruction.

### 1. Slide-layout decomposition

![Original and reconstructed generative AI history infographic](./assets/examples/01-slide-layout.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/genai-history/)

### 2. Mixed icons and diagram structure

![Original and reconstructed Skill Compiler architecture diagram](./assets/examples/02-icon-diagram.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/skill-compiler/)

### 3. Full vector redraw

![Original and reconstructed Parallel Loops paper figure](./assets/examples/03-vector-redraw.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/parallel-loops/)

### 4. Asset-heavy reconstruction

![Original and reconstructed virtual try-on data pipeline](./assets/examples/04-raster-assets.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/tryon-pipeline/)

### 5. Mixed-element reconstruction

![Original and reconstructed TransitBench infographic](./assets/examples/05-mixed-reconstruction.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/transitlm/)

### 6. Formula-rich reconstruction

![Original and reconstructed AST method figure with mathematical notation](./assets/examples/06-formula-reconstruction.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/ast-reveal/)

### 7. Mixed formulas and raster evidence

![Original Camera Grid Rendering figure](./assets/examples/camera-grid-rendering/source.png)

![Reconstructed Camera Grid Rendering figure](./assets/examples/camera-grid-rendering/preview.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/camera-grid-rendering/)

### 8. Grouped data-chart reconstruction

![Original and reconstructed LLM performance evaluation chart](./assets/examples/08-llm-performance-evaluation.png)

[Open the complete case: source, SVG, PPTX, manifest, and quality reports](./assets/examples/llm-performance-evaluation/)

## Why a hybrid approach?

Turning a flat image back into an editable document is not only an object-recognition problem. The difficult part is deciding how each element should be represented.

| Approach | Typical method | Strength | Limitation |
| --- | --- | --- | --- |
| Outline tracing | Potrace, VTracer, Illustrator Image Trace | Fast and useful for logos, line art, and silhouettes | Does not understand text, formulas, or relationships; complex figures become piles of paths |
| OCR text overlay | OCR-to-PPT tools | Keeps the appearance while making some text editable | Most structure remains rasterized, and the original text may still be visible underneath |
| Vision-guided code reconstruction | SVG, Draw.io, Excalidraw, or TikZ generation | Good for regular nodes, arrows, and diagrams | Distinctive icons, screenshots, maps, and pictorial content are often simplified or lost |
| End-to-end image-to-SVG | Specialized generative models | Highly automated and capable of path-level output | Often requires dedicated models or GPUs; complex outputs can be long, fragile, and hard to edit |
| Element decomposition | Segmentation, OCR, cleanup, and layered assembly | Preserves richer visual content and supports object-level editing | Usually depends on a heavy multi-model pipeline |

FigEdit combines the useful parts of these approaches:

- ordinary text is reconstructed as editable text;
- formulas are stored as semantic math and exported as editable Office Math in PowerPoint;
- panels, shapes, borders, arrows, and connectors are rebuilt as vectors;
- logos, photos, screenshots, maps, chart bodies, and other source-specific visuals are cropped from the source;
- the final package includes SVG, self-contained SVG, and native PPTX output.

## How it works

The workflow has four stages: measure, decide, compose, and validate.

### 1. Measure

PaddleOCR locates text candidates, while OpenCV detects lines, rectangles, arrows, and other geometric evidence. The scripts also sample colors and style information. These measurements guide reconstruction; they do not automatically become final elements.

### 2. Decide

The agent classifies the figure and chooses a representation for every significant element.

| Element | Representation |
| --- | --- |
| Panels, arrows, grids, separators | Editable SVG shapes |
| Labels, titles, captions, legends | Editable text |
| Equations, variables, inline formulas | LaTeX-backed math and Office Math |
| Icons, photos, maps, charts, logos | Cropped and replaceable image assets |

Complex figures can mix several strategies. A single panel may use a vector frame, editable labels, semantic formulas, and preserved raster evidence. Every decision is recorded in `manifest.json`, making the build reproducible.

### 3. Compose

The manifest is converted into the final package: vector structure, positioned text, rendered formulas, cropped image assets, SVG files, and a native PowerPoint file.

### 4. Validate

The audit checks for missing structure, text trapped inside image assets, failed formula conversion, weak editability, clipped crops, and export problems. The agent repairs the manifest and recomposes the package when necessary.

## Quick start

### Requirements

- Python 3.10+
- An agent environment that supports skills, image input, and local tool execution

Reconstruction quality depends heavily on the model's visual understanding, spatial reasoning, and ability to inspect generated files. Use a capable multimodal coding agent for complex figures.

### Install

Clone the repository:

```bash
git clone https://github.com/giszzt/figedit.git ~/.codex/skills/figedit
```

Then install the Python dependencies:

```bash
pip install -r ~/.codex/skills/figedit/requirements.txt
```

You can also ask your agent to install the skill directly from:

```text
https://github.com/giszzt/figedit
```

### Use

Once installed, give the agent an image and describe the editable result you need:

```text
Turn this figure into an editable SVG package.
```

```text
Rebuild this image as an editable PowerPoint figure.
```

```text
I need to change several labels in this diagram. Convert it into an editable PPTX.
```

The agent should run the full measurement, reconstruction, export, and quality-check workflow in your project directory.

## Output package

```text
output/
├── editable.svg              # Editable SVG with linked assets
├── editable_embedded.svg     # Self-contained SVG with embedded assets
├── editable.pptx             # Native PowerPoint shapes and text boxes
├── preview.png               # Rendered preview
├── contact_sheet.png         # Overview of extracted raster assets
├── manifest.json             # Reconstruction plan
├── quality_report.md         # Quality checks and export status
├── editability_report.md     # Text-lift and asset-text audit
└── assets/                   # Cropped raster assets
```

## Project structure

```text
figedit/
├── SKILL.md            # Agent-facing workflow
├── README.md           # Chinese introduction
├── README.en.md        # English introduction
├── LICENSE
├── VERSION
├── THIRD_PARTY_NOTICES.md
├── requirements.txt
├── scripts/            # Measurement, composition, export, and audit tools
├── references/         # Reconstruction policies and authoring guidance
├── templates/          # Manifest schema and task templates
├── examples/           # Example prompts
└── assets/examples/    # Complete downloadable reconstruction cases
```

## Dependencies

| Package | Version | Purpose |
| --- | --- | --- |
| opencv-python | >= 4.9 | Structural detection |
| paddleocr | >= 3.7 | OCR using PP-OCRv6 |
| paddlepaddle | >= 3.3 | PaddleOCR backend |
| Pillow | >= 10.0 | Image processing |
| numpy | >= 1.24 | Array operations |
| scipy | >= 1.10 | Spatial analysis |
| matplotlib | >= 3.7 | Preview rendering |
| latex2mathml | >= 3.81 | Formula conversion |
| lxml | >= 5.0 | SVG and XML processing |

## Contributing

Issues and improvements are welcome, especially for complex layouts, formula export, OCR correction, and PowerPoint compatibility.

## Acknowledgments and third-party code

FigEdit's native SVG-to-PPTX export layer is adapted from [PPT Master](https://github.com/hugohe3/ppt-master). Thanks to Hugo He for open-sourcing its native, element-by-element editable PowerPoint conversion work. FigEdit extends and integrates that work for single-figure reconstruction, manifest-driven assets, editable equations, and reconstruction quality checks.

PPT Master is licensed under the MIT License. Its copyright notice, complete license text, and a description of the integration are preserved in [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md). FigEdit is an independent project and is not affiliated with or endorsed by PPT Master or its author.

## License

FigEdit's original code is available under the [MIT License](./LICENSE). Third-party components remain under their respective licenses; see [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
