# Manifest 规范（Manifest Specification）

manifest 记录重建方案，支撑可复现的更新。

## 必需部分

- `project`：项目 slug
- `source_image`：原图路径
- `canvas`：源图尺寸与背景色
- `classification`：图形类型与所选模式
- `route_decision`：新任务的组合路由锁；旧 manifest 可缺失
- `panels`：主要布局区域
- `assets`：裁剪或生成的位图素材
- `elements`：可编辑 SVG 元素与素材放置

没有 AI 清版区域时不需要 `background_plans`。局部或全图区域选定 `ai-clean-plate` 后，每个区域添加一条计划。

## Route Decision

新任务在测量、裁剪和生成之前记录 Route Decision v2：

```json
{
  "route_decision": {
    "schema_version": 2,
    "source": "fresh-global-read",
    "route_status": "ready",
    "editability_depth": "text+structure",
    "base_strategy": "svg-rebuild",
    "background_scopes": [],
    "asset_groups": [],
    "unresolved_decisions": [],
    "validation_tier": "svg-primary",
    "exception_ids": ["icon-overlap-03"]
  }
}
```

允许值：

- `schema_version`：新结构固定为 `2`
- `source`：`fresh-global-read`、`user-directive`
- `route_status`：`ready`、`needs-user-input`
- `editability_depth`：`text-only`、`text+structure`、`selective-assets`、`full-extract`
- `base_strategy`：`svg-rebuild`
- `background_scopes`：局部/全图连续场与明确栅格保留区域；每个 scope 的粗略坐标先标 `region_accuracy: estimated-from-global-read`，生成前收紧为 `measured`
- `asset_groups`：初始批量素材策略
- `unresolved_decisions`：尚待用户选择的事项
- `validation_tier`：`svg-primary`、`pptx-triggered`
- `exception_ids`：字符串数组

`background_scopes` 记录路由时已判定的区域策略；最终生成来源与验收写入 `background_plans[]`。每个 `asset_groups[]` 条目除 `strategy / ids / reason` 外还写 `separability`：`not-applicable`、`clean`、`clean-on-fill`、`contaminated` 或 `embedded-in-continuous-field`。污染组必须加 `observed_overlap`，列出边框、文字、箭头、邻居等整图可见压盖。最终 `assets[].decision` 必须与 `asset_groups` 一致；crop 组只允许 `clean / clean-on-fill`，并与最终 `crop_window` 一致。完整算法见 `global_routing.md`。

AI scope 可含 `foreground_inventory[]`，只列处理方式随用户深度变化的源图专有非结构对象。每项为 `id / kind: source-specific-visual / resolved_strategy`；未决时为 `pending-user-choice`，确认后改为 `flatten` 或 `regenerate-chroma`，并在 `asset_groups` 中使用同一策略。通用箭头、路线、圆点、文字和公式不放入该清单。

旧 manifest 的 `source: global-read`、`reconstruction_route` 与单个 `background_plan` 继续兼容读取，但新任务不得只写旧式二选一路由。

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

`reconstruction_mode` 只作人类可读分类，不再决定背景路线。实际执行以 Route Decision v2 与 `background_plans[]` 为准。

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

## 连接线与 marker

旧字段 `arrow_start` / `arrow_end` 继续支持，等价于实心三角。新字段允许明确样式和尺寸：

```json
{
  "type": "line",
  "id": "flow-a-b",
  "x1": 120,
  "y1": 90,
  "x2": 320,
  "y2": 90,
  "marker_end": {"style": "open-chevron", "size": 8},
  "marker_start": null,
  "connector_clearance": 4
}
```

- `marker_start` / `marker_end.style`：`solid-triangle`、`open-chevron`、`circle`、`diamond`
- `size`：正数，单位为 SVG 用户空间像素；缺省为 7
- `connector_clearance`：正数或 0；直线连接线沿两端方向各回缩该距离，避免线头压入节点
- `marker_mid`：可选，用于 `line` / `polyline`；`{"style":"solid-triangle","size":7,"at":0.5}` 表示路径中点标记

新字段是可选表达能力，不是每条连接线必须满足的 gate。手画 polygon 箭头允许保留，但质量报告会提示优先使用 marker。

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
- `crop_window`：`clean`、`clean-on-fill`、`contaminated` —— Crop Window Check 的视觉判定结果。一次整图和 contact sheet 可以覆盖整批，异常项才独立放大。`clean-on-fill` 时附带承载面实色并确保 manifest 用同色重画承载面；`contaminated` 的资产不允许 `decision: "crop"`（`quality_audit.py` 的 `crop_window_consistency` 门会判 failed）。
- `background_handling`：`tight-crop`、`transparent`、`preserve-background`、`remove-background`、`mask`、`full-canvas`、`uncertain`
- `crop_status`：`pending`、`verified`、`needs-padding`、`wrong-region`、`background-issue`、`dirty-residue`
- `text_policy`：`extract-editable`、`preserve-raster`、`allow-embedded-text`、`review`

chroma 再生产出的素材用 `source_mode: "external"`、`decision: "regenerate-chroma"` 和 `generation_provenance` 对象；完整条目形态和工作流见 `chroma_regeneration.md`。

确认为 `clean / clean-on-fill` 的素材才从源图坐标裁剪矩形（`scripts/crop_assets.py` 读取各素材的 `source_region`），带 `decision: "crop"`；污染素材改走再生、压平或用户明确接受的区域栅格保留。

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

## Background Plans

`background_plans` 是数组；每个 `ai-clean-plate` scope 对应一条执行与验收记录。没有 AI 清版区域时省略。旧的单个 `background_plan` 只用于兼容。

```json
{
  "background_plans": [
    {
      "scope_id": "panel-c-map",
      "strategy": "ai-clean-plate",
      "source_region": {"x": 1200, "y": 55, "w": 478, "h": 600},
      "foreground_mode": "flatten",
      "foreground_mode_source": "user-choice",
      "route_reason": "Editable labels and routes overlap continuous map pixels.",
      "plate_asset_id": "asset-clean-plate-panel-c",
      "generation_provenance": {
        "role": "regional-clean-plate",
        "backend": "Codex Image Gen",
        "prompt_file": "work/panel-c/clean-plate-prompt.txt",
        "references": ["work/panel-c/source.png"],
        "output": "work/panel-c/clean-plate.png"
      },
      "candidate_review": {
        "accepted": true,
        "checks": {
          "foreground_removed": true,
          "visual_identity_preserved": true,
          "region_registration_usable": true
        }
      },
      "review_status": "verified"
    }
  ]
}
```

最低要求：

- `scope_id` 唯一，并引用 `route_decision.background_scopes[].id`
- `strategy` 恰为 `ai-clean-plate`
- `source_region` 与路由 scope 一致；全画布只是 `x=0,y=0,w=canvas.width,h=canvas.height` 的普通特例
- `foreground_mode` 为 `full-extract`、`selective` 或 `flatten`，不得为 `pending-user-choice`
- `foreground_mode_source` 为 `user-choice`、`explicit-request` 或仅限无人值守的 `auto-default`
- `plate_asset_id` 指向与区域同尺寸、放置坐标一致的 `background-plate` 素材
- `generation_provenance` 记录实际生成路径与输出
- `candidate_review.accepted` 为 true

详细的 `text_layer_policy`、`foreground_asset_policy`、`generation_brief` 对象是可选的。有用就存，不当作例行仪式。

## AI 清版底的前景素材

清版底验收后，源图专有素材仍由常规位图素材门决定。

只有以下条件同时成立才在底板上裁素材：

- 精确身份重要
- 独立移动或替换有用
- 裁剪干净

不要把大块矩形原背景裁到清版底上。不要把旧标签、引线或标注碎片裁回最终包。
