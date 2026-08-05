---
name: figedit-v2
description: 将位图图形重建为高保真可编辑 SVG 与原生 PowerPoint，支持仅文字可编辑、文字/结构/公式可编辑、源图素材保真混合、选择性或完整前景拆分，以及复杂连续背景的 AI 清版底重建。当用户希望把截图、论文插图、流程图、架构图、信息图、UI、图表/地图、海报或封面转成可编辑图形，或提到“图片转可编辑 SVG/PPT”“仅文字可编辑”“图表重建”“FigEdit”时使用。
---

# FigEdit

把不可编辑的位图图形重建为高保真、可维护、可继续编辑的 SVG 与原生 PPTX 包。

**核心管线**：`用户要求 + 源图整图 → 区域/素材组合路由 → 必要的用户检查点 → 只补缺失证据 → 批量 manifest/资产 → SVG 主验收 → 条件式 PPTX 验证 → 打包`

## 核心原则

**整图先判、区域组合、批量执行、异常细查。**第一次查看源图时，同时判断编辑深度、默认 SVG 区域、局部或全图连续视觉场、素材身份与可分离性、明显污染、用户检查点和验证档位。不要用一个全局二选一标签替代区域和素材决策，也不得为每个元素单独制造视觉证明。

目标不是全部矢量化、全部裁剪或全部交给 AI：

- 结构性元素重画为可编辑 SVG 形状。
- 可读标签重打为可编辑 SVG 文字。
- 公式规范化为 `math`，并导出为可编辑 Office Math。
- 源图专有视觉先保真，再按可分离性选择裁剪、再生或压平；源图专有不等于可裁剪。
- 局部或全图连续场中存在待编辑前景时走区域 AI 清版底；不得静默整区裁剪。

OCR、像素量测和质量脚本只提供证据或执行已定决策，不替模型决定最终内容。

## 工作位置

所有命令在用户项目目录运行，不在 skill 目录运行。每张图建立任务目录，以 `figure-task/work` 保存证据、`figure-task/out` 保存交付包。绝不把运行产物写回 skill 目录。Windows 命令参数使用正斜杠；非 ASCII 路径先由文件系统发现并验证。

## 默认工作流

### 1. Global Reconstruction Read

在运行 OCR、测量或局部裁图前先查看一次足够清晰的源图，并结合用户原话形成全局路由锁。权威规则见 `references/global_routing.md`。

一次整图必须形成 Route Decision v2：

- `editability_depth`：`text-only`、`text+structure`、`selective-assets` 或 `full-extract`。
- `base_strategy: svg-rebuild` 与 `background_scopes`：局部/全图 `ai-clean-plate`，或内部无需编辑的 `self-contained-raster` 保留；含待编辑前景的连续场只有用户明确接受时才可 `source-preserve-region`。
- `asset_groups`：按 `redraw`、`crop`、`regenerate-chroma`、`flatten`、`preserve-raster` 或有理由的 `omit` 批量分组；每组同时写 `separability`，污染组写 `observed_overlap`。
- `route_status`：`ready` 或 `needs-user-input`；后者必须停止。
- `unresolved_decisions`：需要用户选择的前景深度；已知污染不得放进这里。
- `exception_ids`：整图证据不足或高风险的区域。
- `validation_tier`：`svg-primary` 或 `pptx-triggered`。

用户指令优先。**仅当**用户说“仅文字可编辑/只改文字/翻译文字”并锁定 `text-only` 时，AI 清版区域才直接对应 `flatten`，无需再次询问前景深度；不是“选了清版就自动 flatten”。用户说“所有对象都要可移动/可替换”锁定 `full-extract`；点名对象锁定 `selective`。只有用户没有表达编辑深度，且不同选择会显著改变费用或交付能力时才提问。

用户未说明编辑深度但检出公式时，默认 `text+structure`，公式写成可编辑 `math`，验证档位锁定 `pptx-triggered`。用户已明确 `text-only` 时不扩大结构重画范围，但公式仍保持可编辑，除非用户明确允许压平。

把组合结论写入 manifest 顶层 `route_decision`。连续场的初始前景模式写在 `background_scopes`；用户确认后，最终生成与验收记录写入 `background_plans[]`，通过 `scope_id` 关联。

视觉对象的路线按“身份 × 可分离性 × 编辑价值”决定：通用结构重画；源图专有且窗口干净才裁剪；明显压盖且需要独立存在的对象直接 `regenerate-chroma`；不需独立移动且位于清版区域的对象 `flatten`。先在整图上做负向污染扫描：轮廓被文字/边框/箭头/邻居穿过、外接矩形含异物、与圆角/阴影/纹理相交或对象自身缺损，任一成立即不是干净裁剪。明显污染是已知决策，不是等待后续裁剪验证的异常项。

同源图历史 manifest 只能复用文字、公式、面板边界和已验证坐标。重新计算 `route_decision`、背景计划、资产 decision/crop_window 和质量状态；不得因哈希相同沿用旧路线。

### 2. 一次性准备证据

只有 `route_status: ready` 且 `unresolved_decisions` 为空后才运行：

```powershell
python scripts/prepare_measurements.py input.png --out figure-task/work
```

保留 `draft_manifest.json` 中的 `diagnostics.measurement_workspace`，但不要把草稿 manifest 或 OCR 候选整批倒入最终 `elements`。

只读取会改变 manifest 的证据：低置信文字、公式/断行、坐标冲突和 `exception_ids`。高置信普通标签不逐框打开；颜色、尺寸和边界占用能由报告回答时不看图。需要局部证据时统一调用：

```powershell
python scripts/inspect_regions.py input.png --boxes figure-task/work/exceptions.json --out figure-task/work/exceptions.png --report figure-task/work/exceptions.json.report.json
```

### 3. 编写 manifest 与路线专属资产

每个任务必读：

- `references/manifest_spec.md`
- `references/svg_authoring.md`
- `references/quality_checklist.md`

逻辑门在整图总判中同时评估，细则按需加载：

- 公式或行内数学：`references/formula-reconstruction.md`
- 非文字视觉对象：`references/element_decision_matrix.md`
- 裁剪素材：`references/asset_extraction.md`
- 重画与保素材边界拿不准：`references/asset_preservation_policy.md`
- 陌生或混合图形：`references/taxonomy.md` 与 `references/workflow.md`
- 连续背景、局部地图/照片/插画区域或背景路线未决：`references/background_reconstruction.md`
- `ai-clean-plate`：另读 `references/ai_clean_plate_prompting.md` 与 `references/image_backend_policy.md`
- `regenerate-chroma`：`references/chroma_regeneration.md` 与 `references/image_backend_policy.md`
- crop 窗口为 contaminated 或 clean-on-fill 不成立：`references/contaminated_asset_recovery.md`
- 连续视觉场中的文字：`references/text_layer_policy.md`

#### 元素表达摘要

- 面板、卡片、边框、网格、简单标记、箭头和连接线：`redraw`。
- 标签、标题、图注和注释：`retype`；公式片段拆成独立 `math`。
- 截图、地图、照片、图表主体、logo、缩略图和源图专有视觉：先判断区域内部是否需要编辑，再按可分离性 `crop`、`regenerate-chroma`、`flatten` 或经用户确认 `preserve-raster`。
- 图表/地图/截图内部小字默认留在位图中，除非用户要求其可编辑。

#### Crop Window Check

每个 `decision: "crop"` 资产必须记录 `crop_window: clean | clean-on-fill | contaminated`。**每个资产有判定，不等于每个资产单独出图。**一次整图总判和带 ID 的 contact sheet 可以覆盖整批；只有压盖、贴边、低对比、透明边、密集区域、整图看不清或质量报告点名项才独立 1:1 放大。

- `clean`：窗口除元素外只有画布底色。
- `clean-on-fill`：窗口余量是单一均匀实色，且 manifest 用同色重画承载面；对象完整轮廓与边框、圆角、阴影、渐变、连接线、标签和邻居之间四边都有可见净空。
- `contaminated`：先收缩/平移窗口；做不到则改 `regenerate-chroma`，或在无需独立编辑时 `flatten`。不得继续用 `crop` 交付。

批量裁剪后看一次 `contact_sheet.png`。全绿且无新告警时不再逐项回看源图。

#### AI 清版底检查点

背景可恢复性与前景深度以 `references/background_reconstruction.md` 为唯一权威。任何局部或全图连续场只要包含待编辑前景就进入 `ai-clean-plate` 区域。若用户原话没有锁定 `flatten/selective/full-extract`，在 OCR、裁剪和任何生成调用前呈现具体区域、对象清单、计费调用预算和推荐并等待选择。

清版底必须是对对应源区域的编辑：移除待重建前景并恢复其后像素，其余视觉场保持对齐和身份一致。`full-extract/selective` 的范围内对象从 chroma sheet 再生并键控，不从原图矩形裁剪，也不使用 rembg/GrabCut/临时阈值抠图。元素级 `regenerate-chroma` 也可用于普通 SVG 区域中的污染素材，不要求全图先进入清版路线。

没有可用图像后端或无法得到合格底板时停止并报告，不静默降级。

### 4. 分阶段合成

日常布局、文字、箭头或裁剪修复只跑 SVG 阶段：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg
```

SVG 冻结后导出原生 PPTX并运行静态回流审计：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage pptx
```

只更新证据、报告和打包元数据时：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage package
```

不带 `--stage` 保持全量兼容路径。修复阶段直接编辑 `manifest.json`，把独立告警收齐后一次修改、一次重跑；不要为每个元素写临时 patch 脚本或在每项之间 compose。

### 5. SVG 主验收与条件式 PPTX 验证

每次检查 `preview.png`、`quality_report.md`、`editability_report.md`、`diagnostics/placement_overlay.png`，以及路线专属的 contact sheet/清版底/chroma 报告。最终至少看一次 SVG 总览；报告点名后只复查受影响区和总览一致性。

验证分档：

- **档 0 / `svg-primary`**：无 `math`，`pptx_text_fit.py` 未报告换行、溢出、缺字或整体错位。SVG 预览即视觉验收；不打开 PowerPoint。
- **档 1 / `pptx-triggered`**：含 `math`，或静态审计报告结构风险。交付前原生渲染一次，只检查公式越槽、意外换行、内容截断、元素错位和碰撞。
- **档 2**：档 1 确认存在结构缺陷。批量修 manifest 后最多再渲染一次；仍有问题写入交付说明，不因字体观感无限循环。

以下不是缺陷，不触发重做：抗锯齿、笔画粗细、逗号/引号/括号亚像素差异、基线约 ±1 px、字距约 ±0.5 px、整体色彩管理差异。结构性缺失、换行变化、溢出、公式越槽或元素整体错位超过 3 px 才算缺陷。

#### PowerPoint 安全规则

PPTX 原生渲染只能调用：

```powershell
python scripts/render_pptx.py figure-task/out/editable.pptx --out figure-task/out/pptx_render
```

- 禁止现场手写 `PowerPoint.Application` 自动化。
- 禁止附着用户 PowerPoint 后调用 `Quit()`。
- 禁止 `taskkill /IM POWERPNT.EXE`、`Stop-Process POWERPNT` 或任何结束用户 PowerPoint 的命令。
- 检测到用户正在使用 PowerPoint 时，脚本默认拒绝；只有用户明确同意后才加 `--allow-attach`。
- 附着态只关闭脚本自己只读打开的 Presentation，不退出应用。
- 未完成要求中的原生渲染时，交付说明写“原生渲染暂缓”，不得伪称完成。

## 视觉注意力纪律

- 同一版本图像在没有新告警、没有未决问题时不重复打开。
- 一次源图整图负责总体路线；局部图不能反推或推翻全局路线，除非它提供了新事实。
- 路线专属产物各看一次：crop contact sheet、每批 clean plate/chroma sheet、最终 SVG preview。
- 每个元素都被覆盖检查，不等于每个元素都单独出图。
- 坐标、颜色、尺寸和文字宽度优先由脚本报告；视觉判断只处理语义、层级和真实异常。

## 输出包

完整交付包含：

- `editable.svg`、`editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `manifest.json`
- `contact_sheet.png`（实际有素材时）
- `quality_report.md`、`editability_report.md`
- `assets/`
- `diagnostics/placement_overlay.png`
- `diagnostics/visual_qa/`
- `timings.json`

PPTX 默认做语义级顶层解组：普通文字、形状、连接线和素材可直接选中；公式、蒙版、滤镜、旋转和显式原子组按保真需要保持成组。

## 权威与职责

| 关注点 | 唯一权威 |
|---|---|
| 总流程、整图总判、验证分档、PowerPoint 安全 | 本 `SKILL.md` |
| 全局路由与 `route_decision` | `references/global_routing.md` |
| manifest 字段 | `references/manifest_spec.md` |
| 背景与前景深度 | `references/background_reconstruction.md` |
| 元素语义 | `references/element_decision_matrix.md` |
| crop 语义与异常裁剪 | `references/asset_extraction.md` |
| chroma 再生 | `references/chroma_regeneration.md` |
| 最终放行条件 | `references/quality_checklist.md` |

模型负责整图路由、语义拆解、manifest、异常判断和最终视觉验收。OCR 提供文字候选和定位证据；图像后端执行已写好的清版底或 chroma 简报；脚本执行裁剪、合成、量测、导出和事后审计。任何脚本报告都不得取代模型对内容身份和视觉语义的判断。

## 入口脚本

- `prepare_measurements.py`：一次性 OCR/风格证据。
- `inspect_regions.py`：异常区域批量放大与量测。
- `compose_svg_package.py`：分阶段或全量合成。
- `fit_text.py`：按真实字体拟合文字槽位。
- `pptx_text_fit.py`：PPTX 文字结构风险静态报告。
- `render_pptx.py`：安全的 PowerPoint/LibreOffice 原生渲染。
- `crop_assets.py`：常规路线矩形裁剪。
- `probe_palette.py`、`chroma_key.py`、`slice_grid.py`：chroma 再生链。
- `check_plate_registration.py`：清版底配准。
- `visual_compare_qa.py`：报告式视觉差异。
- `audit_editability.py`、`quality_audit.py`、`validate_manifest.py`：可编辑性、质量和 schema 审计。

## 质量底线

保留源图全部重要信息、阅读关系和专有视觉；普通文字和每个检出公式保持可编辑；没有检测噪声、公式文字泄漏、脏裁剪、源图补丁拼贴或静默路线降级。减少的是重复证明和重型验证频率，不是信息完整性、裁剪语义、公式可编辑性或背景验收标准。完整放行条件见 `references/quality_checklist.md`。
