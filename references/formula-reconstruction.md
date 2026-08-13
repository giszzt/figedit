# 公式重建（Formula Reconstruction）

图形含方程、不等式、递推式、分式、求和、上下标密集符号、希腊字母表达式，或标题/标签/图例/图注里的行内数学时读本文件。它说明如何编写 `math` 元素，使合成步骤渲染出矢量 SVG 公式和可编辑的 PowerPoint 公式。

## 数学是一等语义对象

可读区域主体是方程、不等式、递推、分式、求和、上下标密集符号或希腊字母表达式时，用 `math` 元素：

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

不要把 `A^{ep}_i` 这类公式编码成 `type: "text"` 里的字符串。那样保住了字符，丢掉了数学排版。合成步骤用 `scripts/math_renderer.py` 把 math 元素渲染为矢量 SVG 路径，原始 LaTeX 存在 `data-latex`。PPTX 侧，`scripts/pptx_math.py` 把同一份规范化 LaTeX 转成 MathML，再转 Office Math（OMML），从 PPTX 暂存 SVG 中剥掉已成功转换的公式路径，把可编辑公式对象注入 `editable.pptx`。普通 `text` 只用于散文标签、代码、文件名、图例和图注。

## 行内数学从散文中拆出

本规则对行内公式和独立公式同样适用。`turn-level scope A^{intent}` 这类混排标签写成两个元素：

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

## 定稿前扫描每个文字元素

定稿 manifest 前，扫描每个 `type: "text"` 元素找公式痕迹：TeX 命令、`^`/`_` 上下标、Unicode 上下标、希腊变量、大型运算符、关系符号、箭头、分式、递推式和带下标变量。符号样字符串确实是字面的方法名、文件名、代码 token 或散文标签时，保留为 text，但加 `formula_policy: "not-formula"` 和 `formula_decision_reason`。

## 绝不静默放过失败的转换

公式无法转成可编辑 OMML 时，不要静默标记完成。PPTX 导出器会把该公式保留为可见矢量图形，并把失败写进 `editable.pptx.math_report.json` 和 `pptx_math_export` 质量门。修复 LaTeX、重跑合成，直到每个检出公式都可编辑，除非用户对某项明确豁免。

## 可编辑公式必须同时保持视觉排位

公式重建有两个不可分割的要求：

1. 公式语义化且可编辑（manifest 里是 `math`，PPTX 里是可编辑 Office Math）
2. SVG 渲染和原生 PPTX 导出后，公式占据与源图相同的视觉槽位

不要为回避排位难度把公式裁成位图。可编辑公式在 PowerPoint 里漂移、变大、变小、压到连接线或基线偏移时，视为排位缺陷，修 manifest。

密集图形记录足够的布局证据，让修复可复现：

- `source_region`：公式在源图像素中的观察包围盒
- `x`、`y`、`w`、`h`：预期放置槽位，通常等于 padding 决策后的源区域
- `font_size`：按渲染后适配槽位来选，不是照抄 OCR 高度
- `text_anchor` 和 `dominant_baseline`：显式锚点选择
- `baseline_y`：公式必须与相邻散文或图轴对齐时
- `layout_lock: "source-slot"`：必须适配紧凑区域的公式
- `review_status: "verified"`：仅在视检之后

示例：

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

SVG 和 PPTX 表现不一致时，优先调整可编辑公式的布局约束，而不是接受视觉漂移。常见修法：减小 `font_size`、源图允许时加宽槽位、改锚点、把散文/公式混排行拆成更细的元素、相邻元素对齐到共享 `baseline_y`。

`editable.pptx.math_report.json` 证明可编辑性，不证明排位。密集公式图形上，OMML 转换成功不足以验收。
