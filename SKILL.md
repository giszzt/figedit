---
name: figedit-v2
description: 将位图图形重建为高保真可编辑 SVG 与原生 PowerPoint，支持仅文字可编辑、文字/结构/公式可编辑、源图素材保真混合、选择性或完整前景拆分，以及复杂连续背景的 AI 清版底重建。当用户希望把截图、论文插图、流程图、架构图、信息图、UI、图表/地图、海报或封面转成可编辑图形，或提到“图片转可编辑 SVG/PPT”“仅文字可编辑”“图表重建”“FigEdit”时使用。
---

# FigEdit

把不可编辑的位图图形重建为高保真、可维护、可继续编辑的 SVG 与原生 PPTX 包。

**主流程：勘察 → 吸附 → 组装 → 验收。**模型负责语义（对象是什么、走哪条路线、要不要问用户），脚本负责像素（边界在哪、净空多少、窗口脏不脏）。模型不当卡尺，脚本不做语义裁判。

## 核心原则

**勘察一次、机器量测、批量组装、异常细查。**第一次看源图时一次性形成全部对象的路线直觉和重建计划；精确坐标和污染判定交给 snap_boxes；修复收齐成批用 manifest_edit 一次改完；只有脚本点名或整图看不清的项才局部放大。

### 重绘门槛

只有“用三五笔基础图元能画得像”的图形才允许 `redraw`：朴素箭头、方框、分隔线、圆点、加减号、对勾、简单节点圆。有定制轮廓、渐变、阴影、多色细节、品牌或角色身份的对象一律按素材处理（crop / regenerate-chroma / flatten），哪怕它看起来简单。拿不准时按素材处理，不重画。重画产物必须与源图形状可对照，画不像就是路由错误，不是绘画技术问题。

## 工作位置

所有命令在用户项目目录运行，每张图建任务目录（`figure-task/work` 证据、`figure-task/out` 交付），绝不写回 skill 目录。Windows 路径用正斜杠，非 ASCII 路径先经文件系统验证。

## 默认工作流

### 1 勘察

看一次足够清晰的源图，在一个回合里写出 `work/inventory.json`：全部对象各一行（id、粗框 bbox、kind、route、一句话理由、是否需用户决定）。粗框允许 10–20px 偏差，精确坐标是下一阶段脚本的事。同时在 manifest 顶层写 `reconstruction_plan`（edit_scope、background_regions、validation_tier、open_questions、closeup_ids）。细则与决策树见 `references/routing.md`。

用户原话优先：说“仅文字可编辑”锁 `text-only`（连续场直接 flatten）；点名对象锁 `selective-assets`；要求全部可动锁 `full-extract`；检出公式且用户未表态时默认 `text+structure` 并锁 `pptx-triggered`。

**用户提问一次问完**：勘察结束时若有待决项，把前景深度选项、生成预算和 PPTX 附着预授权（含公式时）合并成一次提问。`open_questions` 非空期间禁止 OCR、裁剪、生成和 compose。拿到附着预授权后验收阶段直接 `--allow-attach`，不再二次提问。

### 2 吸附与测量

```powershell
python scripts/prepare_measurements.py input.png --out figure-task/work
python scripts/snap_boxes.py input.png --inventory figure-task/work/inventory.json --exclude-text figure-task/work/measurements/ocr_results.json --out figure-task/work/snap_report.json --sheet figure-task/work/snap_sheet.png
```

snap_boxes 把粗框吸附成紧裁剪窗，量四边净空，机械判定 `clean / clean-on-fill / contaminated / snap-failed`。看一次 snap_sheet 总览；只有 `contaminated`、`snap-failed`、带 warning 的项和 `closeup_ids` 才用 `inspect_regions.py` 局部放大。判定是证据不是裁判：contaminated 的对象由模型改路由（regenerate-chroma / flatten），不修判据。OCR 证据只读会改变 manifest 的部分（低置信文字、公式、坐标冲突）。

### 3 组装

必读 `references/manifest_spec.md`、`references/svg_authoring.md`、`references/quality_checklist.md`，其余 references 按路线加载（见各文件开头的适用说明）。写 manifest：文字 `retype`、公式拆 `math`、结构 `redraw`（过重绘门槛才行）、素材按 snap 判定走 `crop` 或改道。`--apply-snap` 直接回写裁剪窗。

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg
```

修复直接用批量通道，不手编大 JSON、不写临时 patch 脚本：

```powershell
python scripts/manifest_edit.py manifest.json --set "label-3,label-4:y+=4" --apply-fit figure-task/work/fit_report.json
```

告警收齐一批改完再 compose；SVG 冻结后 `--stage pptx` 导出，仅补元数据用 `--stage package`。

### 4 验收

每轮看 `preview.png` 与各报告；报告点名后只复查受影响区。最终至少看一次 SVG 总览。

- **档 0 / svg-primary**：无 `math` 且 `pptx_text_fit.py` 无换行/溢出/缺字/错位报告。SVG 即验收，不开 PowerPoint。
- **档 1 / pptx-triggered**：含 `math` 或静态审计报结构风险。交付前原生渲染一次，只查公式越槽、意外换行、内容截断、元素错位。
- **档 2**：档 1 发现结构缺陷，批量修完最多再渲染一次；仍有问题写入交付说明，不无限循环。

不算缺陷：抗锯齿、笔画粗细、标点亚像素差、基线 ±1px、字距 ±0.5px、整体色彩管理差异。算缺陷：内容缺失、换行变化、溢出、公式越槽、元素错位超 3px。

#### PowerPoint 安全规则

PPTX 原生渲染只能调 `python scripts/render_pptx.py figure-task/out/editable.pptx --out figure-task/out/pptx_render`。

- 禁止手写 `PowerPoint.Application` 自动化；禁止附着态调用 `Quit()`；禁止 `taskkill /IM POWERPNT.EXE`、`Stop-Process POWERPNT`。
- 检测到用户正在使用 PowerPoint 时脚本默认拒绝；只有用户同意（含勘察时的预授权）才加 `--allow-attach`。
- 附着态只关自己只读打开的 Presentation。未完成要求中的原生渲染时交付说明写“原生渲染暂缓”，不得伪称完成。

## Crop Window Check

每个 `decision: "crop"` 资产必须有 `crop_window: clean | clean-on-fill | contaminated` 判定，默认证据来自 `snap_report.json`，人工只复看脚本点名项。`clean`：窗口余量是画布底色。`clean-on-fill`：余量是单一均匀实色且四边与邻居有净空，manifest 用同色重画承载面。`contaminated`：不得继续 crop，改 `regenerate-chroma`（需独立存在）或 `flatten`（位于清版区域）。`quality_audit.py` 的事后核验保留为兜底。

## AI 清版与再生

含待编辑前景的连续视觉场（照片、地图、插画、纹理）走区域 `ai-clean-plate`，细则见 `references/background_reconstruction.md` 与 `references/image_generation.md`；被压盖且需独立存在的对象走 `regenerate-chroma`（`references/chroma_regeneration.md`），可用于任意区域，不依赖全图清版。禁止 rembg/GrabCut/阈值抠图。无可用图像后端或底板不合格时停止并报告，不静默降级。

## 输出包

`editable.svg`、`editable_embedded.svg`、`editable.pptx`、`preview.png`、`manifest.json`、`contact_sheet.png`（有素材时）、`quality_report.md`、`editability_report.md`、`assets/`、`diagnostics/`、`timings.json`。PPTX 语义级顶层解组：文字、形状、连接线、素材可直接选中；公式、蒙版、旋转等按保真需要保持成组。

## 权威与职责

| 关注点 | 唯一权威 |
|---|---|
| 总流程、重绘门槛、验证分档、PowerPoint 安全 | 本 `SKILL.md` |
| 勘察协议、对象清单、`reconstruction_plan` | `references/routing.md` |
| manifest 字段 | `references/manifest_spec.md` |
| 背景与前景深度 | `references/background_reconstruction.md` |
| 元素语义 | `references/element_decision_matrix.md` |
| crop 执行语义 | `references/asset_extraction.md` |
| chroma 再生 | `references/chroma_regeneration.md` |
| 最终放行条件 | `references/quality_checklist.md` |

## 入口脚本

- `prepare_measurements.py`：一次性 OCR/风格证据
- `snap_boxes.py`：粗框吸附、净空量测、裁剪窗判定
- `inspect_regions.py`：异常项 1:1 放大
- `manifest_edit.py`：批量修改 manifest（带备份与自动校验）
- `compose_svg_package.py`：分阶段或全量合成
- `fit_text.py` / `pptx_text_fit.py`：文字槽位拟合 / PPTX 结构风险静态报告
- `render_pptx.py`：安全的原生渲染
- `crop_assets.py`、`probe_palette.py`、`chroma_key.py`、`slice_grid.py`、`check_plate_registration.py`：裁剪与再生链
- `audit_editability.py`、`quality_audit.py`、`validate_manifest.py`：审计与校验

## 质量底线

保留源图全部重要信息、阅读关系和专有视觉；普通文字和每个检出公式保持可编辑；无检测噪声、公式文字泄漏、脏裁剪、源图补丁拼贴或静默路线降级。完整放行条件见 `references/quality_checklist.md`。
