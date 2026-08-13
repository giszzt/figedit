# SVG 编写约定（SVG Authoring Conventions）

**何时读我**：每个任务写 manifest 元素前必读。本文件是 SVG 画布、分层、字体和 marker 约定的权威。

## 画布

除非要求缩放，SVG 坐标系使用源图尺寸。

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="W" height="H" viewBox="0 0 W H">
```

## 文件组织

分组顺序（与 `build_svg_from_manifest.py` 的 `group_order` 一致——连接线画在 sections/icons 之下，图标盖住线头）：

```xml
<g id="background">...</g>
<g id="assets">...</g>
<g id="panels">...</g>
<g id="connectors">...</g>
<g id="sections">...</g>
<g id="icons">...</g>
<g id="texts">...</g>
<g id="annotations">...</g>
```

实操建议：manifest 元素显式写 `layer` 字段指定分组，不要依赖按类型推断的默认分组——类型推断的落组结果和你预想的绘制次序不一定一致。

每个 `background_plans[]` 条目通过 `plate_asset_id` 或 `plate_file` 在 background 组放置一张区域底板，位置取该计划的 `source_region`，并带 `preserveAspectRatio="none"`。底板像素尺寸和放置坐标必须与区域一致；该属性防的是意外信箱化，不是几何修复。旧 `background_plan` 仍按全画布底板兼容。

## PPTX 分组

为图层次序和可维护性组织 SVG 分组，但不要依赖普通分组在 PowerPoint 里保持成组。原生 PPTX 导出默认做语义解组：`background`、`assets`、`panels`、`connectors`、`texts` 这类非语义布局组在应用变换和样式后被压平，最终 PowerPoint 文件无需手动解组即可直接选中元素。

只在解组会损害视觉保真或编辑性时保持分组原子性。使用显式标记：

```xml
<g id="logo-mark" data-pptx-group="atomic">...</g>
<g id="equation-main" class="formula" data-latex="...">...</g>
<g id="masked-photo" data-pptx-group="preserve" clip-path="url(#clip)">...</g>
```

导出器还会保留带公式、组级裁剪路径、蒙版、滤镜、不透明度或需要组包装的旋转的分组。除非用户明确要求某对象整体移动，不要把整幅图、整个面板或整个素材层包成原子组。

## 命名

使用稳定的语义 ID：

- `panel-data-source`
- `section-evaluation-metrics`
- `arrow-collection-to-processing`
- `label-stage-1`
- `asset-route-map`

避免 `rect1`、`image2`、`path-final` 这类通用名。

## 文字

- 用 `<text>` 和 `<tspan>` 保持文字可编辑。
- 多行标签手动断行。
- 用 `text-anchor` 和 `dominant-baseline` 控制对齐。
- 不确定的文字在 manifest 里标注。
- 密集图形保留源图槽位和基线，不依赖浏览器或 PowerPoint 的默认文字度量。

推荐字体栈：

```css
--font-sans: "Inter", "Arial", "Helvetica", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
--font-serif: "Georgia", "Times New Roman", "Noto Serif CJK SC", serif;
--font-hand: "Comic Sans MS", "Comic Neue", "Arial Rounded MT Bold", "Microsoft YaHei", sans-serif;
```

生成器保留 CSS 变量定义，但写入每个 `<text>` 的 `font-family` 时会把 `var(--font-*)` 展开，并把本机已安装的首选字体放在栈首。PPTX 导出器不得把 `var(--font-sans)` 之类的 CSS 变量名原样写成 DrawingML typeface。

除非明确要求，不要把普通文字转成轮廓路径。

交付目标包含 PPTX 时的字符集约束见 `background_reconstruction.md` 的文字层策略一节（弯引号等易触发 PowerPoint 字体回退的字符会留下可见空档）。

## 公式

公式用 manifest 的 `math` 元素，不要用纯文字近似。生成器把 `latex` 渲染为矢量路径并在 `data-latex` 保留源公式。PPTX 导出器用同一个 `latex` 值创建可编辑 Office Math 公式，所以畸形或近似的 LaTeX 应视为重建缺陷。

```json
{
  "type": "math",
  "id": "formula-return-normalization",
  "latex": "\\frac{R_n-\\mathrm{median}(R_u)}{\\mathrm{MAD}(R_u)+\\epsilon}",
  "x": 1200,
  "y": 520,
  "w": 260,
  "h": 70,
  "font_size": 24,
  "fill": "#111111"
}
```

分式、求和、乘积、积分、希腊字母、上下标、帽/横线、矩阵记号和递推式都用 `math`。散文标签、文件名、代码片段和图注用普通 `text`。

不要因为源图公式短就用 `text`。`A_i^{tree}`、`\delta_i`、`R^{(m)}`、`\sum_{\ell=1}^{G}` 这类，只要作为方程或数学标注出现，仍属于 `math`。

不要为回避排位难度而把公式栅格化。公式密或小，就保持可编辑并用测量好的源槽位、显式宽高、锚点、基线和字号控制布局。

散文/公式混排的标签，把视觉行拆成共享基线的相邻元素。不要把 TeX 语法、Unicode 上下标或紧凑的希腊变量记号留在 `type: "text"` 里。

```json
[
  {
    "type": "text",
    "id": "label-scope-prefix",
    "text": "episode-level scope",
    "x": 614,
    "y": 480,
    "font_size": 35
  },
  {
    "type": "math",
    "id": "label-scope-formula",
    "latex": "A^{\\mathrm{ep}}",
    "x": 920,
    "y": 480,
    "w": 90,
    "h": 42,
    "font_size": 35,
    "dominant_baseline": "middle"
  }
]
```

符号样文字确实不是公式时，加 `formula_policy: "not-formula"` 和简短的 `formula_decision_reason`。

原生 PPTX 导出使用 PowerPoint 文字和 Office Math 排版。含 `math` 或静态文字回流审计报告换行、溢出、缺字、碰撞风险时才做原生 PPTX 视检；无公式且静态审计全绿时以 SVG 为视觉验收源。

## 形状

使用：

- `rect`：面板、卡片、表格单元、背景块
- `line` / `polyline`：直连接线
- `path`：曲线连接线
- `marker`：箭头头部
- `circle` / `ellipse`：节点
- `polygon`：简单几何图标

### 箭头与连接线

优先在 manifest 用 `marker_start` / `marker_end`，不要为常规箭头手画 polygon。支持：

```json
"marker_end": {"style": "open-chevron", "size": 8},
"marker_start": {"style": "circle", "size": 6},
"connector_clearance": 4
```

样式有 `solid-triangle`、`open-chevron`、`circle`、`diamond`。旧 `arrow_start` / `arrow_end` 兼容为实心三角。直线的 `connector_clearance` 沿两端回缩；端点必须仍指向正确对象且不压进节点。`marker_mid` 仅在需要路径中间语义标记时使用。

## 样式

在 `<style>` 里定义可复用类：

```xml
<style>
  .panel { fill: #fff; stroke: #333; stroke-width: 2; }
  .label { font-family: var(--font-sans); font-size: 18px; fill: #111; }
  .connector { fill: none; stroke: #333; stroke-width: 2; }
</style>
```

## 素材

`editable.svg` 用相对路径：

```xml
<image href="assets/example.png" x="100" y="120" width="240" height="160" preserveAspectRatio="xMidYMid meet"/>
```

`editable_embedded.svg` 用 base64 data URI。

背景底板优先用顶层 `background_plans[]` 引用，不要加重复的 image 元素。坐标敏感的前景素材保持正常的宽高比保留，并对照源图叠加验证位置。

## 可访问性与可维护性

条件允许时：

- 主要分组加 `<title>`
- 使用语义 ID
- 源顺序贴近阅读顺序
- 复杂路径保持可读或加说明
