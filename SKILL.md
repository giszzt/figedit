---
name: figedit-v2
description: 将位图图表重建为高保真可编辑的 SVG 与原生 PowerPoint 包。适用于截图、论文插图、流程图、架构图、信息图、UI 示意图、图表/地图、海报、封面等图像密集型技术图形，当标签、公式、结构、源图专有素材和复杂连续背景都需要以可用的可编辑性重建时使用。
---

# FigEdit

用本 skill 把不可编辑的位图图形重建为高保真可编辑图形包。以 FigEdit 基础工作流为默认路线，并为复杂连续背景增加一道额外的决策门。

目标不是"全部矢量化"、"全部裁剪"或"全部交给 AI"。把源图的每个部分路由到既保真又保留可用编辑性的表达方式：

- 结构性元素重画为可编辑 SVG 形状
- 可读标签重打为可编辑 SVG 文字
- 公式规范化为 `math` 元素和可编辑的 PowerPoint 公式
- 源图专有的位图视觉对象裁剪为素材，用 `image` 元素放置
- 密集图表、地图、截图、缩略图、图像证据一律裁剪保留，除非用户明确要求重建
- 复杂连续背景在"裁剪 + 简单确定性 SVG 无法忠实重建"时走 AI 清版底（clean plate）

OCR 与像素测量证据可以辅助定位和验证，但不决定什么进入最终 SVG。不要把 OCR 框或草稿 manifest 对象整批倒进最终包。

## 工作位置

所有命令都在用户的项目目录下执行，不在 skill 目录下执行。每张图在用户工作区建一个任务目录，所有中间产物和输出写在那里。绝不把运行产物写回 skill 目录。

下文示例使用 `figure-task/work` 存证据、`figure-task/out` 存最终包。

## 默认工作流

### 1. 准备测量证据

运行：

```powershell
python scripts/prepare_measurements.py input.png --out figure-task/work
```

脚本参数一律用正斜杠；结尾反斜杠会被部分 shell 吞掉。

产出：

- `ocr_results.json`
- `style_tokens.json`
- `draft_manifest.json`（其中 `diagnostics.measurement_workspace` 已指向本工作目录——**编写最终 manifest 时保留这个字段**，合成步骤靠它把 OCR 证据拷进产物包，缺了它可编辑性门会报 `unavailable`）
- `measurement_report.md`
- `diagnostics/ocr_overlay.png`
- `diagnostics/style_overlay.png`
- `assets/source.*`

这些文件只作证据使用。

OCR 默认使用 PaddleOCR 的 PP-OCRv6 medium 配置。小配置只用于快速草稿，不用于最终小字复核。OCR 从来不是标准答案：高置信混淆字、代码 token、中文形近字、公式符号都要对照源图核实。

### 2. 判定图形路线

编写 manifest 之前先看源图和诊断产物。先做语义路线分类；不要因为画面视觉密集就选 AI 背景路线，也不要因为"一个熟练的插画师能画出来"就拒绝它。问题只有一个：FigEdit 能否用简单 SVG 图元加干净源图裁剪可靠地重建它。

- **简单文字/形状图**：以标签、方框、箭头、网格和基础几何标记为主。通常重画结构、重打文字。
- **工作流、架构、方法或信息图复合体**：面板、文字、公式、连接线、图标、截图、logo、文档/文件夹图形、图形标记混排。逐面板拆解，套用下面的元素门。
- **截图、UI、地图、照片、图表、缩略图或密集视觉主体**：视觉主体整体保留为位图素材（除非用户明确要求数据级/可编辑重建），周边可读标签单独提取。
- **公式密集图**：所有公式和行内数学片段都走可编辑 `math` 重建，带源图 bbox 和基线约束，保证 SVG 和 PPTX 导出后公式仍在原视觉位置。
- **设计导向或图像密集图**：海报、封面、社交卡片、插画场景、渲染场景等标签落在连续视觉场上的图形。可能需要 AI 清版底，但由背景门按"背景可恢复性"判定，不按体裁判定。

参考文件按路线加载：

- 永远使用 `references/manifest_spec.md`、`references/svg_authoring.md`、`references/quality_checklist.md`。
- 图形类型陌生或混合时，读 `references/taxonomy.md` 和 `references/workflow.md`。
- 出现任何公式或行内数学时，读 `references/formula-reconstruction.md`。
- 出现任何图形性、位图、截图、logo、地图、图表主体、缩略图、头像、手绘对象、模型标记、文档/文件夹图形或源图专有图标时，读 `references/element_decision_matrix.md`、`references/asset_preservation_policy.md`、`references/asset_extraction.md`。
- **任一资产的裁剪窗判定（见下文 Crop Window Check）不是 clean 时，必读 `references/contaminated_asset_recovery.md` 和 `references/chroma_regeneration.md`。**
- 任何素材路由到 `regenerate-chroma`（被污染、被缠结或连续背景元素）时，读 `references/chroma_regeneration.md` 和 `references/image_backend_policy.md`。
- 背景不是明显机械可复现的，或标签/标记/素材落在连续视觉场上时，读 `references/background_reconstruction.md`。
- 背景门选择 `ai-clean-plate` 时，另读 `references/ai_clean_plate_prompting.md` 和 `references/image_backend_policy.md`。

### 3. 应用元素决策门

通过这些门决定每个重要元素，写出 manifest。各门是平级的，没有哪一个是万能的第一步。

#### 结构门（Structure Gate）

把结构性元素重画为可编辑 SVG 形状：

- 面板、卡片、边框、栏目标题、分隔线、标尺线、网格、表格边框
- 简单箭头、连接线、虚线框、括号、坐标轴、朴素几何标记
- 简单的纯色背景

用像素测量和 OCR 坐标作提示，不作自动事实。拒绝纹理线、压缩边缘、假箭头、重复排线和原始轮廓噪声。

#### 文字门（Text Gate）

把可读的标签、标题、图注、图例、轴标签、标注、普通注释重打为 SVG 文字。OCR 只是候选证据。不确定的文字在 manifest 里标注；不要因为 OCR 给了备选文字就照单接受。

对密集论文图、架构图、公式密集复合图，文字排位是重建的一部分，不是修饰性收尾。写最终文字元素之前，记录或推断小标签的源区域、断行、对齐锚点和基线。字符正确不等于标签完成；它必须放进同一个视觉槽位，在 SVG 预览和原生 PPTX 中都不与方框、箭头、公式、相邻标签碰撞。

#### 公式门（Formula Gate）

数学公式是一等语义对象。方程、不等式、分式、求和、希腊字母、上下标、递推式和行内数学片段一律写成带规范化 LaTeX 的 `math` 元素，绝不写成 `type: "text"` 里的公式字符串。

散文与公式混排的区域，把散文拆成 `text`，公式片段拆成相邻的独立 `math` 元素。定稿前扫描所有 text 元素找公式痕迹并修复泄漏。

公式可编辑性是核心要求。不要用"把公式裁成图"或"公式留成纯文本"来回避公式密度。可编辑公式放错位置的正确修法是更好的测量与布局控制：源图 bbox、宽高、字号、锚点、基线和局部碰撞检查。

PPTX 公式导出是双重要求：

- 公式必须成为可编辑的 Office Math 对象
- 该对象在 PowerPoint 回流后必须仍占据预期视觉槽位

如果 PowerPoint 的公式排版改变了大小、基线或间距，调整 manifest 重跑合成。不要因为 `editable.pptx.math_report.json` 显示转换成功就标记完成。

#### 位图素材门（Raster Asset Gate）

把源图专有的位图视觉对象裁剪为素材，包括图形性图标、logo、应用/模型标记、截图、地图、图表主体、缩略图、照片、UI 片段、头像、机器人、手绘道具、文档/文件夹图形和密集视觉示例。

不要用凭空发明的通用 SVG 替换源图专有视觉对象。只有对象明显是通用图元、或用户明确要求可编辑矢量化时才重画。拿不准就裁剪——但"裁剪"必须先通过下面的裁剪窗检查。

##### 裁剪窗检查（Crop Window Check）

坐标裁剪交付的是整个矩形窗口，不只是你想要的元素。看图决定每个资产的去向时，对着它问一个问题：**这个矩形窗口里，除了元素自身，还有没有别的东西？**

混进窗口的东西可能来自下方（元素压着填充卡片、描边框、渐变条、底纹、另一个资产），也可能来自旁边（元素形状不规整——L 形、斜置、细长、带出头部件——外接矩形圈进了邻近的图标、文字、连线、面板边框）。来源不重要，处置相同。逐资产用眼睛判定，三档：

- **clean** —— 窗口内非元素像素为画布底色，无任何邻居入侵。坐标裁剪安全。
- **clean-on-fill** —— 非元素像素为单一均匀实色，但该色不是画布底色（元素坐在纯色卡片中央）。仍可坐标裁剪，前提两条同时成立：manifest 用**采样到的同一实色**重画承载面，且窗口不压到卡片的边框、圆角或其他元素。任一条不满足，按 contaminated 处理。
- **contaminated** —— 窗口里有承载层杂色、渐变，或圈进了邻居前景。先试最便宜的修复：**收缩或挪动窗口**，能在不切掉元素本体的前提下排除入侵物，就用更紧的窗口裁。做不到则走 `regenerate-chroma`；若该对象无需独立移动，让它留在原位不提取。

这是肉眼判断，不需要跑任何脚本。拿不准的地方（承载色与画布底色极接近的浅色卡片、密集小图标）放大源图看，不要猜。把判定结果写进该资产的 `crop_window` 字段。只有 clean 与合规的 clean-on-fill 适用"拿不准就裁剪"；判定为 contaminated 却仍直接坐标裁剪的，属于交付缺陷。（`quality_audit.py` 的 `crop_window_consistency` 门会在事后对每个裁剪资产做像素核验兜底，与你的判定矛盾时报 review 附证据。）

##### 素材的两种获取方式

素材如何获得取决于路线，且只有两种方法——任何地方都没有显著性抠图（salient-object matting）。路线设定默认方法；用户的明确要求可以把任何单个素材送到另一种方法（例如为了更干净的边缘再生一个本可裁剪的素材，或保留用户偏爱的裁剪）：

- **常规路线——坐标裁剪。** 从源图裁出最小的有视觉意义的矩形（`crop_assets.py` 读取 manifest 的 `source_region`），周边标签、边框、箭头保持可编辑。不要把无关背景、旧标签、标注线或相邻对象拖进裁剪。素材作为矩形 `image` 放置；平底/白底/简单底上的素材完全不需要 alpha。截图、图表主体、地图、平底 logo，以及素材坐在可分离背景上的图形都默认走这条路。
- **AI 路线——先生成再键控。** 背景门选择 `ai-clean-plate` 且 `full-extract`/`selective` 时，前景完全不从原图裁剪。由支持参考图的图像模型把范围内元素复现在一张纯色 chroma 底 sheet 上（键色由 `probe_palette.py` 选定），再用 `chroma_key.py` + `slice_grid.py` 把每个元素分离为干净透明 PNG。"生成干净前景 sheet 再键控分离"是这条路线上范围内对象变成透明素材的唯一方式。记录 `decision: "regenerate-chroma"`、`asset_fidelity: "approximate-ok"` 和 `generation_provenance`。

万物皆可 AI 再生——照片、人物、插画、图标、徽章、logo、截图、图表、地图、复合对象——没有内容类别审批门；质量取决于模型和提示词，难对付的案例要的是更锋利的"保持原样"提示词，不是拒绝。整份前景清单放**一张 sheet**（`chroma_regeneration.md`），只有模型明显放不下或画不清时才拆分——"明显（visibly）"指你看过一张失败的成品，不是你预判它会失败。每个不同元素只再生一次，重复出现的用同一 `asset_id` 多次放置。绝不临时编写 GrabCut/差值/阈值/rembg 抠图脚本从自然背景里抠对象——AI 路线上 sheet 底色已知且键控精确；常规路线上矩形裁剪就够了。

#### 背景门（Background Gate）

在结构、文字、公式、素材各门认领完它们能忠实表达的内容之后应用本门。它只回答一个问题：

**FigEdit 基础混合路线（干净源图裁剪 + 简单确定性 SVG 图元）能否忠实重建背景场，而不要求模型发明或手绘场景像素？**

- **能：走常规 FigEdit 路线。** 不加 `background_plan`（除非用户明确要求 AI 路线）。结构和文字重画为 SVG，源图专有视觉裁剪为位图素材，逐面板混排。常规论文图、流程图、架构图、白底/浅底图、图表、地图、UI 截图，以及背景平整规则或机械可复现的图形都默认走这条路。
- **不能：走 `ai-clean-plate`。** 前景文字、标签、引线、标记或图标嵌在连续照片、插画、渲染、纹理、不规则/多区渐变、场景式信息图、杂志封面场、海报场景或技术场景中，裁剪 + 简单 SVG 无法揭示或复现被遮像素时使用。

本门决定的是默认值；用户用自己的话提出的路线要求在两个方向上都优先于本门——用户可以把常规图送去 `ai-clean-plate` 换取提取精度，也可以在听过保真代价后坚持让场景图走常规路线。记录 `route_decision.source: "user-directive"`，质量标准不变（见 `references/background_reconstruction.md` 的 User Route Directive）。

本门只关心背景可恢复性，不关心内容类别、视觉密度或体裁。手工重画场景不算忠实的 SVG 重建；近似的 SVG 风景是重新设计，不是高保真重建。本门的权威定义——可恢复性测试、强信号清单、底板通过后的前景策略——在 `references/background_reconstruction.md`；答案不是明显的"能"时就去读它。**本门同样不回答任何一个前景资产能否干净裁出：一张纯色底架构图完全可能背景走常规路线、而其中若干资产必须收窗或再生，后者由 Crop Window Check 逐资产判定，与本门相互独立。**

对 `ai-clean-plate`，清版底是一张完整的不可编辑视觉底层。它必须是**对源图的编辑：移除待重建的前景、重建其背后的像素，其余背景保持不变**——色调、渐变/雾带分区、纹理、星点/颗粒密度、光照和结构都与源图一致。它不是一张新场景：把背景重新合成为明显不同的场（雾带位置变了、星点密度变了、颜色重新风格化了）属于重新设计，必须拒收重生，尽管被遮区域的填充像素不可能逐像素一致。可编辑文字、`math` 和简单标记叠加在上面。`full-extract`/`selective` 下，范围内图形对象以透明素材形式来自生成的前景 sheet（绝不来自源图矩形裁剪）；`flatten` 下它们留在底板里。一张干净的压平底板胜过一堆脏源图裁剪拼贴。

生成底板之前，先做**前景深度决策**（Foreground Depth Decision，见 `background_reconstruction.md`）：full-extract（所有图形对象独立成素材）、selective（用户点名的子集）或 flatten（对象留在底板）。不同模式需要不同的底板，所以必须先定。**这是硬检查点：除非用户自己的话表明了深度偏好，否则停下来呈现选项——清单、每种模式换来什么、相对成本和时间（含具体的计费生成次数）、你的推荐——然后才允许任何生成调用。**图形特征只影响推荐，绝不允许替用户默默选择。把模式及其来源记入 `background_plan.foreground_mode` / `foreground_mode_source`。

如果选择了 `ai-clean-plate` 但没有可用或被认可的参考图像后端，停下报告阻塞。不要静默降级为常规重建、把未处理的源图当底板，或用本地模糊/克隆/inpaint 脚本伪造清版底。

#### 复合拆分规则

逐面板做语义拆解。不要因为面板密集就整体裁剪，也不要因为结构规整就整体重画。每个面板按功能拆：

- 结构外壳：重画
- 可读标签：重打
- 公式片段：`math`
- 流向关系：重画连接线
- 源图专有视觉证据：裁剪素材
- 复杂连续背景：仅当背景门要求时走 AI 清版底
- 图表/地图/截图内部小字：保留在位图里，除非用户需要可编辑

分层要小心：

- 画布填充和清版底放 `layer: background`。
- 位图证据放 `layer: assets`。
- 面板边框、方框边框放 `layer: panels`，`fill: none`。
- **压在**填充面板或卡片之上的位图素材（信息卡里的图标块、横幅上的徽章）放 `layer: icons`——它在 `panels` 之后绘制；`layer: assets` 在之前绘制，会被任何填充面板盖住。
- 箭头/连接线放 `layer: connectors`。
- 标签和渲染后的公式放 `layer: texts`。

绘制顺序是 background → assets → panels → connectors → sections → icons → texts → annotations（与 `build_svg_from_manifest.py` 的 `group_order` 一致：连接线画在图标之下，图标盖住线头）。不要把填充面板矩形画在图像素材之上，预览里会盖住素材。实操建议：元素显式写 `layer` 字段，不要依赖按类型推断的默认分组。

### 4. 合成 SVG 包

运行：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out
```

产出：

- `editable.svg`
- `editable_embedded.svg`
- `editable.pptx`
- `preview.png`
- `manifest.json`
- `contact_sheet.png`
- `quality_report.md`
- `editability_report.md`
- `assets/`
- `diagnostics/placement_overlay.png`
- `diagnostics/visual_qa/`（对照图、混合图、差异热力图、分块得分）

PPTX 是原生 DrawingML 导出。用户需要在 PowerPoint 里编辑时优先交付它。导出默认做语义级顶层解组：图层/布局分组被压平，文字、形状、连接线和裁剪素材可以直接选中；公式、蒙版、滤镜、旋转和显式原子分组保持成组以保真。

PowerPoint 对文本框和 Office Math 的回流可能不同于 SVG 预览。这是预期行为，必须验证。公式密集或小字密集的图，交付前检查导出的 PPTX 或其渲染预览，修复公式/文字漂移、溢出、基线偏移和碰撞。

### 5. 验证与修复

检查：

- `preview.png`
- `contact_sheet.png`
- 需要 PowerPoint 可编辑性时检查 `editable.pptx`
- 标签密集、公式多、文字/连线间距紧的图，做 PPTX 渲染视检
- `quality_report.md`
- `editability_report.md`
- `diagnostics/placement_overlay.png`
- `diagnostics/visual_qa/diff_heatmap.png` 与 `quality_report.md` 里的最差分块得分（仅报告：高差异分块是复查触发，不是自动失败）
- 使用 `regenerate-chroma` 时检查再生素材 contact sheet 和 `chroma_key` 报告（含 `component_hue_drift`）
- 使用 `ai-clean-plate` 时检查底板候选与提示词/来源记录

交付前对照 `references/quality_checklist.md` 修复；其高优先级失败条件一节是权威清单。最常见的阻塞项：面板缺失或箭头错误、检测/OCR 噪声进入最终 SVG、可编辑内容被烘进位图、公式样文字未拆成 `math`、源图专有视觉被通用重画替换或整体缺失（`Assets: 0` 且无书面理由）、裁剪被切边或被污染（裁剪窗混入承载层或邻居像素）、清版底被脏源图裁剪打补丁、以及未做视检的 PPTX 公式/密排文字。

## 职责分工

### 模型职责

- 分类图形路线和重建模式。
- 决定语义分组和阅读顺序。
- 逐元素门决定裁剪 / 重画 / 重打 / math。
- 逐资产做裁剪窗检查（肉眼判定），把结果写进 `crop_window`。
- 元素门考虑完之后才决定背景门。
- 编写最终 `manifest.json`。
- 保持最终 SVG 干净可读。

### PaddleOCR 职责

- 提供文字候选、包围盒和置信度。
- 帮助定位标签、估计字号。
- 标记低置信文字供复核。
- OCR 不是标准答案；对照源图核实。

### 图像生成职责

图像生成在背景门选择 `ai-clean-plate` 之后使用，或在用户自己的话要求 AI 生成路线时使用。它根据源图和模型撰写的"保留/移除/重建"简报产出被验收的清版底。

碰任何可脚本调用的后端之前，先盘点自己的工具：如果 agent 环境有内置图像生成/编辑工具（Codex `image_gen`、自带图像工具、图像 MCP），先用它。内置工具从可见的对话上下文接收参考图，不从参数接收：先把源图显示进对话（如 `view_image`）使其成为编辑目标，再调用工具并在提示词中指明"刚显示的这张图是唯一编辑目标"，然后从工具的保存位置取输出（Codex：`~/.codex/generated_images/<session>/`）。参数表里没有参考图或输出路径选项对内置工具是常态，绝不是跳过它的理由；完整协议在 `references/image_backend_policy.md`。只有内置工具确实不存在或实际调用失败时，才按该文件的顺序下沉到可脚本后端：Labnana GPT-Image-2 第一，Labnana Gemini/Nano Banana 第二，然后是官方 OpenAI/Gemini API 或已配置的命令适配器。`--precheck` 为正只说明可脚本后备存在，不是跳过内置工具的许可。后端适配器执行简报；它们不决定图形路线或前景素材策略。

## 质量标准

可接受的产出保留源图全部信息（标题、标签、面板、箭头、源图专有视觉），普通文字和每个检出公式在 SVG 与原生 PPTX 中都可编辑，PPTX 回流后位置不变，没有检测噪声、没有公式文字泄漏、没有可编辑内容被烘进位图。AI 清版底路线的交付物是一张干净视觉底板加可编辑前景叠层，绝不是源图块拼贴。完整验收维度见 `references/quality_checklist.md`。

合成后运行 `scripts/audit_editability.py manifest.json`。以下情况触发复查：

- OCR 证据可用时 text lift ratio 低于约 `0.45`
- 十几个以上疑似可编辑的 OCR 框困在素材内部
- 大量大素材带 `text_policy: review`

editability 门为 `unavailable` 表示 OCR 证据缺失、头号指标没有算出来——这不是通过：要么补上测量工作目录（`diagnostics.measurement_workspace`）重跑，要么人工核对没有可编辑文字被烘进位图。

## 参考文件

按路线和元素门加载：

- `references/manifest_spec.md`：manifest 字段参考。每个任务必用。
- `references/svg_authoring.md`：SVG 编写约定、分层与字体。每个任务必用。
- `references/quality_checklist.md`：交付前验证清单。每个任务必用。
- `references/workflow.md`：端到端重建工作流细节。复杂、陌生或混合路线时读。
- `references/taxonomy.md`：图形分类与重建模式。为陌生图形定重建方案前读。
- `references/formula-reconstruction.md`：完整 `math` 元素 schema 与行内数学拆分规则。出现公式或行内数学时必读。
- `references/element_decision_matrix.md`：元素级重画/裁剪/重打决策。图形同时含可编辑结构与非结构视觉对象时必读。
- `references/asset_preservation_policy.md`：源图视觉对象保留为位图素材的规则。图形含图标、logo、截图、缩略图、图形对象、地图、图表主体或源图专有标记时必读。
- `references/asset_extraction.md`：裁剪与素材边界验证规则。需要素材或判断位图/源图专有视觉能否安全重画时必读。
- `references/background_reconstruction.md`：背景门与 AI 清版底前景策略。连续视觉场可能无法用裁剪+SVG 恢复时读。
- `references/ai_clean_plate_prompting.md`：动态提示词框架。仅在选择 `ai-clean-plate` 时必读。
- `references/image_backend_policy.md`：环境中立的图像后端策略。仅在需要图像生成时必读。
- `references/chroma_regeneration.md`：被污染或被缠结素材的"再生-键控"流水线。任何素材路由到 `regenerate-chroma` 时必读。
- `references/contaminated_asset_recovery.md`：被标签、引线或邻居压盖的素材的恢复决策。Crop Window Check 判定 contaminated、或 clean-on-fill 的前提不满足时读。
- `references/text_layer_policy.md`：连续视觉场上的文字处理。源图在场景或底板上有公式、代码或密集文字时读。

## 脚本地图

- `scripts/prepare_measurements.py`：仅产出 OCR/风格证据。
- `scripts/compose_svg_package.py`：从模型撰写的 manifest 合成完整包。
- `scripts/crop_assets.py`：按 manifest 各资产的 `source_region` 从源图坐标裁剪矩形素材；常规路线的素材方法。
- `scripts/probe_palette.py`：为再生 sheet 选择键控色。整图模式保证键色远离源图色板（背景可分离）；`--boxes` 模式逐元素检查色相撞色并输出分 sheet 方案（前景不掉色）。走再生路线必须带 `--boxes` 在首次生成前跑。
- `scripts/chroma_key.py`：从再生 sheet 中键控掉纯色底；去除边缘污染、投影和封闭孔洞；报告边缘质量和逐连通域的 `component_hue_drift`（同色系元素被损伤的唯一检测器）。
- `scripts/slice_grid.py`：把键控后的 sheet 按连通域切成独立透明素材，吸收小的分离部件；多部件图标被切碎时用 `--cells` 按已知格子框重切。
- `scripts/check_plate_registration.py`：量化清版底与源区域的配准（scale/offset/IoU 暴力搜索）。判定"重新取景"的量化依据；通过标志是 scale ≈ 1.00、offset ≈ 0。
- `scripts/visual_compare_qa.py`：源图与预览的像素级对比（对照图、混合图、差异热力图、最差分块）；合成时自动运行，仅报告。
- `scripts/export_pptx_from_svg.py`：把 `editable.svg` 导出为原生 PPTX。
- `scripts/pptx_math.py`：把 manifest LaTeX 转换为可编辑的 PPTX Office Math。
- `scripts/formula_text_detection.py`：检测遗留在 text 元素里的公式样内容。
- `scripts/svg_to_pptx/`：内置 SVG 转 DrawingML 转换器。
- `scripts/svg_finalize/flatten_tspan.py`：PPTX 安全的多行 SVG 文字布局助手。
- `scripts/pptx_animations.py`：PPTX 转换器使用的可选过渡/动画 XML 助手。
- `scripts/audit_editability.py`：审计 text lift ratio、素材文字风险和 SVG 可编辑性；OCR 证据缺失时报 `unavailable`。
- `scripts/detect_ocr_paddle.py`：PaddleOCR 适配器。
- `scripts/sample_styles.py`：颜色/风格采样。
- `scripts/quality_audit.py`：XML/渲染/报告检查加按路线适配的复查门（含 `crop_window_consistency` 裁剪窗核验）。
- `scripts/validate_manifest.py`：manifest 校验。
- `scripts/generate_clean_plate.py`：可选的参考图后端适配器。仅在模型选定 `ai-clean-plate` 并写好提示词简报后使用。
- `scripts/prepare_clean_plate_mask.py`：可选的蒙版/叠加图准备工具。它不产出最终清版底。

`build_svg_from_manifest.py`、`embed_svg_assets.py`、`math_renderer.py`、`api_keys.py` 是被上述脚本导入的内部助手，不要直接运行。
