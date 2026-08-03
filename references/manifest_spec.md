# Manifest 规范（Manifest Specification）

manifest 记录重建方案，支撑可复现的更新。

## 必需部分

- `project`：项目 slug
- `source_image`：原图路径
- `canvas`：源图尺寸与背景色
- `classification`：图形类型与所选模式
- `panels`：主要布局区域
- `assets`：裁剪或生成的位图素材
- `elements`：可编辑 SVG 元素与素材放置

常规 FigEdit manifest 不需要 `background_plan`。只有背景门选定 `ai-clean-plate`、或用户明确要求 AI 路线时才添加。

## 坐标系

使用源图像素坐标。

```json
{ "x": 120, "y": 80, "w": 300, "h": 180 }
```

## 推荐字段

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

`reconstruction_mode: "E-ai"` 仅在 `background_plan.strategy` 为 `ai-clean-plate` 时使用。

### Diagnostics（推荐）

```json
{
  "diagnostics": {
    "measurement_workspace": "figure-task/work"
  }
}
```

`measurement_workspace` 指向 `prepare_measurements.py --out` 的目录。合成步骤靠它把 `ocr_results.json` 等证据拷进产物包，可编辑性门才能计算 `text_lift_ratio`；缺失时合成会回退搜索 manifest 同级的 `work/`、`../work/`，都找不到则该门报 `unavailable`。`prepare_measurements.py` 产出的 `draft_manifest.json` 已自动带上这个字段——编写最终 manifest 时保留它。

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
  "decision": "crop",
  "crop_window": "clean"
}
```

`pad` 可以为负，把裁剪内缩进区域内部——齐平嵌装素材（目测框会带进邻居边框几个像素的那种）的标准修法（见 `asset_extraction.md`）。

生成的背景底板：

```json
{
  "id": "asset-clean-plate",
  "file": "work/generated/clean-plate.png",
  "source_mode": "external",
  "x": 0,
  "y": 0,
  "w": 1920,
  "h": 1080,
  "kind": "background-plate",
  "decision": "generate-replacement",
  "crop_status": "verified"
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
  "source_region": { "x": 895, "y": 42, "w": 260, "h": 38 },
  "text": "Figure Title",
  "font_size": 32,
  "font_weight": "700",
  "review_status": "verified"
}
```

### Math 元素

```json
{
  "type": "math",
  "id": "eq-loss",
  "decision": "reconstruct-math",
  "x": 420,
  "y": 260,
  "w": 220,
  "h": 48,
  "source_region": { "x": 418, "y": 255, "w": 224, "h": 52 },
  "latex": "L = \\sum_i \\ell(y_i, f(x_i))",
  "font_size": 22,
  "layout_lock": "source-slot",
  "review_status": "verified"
}
```

普通稀疏图形里 `source_region`、`w`、`h`、`baseline_y`、`layout_lock` 是可选的。密集文字/公式图形里，凡是标签或公式必须放进紧凑视觉槽位的地方都要用它们——它们明确了可编辑性和排位是双重要求。

## 元素类型

助手脚本支持：

- `rect`
- `text`
- `math`
- `line`
- `path`
- `circle`
- `ellipse`
- `polygon`
- `polyline`
- `image`

其他类型可在合成脚本支持时手写 SVG。

## 素材保真字段

每个裁剪的视觉素材尽量附带保真元数据：

```json
{
  "asset_fidelity": "source-preserve",
  "decision_reason": "custom pictorial icon; preserve original appearance",
  "background_handling": "tight-crop",
  "crop_status": "verified",
  "crop_window": "clean"
}
```

推荐取值：

- `asset_fidelity`：`source-preserve`、`source-close`、`approximate-ok`、`semantic-only`
- `decision_reason`：对 `crop`、`redraw`、`flatten`、`regenerate-chroma` 或 `generate-replacement` 的简要说明
- `crop_window`：`clean`、`clean-on-fill`、`contaminated` —— Crop Window Check（SKILL.md 位图素材门）的肉眼判定结果。`clean-on-fill` 时附带承载面实色并确保 manifest 用同色重画承载面；`contaminated` 的资产不允许 `decision: "crop"`（`quality_audit.py` 的 `crop_window_consistency` 门会判 failed）。
- `background_handling`：`tight-crop`、`transparent`、`preserve-background`、`remove-background`、`mask`、`full-canvas`、`uncertain`
- `crop_status`：`pending`、`verified`、`needs-padding`、`wrong-region`、`background-issue`、`dirty-residue`
- `text_policy`：`extract-editable`、`preserve-raster`、`allow-embedded-text`、`review`

chroma 再生产出的素材用 `source_mode: "external"`、`decision: "regenerate-chroma"` 和 `generation_provenance` 对象；完整条目形态和工作流见 `chroma_regeneration.md`。

常规路线素材是从源图坐标裁剪的矩形（`scripts/crop_assets.py` 读取各素材的 `source_region`），带 `decision: "crop"`。

## 决策审计

manifest 应让不当重画一目了然。每个被重画（而非裁剪）的视觉对象都写理由：

```json
{
  "type": "path",
  "id": "simple-plus-marker",
  "decision": "redraw",
  "decision_reason": "generic primitive marker; not source-specific"
}
```

被重画的对象若是图形性、源图专有、品牌性、证据性或视觉上有辨识度的，该决策应视为可疑并复查。

## 可选证据字段

这些字段在困难案例上有用，普通任务不要求：

- `recognition_summary`：检视过的 OCR/风格诊断及其如何影响 manifest
- `asset_decision_policy`：哪些对象被裁剪、重画、压平或生成的简述
- `editability_targets`：困难重建的最低可编辑文字/结构/素材预期
- `layout_fidelity_targets`：必须在 SVG 和 PPTX 中视检的密集文字/公式区域
- `pptx_visual_review`：PPTX 渲染/打开复查的摘要

不要把这些字段当仪式添加。它们用于消除歧义。

## Background Plan

`background_plan` 只为 `ai-clean-plate` 存在。

常规路线：

```json
{
  "classification": {
    "reconstruction_mode": "C+B"
  }
}
```

不含 `background_plan`。

AI 清版底路线：

```json
{
  "background_plan": {
    "strategy": "ai-clean-plate",
    "route_decision": {
      "reason": "Foreground labels sit on a continuous illustrated field; crop + SVG cannot reconstruct the hidden pixels.",
      "crop_svg_recoverable": false
    },
    "plate_asset_id": "asset-clean-plate",
    "generation_provenance": {
      "role": "primary-clean-plate",
      "backend": "Codex Image Gen",
      "fallback_policy": "Codex Image Gen -> Labnana GPT-Image-2 -> Labnana Gemini/Nano Banana -> official provider API -> configured command",
      "prompt_file": "work/clean-plate-prompt.txt",
      "references": ["work/assets/source.png"],
      "output": "work/generated/clean-plate.png"
    },
    "candidate_review": {
      "accepted": true,
      "checks": {
        "foreground_text_removed": true,
        "major_visual_identity_preserved": true,
        "aspect_ratio_and_alignment_usable": true
      },
      "notes": "Brief visual review of the accepted candidate."
    },
    "review_status": "verified"
  }
}
```

最低要求：

- `strategy` 恰为 `ai-clean-plate`
- `route_decision.reason` 说明为何裁剪+SVG 无法忠实重建背景，或引用用户的路线要求
- `route_decision.source` 为 `background-gate` 或 `user-directive`（用户自己的话选的路线）
- `foreground_mode` 为 `full-extract`、`selective` 或 `flatten`，`foreground_mode_source` 为 `user-choice`、`explicit-request`（在 `route_decision` 引用用户措辞）或 `auto-default`（仅限无人值守运行）——见 `background_reconstruction.md` 的前景深度决策
- `plate_asset_id` 指向整幅画布的 `background-plate` 素材
- `generation_provenance` 记录实际生成路径与输出
- `candidate_review.accepted` 为 true

详细的 `text_layer_policy`、`foreground_asset_policy`、`generation_brief` 对象是可选的。有用就存，不强制每个清版底 manifest 都带。

## AI 清版底的前景素材

清版底验收后，源图专有素材仍由常规位图素材门决定。

只有以下条件同时成立才在底板上裁素材：

- 精确身份重要
- 独立移动或替换有用
- 裁剪干净

不要把大块矩形原背景裁到清版底上。不要把旧标签、引线或标注碎片裁回最终包。
