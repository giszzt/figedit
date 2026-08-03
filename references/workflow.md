# 重建工作流（Reconstruction Workflow）

## 1. 需求与意图

重建前先确定用户意图：

- 像素级忠实重建
- 可编辑结构重建
- 保素材混合重建
- 语义重画
- 出版清理或重新设计

用户未指明时，默认保素材混合重建。

背景感知重建是标准 FigEdit 工作流的扩展，不替代 OCR 复核、结构重画、公式重建、素材保留、原生 PPTX 导出和视觉修复。

## 2. 识别与测量

每张图在编写 manifest 前先跑 `scripts/prepare_measurements.py`。检视：

- OCR 候选和 `diagnostics/ocr_overlay.png`
- 采样的风格 token 和 `diagnostics/style_overlay.png`
- `measurement_report.md`
- `draft_manifest.json`（注意保留其中的 `diagnostics.measurement_workspace` 字段到最终 manifest）
- 拷贝到任务工作区的源图

诊断产物只用于测量和验证。不要把 `draft_manifest.json` 当最终 manifest 用。不要把 OCR 备选文字或任何检测器的原始候选整批导入 `elements`。

## 3. 图形分类

记录：

- 布局拓扑
- 内容复杂度
- 风格类型
- 重建模式
- 预期素材保真级别

类型陌生时用 `taxonomy.md`。默认路线始终是常规 FigEdit；背景路线只由 `background_reconstruction.md` 的背景门决定。

## 4. 建立清单

### 结构清单

面板、卡片、边框、表格/网格结构、分隔线、背景块、连接线、箭头。

默认决策：`redraw`。

### 文字与公式清单

标题、节标题、标签、注释、图例、图注、数学公式、方程和行内数学片段。

默认决策：普通散文标签 `retype`；含数学的片段用带规范化 LaTeX 的可编辑 `math`。密集图形先记录源槽位、基线和相邻碰撞约束再定最终位置。OCR 框只是提示；每个紧凑标签或公式都对照源图裁剪或分块核实。

### 素材清单

图标、象形图、插画、logo、地图、截图、缩略图、照片、手绘对象、模型输出、UI 片段和其他源图专有视觉。

默认决策：`crop`，除非对象通过 `asset_preservation_policy.md` 的重画资格测试。**每个 `crop` 决策先过 SKILL.md 的裁剪窗检查（Crop Window Check）**：肉眼判定窗口内除元素外还有没有别的东西（承载层、邻居），三档结果写进 `crop_window` 字段；contaminated 的先试收窗，不行走 `regenerate-chroma` 或留在原位。

不要因为源图专有图标、logo、截图、定制象形图、证据缩略图、技术符号或有辨识度的装饰标记小就重画。拿不准就裁剪（前提是裁剪窗干净）。

### 背景清单

识别前景文字和标记背后的视觉场：

- 纯色填充和简单单区渐变
- 干净的裁剪区域
- 照片、插画、渲染场景、纹理、颗粒、星点、地形、大气、水、云、辉光、光照、拼贴或绘画场
- 前景标签遮住未知像素的区域
- 可能是背景细节而非可编辑前景的类文字内容

然后问 `background_reconstruction.md` 的背景门问题：干净裁剪加简单确定性 SVG 能否在不发明场景像素的前提下忠实重建背景场？

## 5. 决定元素策略

应用这些门：

1. 公式门：公式和行内数学变 `math`。
2. 文字门：可读前景文字变 SVG 文字。
3. 结构门：面板、连接线、简单标记和图元重画。
4. 位图素材门：源图专有视觉在精确身份重要时裁剪（先过裁剪窗检查）。
5. 背景门：带前景叠层的连续场景背景在非机械可恢复时走 `ai-clean-plate`。

决策和理由记入 manifest。可选摘要保持简洁；不要把字段当仪式加。

## 6. 准备背景与素材

### 常规路线

无 `background_plan`。仅在背景机械可恢复时使用：普通 SVG 填充、简单规则渐变、测量几何区域或干净源图裁剪。正常准备素材：

- 建立源图包围盒
- 加 padding
- 按矩形裁到 `assets/`（`crop_assets.py`）；独立透明素材来自 chroma 再生（`chroma_regeneration.md`），不来自显著性抠图
- 记录目标位置
- 生成 contact sheet
- 核实裁剪没有切边、污染或缺失

### AI 清版底路线

在背景门选定 `ai-clean-plate` 后使用，或用户自己的话要求 AI 路线时使用（记录 `route_decision.source: "user-directive"`）。

1. 建前景清单并做前景深度决策（`background_reconstruction.md`）。这是硬检查点：除非用户自己的话表明深度偏好，停下呈现模式选项（含清单、具体计费调用数预算和推荐）再做任何生成调用。记录 `background_plan.foreground_mode` 和 `foreground_mode_source`。
2. 按 `ai_clean_plate_prompting.md` 写动态生成简报；移除清单与提取范围互为镜像。
3. 按 `image_backend_policy.md` 调用支持参考图的后端——agent 自己的内置图像工具优先，可脚本后端作后备。
4. 只验收移除了范围内前景、保留了声明视觉身份的整幅清版底；配准存疑时用 `check_plate_registration.py` 量化。
5. 把验收底板加为最底层背景素材。
6. 范围内前景对象在 chroma sheet 上再生并键控分离（`chroma_regeneration.md`）——先跑 `probe_palette.py --boxes` 分区，整份清单一张 sheet，只有单张明显失败才拆。不从原图裁这些对象，不跑显著性抠图或临时抠图脚本。
7. 叠加可编辑文字、公式、简单标记和提取的素材。

不要把大块矩形源图裁到底板上。不要把旧标签、引线或标注残留裁回最终输出。对象即使对再生来说也不可分离且编辑价值低时，留在清版底里。

产不出可接受的清版底时，报告阻塞，不静默降级。

## 7. 重建结构 SVG

绘制：

- 画布背景或清版底放置
- 面板轮廓
- 卡片和内容块
- 分隔线
- 箭头和连接线
- 表格/网格线
- 简单结构符号

使用语义分组和 ID。

## 8. 重打文字、重建公式

文字重打为 SVG 文字：

- 保持视觉层级
- 使用可读的备选字体
- 手动拆分长行
- 密集标签保住源区域适配、对齐和基线
- 不确定的文字在 manifest 标注

公式用 `type: "math"` 和规范化 `latex` 字符串。不要用纯文本近似公式，也不要为回避排位工作把公式裁成图。每个检出公式在 PPTX 中都应保持可编辑，除非用户对该项明确豁免。

公式密集或小字密集的图形：

1. 每个公式/文字元素放进测量好的源槽位
2. 渲染 SVG 预览并修复局部碰撞
3. 导出原生 PPTX
4. 检查或渲染 PPTX，修复 PowerPoint 特有的回流、基线和溢出问题

`pptx_math_export` 通过意味着公式可编辑；不证明 PowerPoint 排版视觉正确。

定稿前扫描文字元素找公式痕迹、OCR 伪影和备选垃圾。

## 9. 放置素材

用 `<image>` 元素放置裁剪素材。

- 保持宽高比。
- 只在必要时用蒙版或裁剪。
- 不拉伸素材，除非源图本身是拉伸的。
- 素材对齐重建的结构。
- 生成的素材标注为近似。
- 精确身份重要的源图专有素材保持源图原样。

## 10. 生成交付物

创建：

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `contact_sheet.png`
- `manifest.json`
- `quality_report.md`
- `editability_report.md`
- `assets/`

`editable.pptx` 是同一重建的原生 PowerPoint 导出。`pptx_math_export` 为 `ok` 时公式元素以可编辑 Office Math 对象呈现。PPTX 导出时普通图层/布局分组被压平，用户可直接选中文字、形状、连接线和裁剪素材；只保留为保真必须成组的显式原子组。

紧凑文字或公式布局要把 PPTX 导出当作另一个渲染目标，不是打包收尾。原生 PPT 文字和 Office Math 的回流可能不同于 SVG；修 manifest 直到两个交付物都可接受。

## 11. 验证与修复

用 `quality_checklist.md`。

修复顺序：

1. 泄漏进 SVG 的原始检测候选、OCR 备选文字或检测器噪声
2. 缺失信息
3. 错误结构或箭头方向
4. 缺失或被错误重画的源图专有素材
5. 被污染、切边、带光晕或错位的裁剪（含裁剪窗问题）
6. 背景路线错误、鬼影、接缝或源图块拼贴
7. 未复查的生成内容
8. 公式和文字可编辑性问题
9. SVG 或 PPTX 里的公式/文字排位问题
10. 视觉抛光
