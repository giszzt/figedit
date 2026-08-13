# 图像生成（Image Generation）

本文件是「怎么调图像模型」的唯一权威，涵盖生成简报的写法与后端选择、调用协议。在任一 `background_regions[].strategy` 选定 `ai-clean-plate`、任一素材选定 `regenerate-chroma`，或用户明确要求 AI 辅助图像编辑时读本文件。

FigEdit 决定区域和素材路线。图像后端只执行已批准的清版或 chroma 简报，不参与路由。

## 目的

决定可编辑重建需要什么的是 FigEdit，不是图像模型。调用图像后端前，先检视源图并写一份结构化生成简报。图像模型收到的是精确的编辑说明书，不是"把所有字都去掉"的泛泛请求。

源图含公式、代码、手写、低对比方程、UI 微缩文字或嵌在背景里的示意字形时，读 `background_reconstruction.md` 的文字层策略一节。

## 生成简报

以下字段记入对应的 `background_plans[].generation_brief`。局部连续场只描述该 `scope_id` 与 `source_region`，不要把其他确定性 SVG 区域一起重绘。

### Task（任务）

声明参考图要被转换为一张干净视觉底板，供后续可编辑标注叠层使用。明确这不是重新设计。

把它框定为**对所附源图的清理编辑**，不是生成新场景。照片类写 "Remove the typographic overlay and translucent color bands from this photograph and reconstruct the pixels they covered, keeping the photograph otherwise unchanged."。插画或技术信息图写 "Remove the foreground labels, arrows, and annotation marks from this provided illustration and reconstruct the covered background pixels while keeping the composition, objects, color zones, and visual style unchanged."。这个编辑式框定是让支持参考图的后端专注于清版修复而非重新设计的关键。

### Preserve（保留）

列出必须保持不变的每个主要对象和视觉关系：

- 对象身份和数量
- 左中右位置
- 视角、朝向、姿态和比例
- 重叠和深度次序
- 画布边缘的裁切
- 背景色场、纹理、光照、阴影和颗粒
- 源图分析判定为融入式视觉内容（而非可编辑前景）的背景铭刻：公式、代码、手写、图轴刻度、示意字形场
- 为后续标签预留的有意空区

用具体的源图描述。不要只写"保持构图"。

### Preserve Background Inscriptions（保留背景铭刻）

列出经源图分析后应在生成底板中保持栅格化的类文字内容：

- 技术背景里的淡色方程
- 嵌在对象内部的代码窗格、终端文字或数据表
- 低对比图表字形和图注记号
- 作为视觉纹理的手写涂写或公式

它们不因看起来像公式或代码就自动保留。只在其视觉角色是背景氛围、图形表面细节或低编辑价值语境时保留。要求模型保持其视觉密度、位置和源图气质，同时避免生成新的可读幻觉词。

### Remove（移除）

列出必须消失的所有内容：

- 标题、图注、正文和标签
- 引线、箭头、圆点、括号、图例和标记
- 仅当重建会替换它们时才移除的 logo 或日期
- 穿过视觉对象的标注碎片
- 源图中不存在的伪文字或意外字形样标记

除非源图分析确认没有值得保留的类文字内容，不要写 "remove all text"。

### Reconstruct（重建）

描述被遮像素如何补全：

- 在被移除标记之下延续对象的材质、纹理或结构
- 延续局部渐变或背景颗粒
- 保持合理的遮挡和阴影
- 在后续放置可编辑文字的位置留出干净负空间

不要因为文字穿过某个对象就指示模型抹掉该对象。

### Constraints（约束）

声明不允许发生的事：

- 不重新设计或美化
- 不加新对象
- 不缺失主要对象
- 不重复零件
- 不改变机位或朝向
- 不发明标签、符号、logo 或伪文字
- 不抹掉已声明保留的类文字背景铭刻
- 不加边框、画框、水印或装饰字
- 不发明超出允许保真级别的科学或技术细节

### Output（输出）

指定：

- 与源图相同的宽高比和横竖方向
- 满幅底板，无边距
- 除非支持，不要求 alpha
- 目标保真：`layout-locked` 或 `approximate`
- 后续可编辑叠层所需的干净区域

**固定画幅后端的拉伸补偿措辞**（后端恒返固定画幅并重新取景时使用，见 `image_generation.md` 的 Fixed-Aspect Backends）：参考图已被非等比拉伸成后端原生画幅，OUTPUT 段必须写明照抄拉伸几何：

```text
OUTPUT:
- The reference image has been deliberately stretched (non-uniformly scaled)
  to fit this canvas. Reproduce this exact stretched geometry as-is.
- Do NOT correct the proportions, do NOT re-frame or re-compose the scene,
  do NOT add letterboxing or black bars.
- Every object must stay at the same position in the stretched coordinate
  space as in the reference.
```

生成后把结果压回源区域原始宽高，并用 `check_plate_registration.py` 验证配准。

### Reject（拒收）

生成前写好候选拒收条件。至少包含：

- 残留文字或标注痕迹
- 已声明保留的背景公式、代码或字形场缺失或被过度抹平
- 主要对象缺失、重复或实质性改变
- 破坏后续标签放置的构图漂移（含配准检查不通过的重新取景）
- 生成的伪文字
- 宽高比改变或加了边距

## 提示词构造

用带标签分段的英文提示词：

```text
TASK:
...

PRESERVE EXACTLY:
- ...

PRESERVE BACKGROUND INSCRIPTIONS:
- ...

REMOVE COMPLETELY:
- ...

RECONSTRUCT:
- ...

DO NOT:
- ...

OUTPUT:
- ...
```

图像后端各不相同，但简报与模型无关。后端适配的调整与语义简报分开存放。

简报写好后，下一步是真实的图像生成调用。**不要把简报转译成本地脚本去涂抹、模糊、填充、克隆或修补源像素。**本地脚本只能准备蒙版或复制已验收的生成文件。跨提供商保持同一份生成简报；记录后端、模型、提交的提示词、任务实际收到的参考、请求与实际宽高比、输出路径、失败或拒收原因。

## 参考图策略


完整源图作首要参考。可选的附加参考：

- 显示移除区域的蒙版叠加图
- 必须保持可辨识的主要对象的裁剪
- 源图压缩严重时的纯色/纹理参考

除非有意重新设计，不提供无关风格参考。

## 候选复查

组装可编辑图形前检查清版底：

1. 比对主要对象的数量、位置、朝向和轮廓。
2. 确认将被重建的前景标签、引线和图例已消失。
3. 确认已声明的背景铭刻仍视觉存在。
4. 全图扫描发明的伪文字或重复标签。
5. 高倍放大检查原标注穿越处。
6. 核实空标签区和整体色彩平衡。
7. 记录被接受的偏差和拒收原因。

只有验收的候选才能成为 `plate_asset_id`。

简报写好后按以下各节选后端并调用。

## API Key 配置

可脚本后端从环境变量读 key，skill 会自动把 dotenv 文件载入环境：把 skill 根目录的 `env.example` 复制为 `.env`，填上你有的 key 即可。真实环境变量优先于文件；`.env` 已被 gitignore，绝不提交或分享。`scripts/api_keys.py` 是加载器，直接运行它可以查看文件提供了哪些 key。

实用提示：Labnana GPT-Image-2 返回无损 PNG，键控比返回 JPEG 的后端更干净（chroma 边缘压缩伪影更少）——这也是它在可脚本顺序里排第一的原因之一。

## 后端选择

用第一个可用且成功的、支持参考图的图像编辑路径。**碰任何可脚本后端之前，先盘点自己的工具**：agent 环境若有接受参考图的内置图像生成/编辑能力（Codex Image Gen、自带图像工具、图像 MCP），那就是路线 1，必须先试。`generate_clean_plate.py --precheck` 只报告可脚本后备——precheck 为正不是跳过这一步的许可。

1. **内置 agent 图像工具（如 Codex `image_gen`）**。只要 agent 有任何内置图像生成/编辑工具就先用它，即使其参数表没有参考图或输出路径选项。内置工具通过多模态对话上下文接收参考，不通过参数。调用协议：

   1. **先把源图显示进对话**（Codex 用 `view_image`，其他环境用等价方式把图展示给模型）。这使源图成为可见的编辑目标。
   2. **然后调用图像工具。** 提示词必须明确声明刚显示的图是唯一编辑目标，"保留/移除/重建"简报要相对这张图来表述（"编辑这张图：移除……，保持……不变"），不能写成全新场景描述。
   3. **绝不用提示词里写文件路径代替第 1 步。** 提示词文本里的本地路径不传输像素；工具只看得见对话中可见的内容。
   4. **事后定位输出。** Codex `image_gen` 保存在 `~/.codex/generated_images/<session>/`；取最新文件复制进任务工作区。没有输出路径参数是常态，不是缺陷。

   资格按**结果**判断，不按参数表判断：只要源图能在调用前显示、产物位图能在调用后定位，工具就有资格。"内置工具没有可控的参考/保存参数"从来不是下沉到可脚本后端的正当理由——这个具体的合理化说辞以前就造成过错误下沉；参考图走显示的图片进去，不走参数。只有实际调用尝试失败后才下沉（工具不存在、调用报错、或所有候选未通过复查），下沉前记录失败。
2. **Labnana GPT-Image-2**。Codex 之外，或 Codex Image Gen 不可用/失败时，优先 Labnana `provider=openai` + `model=gpt-image-2`。它支持参考图生成/编辑，是首选的可脚本后备。
3. **Labnana Gemini / Nano Banana**。Labnana GPT-Image-2 不可用或失败时使用。尽后端允许保持源图宽高比。
4. **官方 API**。Labnana 不可用时，仅当当前环境具备所需 key、SDK/API 能力和参考图编辑支持时，直接用 OpenAI 或 Gemini 图像 API。

没有任何可用路线时，停下报告阻塞。请用户配置图像后端/API key，或批准非清版底路线。不要静默切换到本地涂抹、模糊、克隆、填充或 inpaint。

已配置的默认值能完成任务时，不要就模型、尺寸、宽高比或参考图找用户确认。只在没有后端配置、用户明确要求控制、或选择实质影响成本/版权/延迟/质量时才问。

除非用户明确要求或更高优先路线已失败且失败已记录，不要在 Codex Image Gen 或 Labnana GPT-Image-2 之前选 Nano Banana。

## 能力契约

清版底是对源图的编辑，不是一张新插画。后端只有具备以下能力才有资格：

- 接受原图作为参考或编辑输入
- 保持源图宽高比，误差足以支撑后续叠层对齐
- 返回可作视觉底层的整幅位图
- 遵循"保留/移除/重建"简报

纯文字生图对 `ai-clean-plate` 没有资格，因为它无法保持源图的特定构图。

## 固定画幅后端（Fixed-Aspect Backends）

部分后端忽略请求的宽高比，恒定返回固定画幅（实测有 2048×2048），且为填满画幅**重新取景**（换构图）而非拉伸；显式传非 `auto` 的宽高比参数会直接返回 HTTP 400。重新取景对清版底是致命的——重构图后源坐标全部失效；拉伸尚可用逆变换还原，重新取景不行。

遇到这类后端，把几何补偿放在提示词之外：

1. 把源区域**非等比缩放**成后端的原生画幅，作为参考图；
2. 提示词写明「参考图是拉伸过的，照抄这个拉伸几何，不要纠正比例，不要加黑边」；
3. 拿到结果后**压回**源区域的原始宽高。

不要试图用宽高比参数解决（只有 `auto` 可用；`generate_clean_plate.py --aspect-ratio` 必须留 `auto`），也不要接受一张重新取景的底板。压回后用 `check_plate_registration.py` 量化配准（对源区域和底板取结构 mask 暴力搜 scale/offset 的最大 IoU），通过标志是 scale ≈ 1.00、offset ≈ 0；明显偏离即判重新取景，拒收重生。

首次接入一个新后端时，先用一张明确非方形的源区域实测一次返回画幅与构图，再决定是否需要本补偿。不要采信文档。

## 提示词与参考图

调用前读 `image_generation.md`，基于实际源图写动态提示词。内容包括：

- 源图作为首要参考
- 保留清单
- 移除清单
- 重建指令
- 受保护的背景铭刻（如有）
- 与源图相同的宽高比和满幅输出要求
- 候选拒收标准

可选的附加参考：蒙版、移除区域叠加图、必须保持身份的对象的紧凑裁剪。除非用户要求重新设计，不要提供无关的风格参考。

## 可选适配器脚本

`scripts/generate_clean_plate.py` 是可选的可脚本后端适配器。它不是路线选择器，也无法调用 Codex Image Gen。使用前提：

- 路由已选定区域 `ai-clean-plate` 或素材 `regenerate-chroma`
- 生成简报已写入提示词文件
- 环境已配置合格的可脚本后端

`--backend auto` 时按此顺序检查：

1. `labnana-gpt-image-2`（`LABNANA_API_KEY`）
2. `labnana-nano-banana`（`LABNANA_API_KEY`）
3. `openai-official`（`OPENAI_API_KEY` + 本地 SDK/API 支持）
4. `gemini-official`（`GEMINI_API_KEY` 或 `GOOGLE_API_KEY`）
5. `configured-command`（`FIGEDIT_CLEAN_PLATE_CONFIG` 或 `--config`）

运行 `python scripts/generate_clean_plate.py --precheck` 查看已配置的可脚本路线。全新安装无后端时应报 `unavailable`；此时 agent 应使用 Codex Image Gen（如有），或请用户配置 key/后端。脚本可以提交请求、保存返回位图、写来源记录。它绝不能用本地模糊、克隆、填充或 OpenCV/PIL 修补来制造清版底。

## 来源记录

对验收的底板，记录：

- 使用的后端或工具
- 提交的提示词或提示词文件
- 实际提供的源参考
- 请求与实际的宽高比或输出尺寸
- 输出图路径
- 验收决定与候选复查笔记（含配准检查结果）

验收输出的路径必须与 manifest 中的背景底板素材一致。

## 失败处理

区分瞬时故障与参数故障。**任何失败先在同一后端原地重试 1 次**——实测存在瞬时 400 和 SSL EOF，一次重试即过。重试后仍 4xx 的属参数问题，继续重试无意义，先排查请求（常见原因：传了后端不接受的宽高比或尺寸取值，如非 `auto` 的 aspect-ratio）。5xx（502/504）属瞬时或后端过载，可再重试 1 次；同一后端连续 3 次失败视为不可用，此时才允许下沉到后备列表的下一个后端，并记录失败原因。不要因单次超时下沉，也不要对参数错误无限重试。

除非用户明确批准其他路线，以下情况视为阻塞：

- 没有支持参考图的后端可用
- 所有生成候选均未通过复查
- 宽高比漂移导致叠层无法对齐（含配准检查不通过的重新取景）
- 后端返回的是重新设计的图而非清版底
- 候选残留前景文字、幻觉文字或缺失主要对象

不要把失败的 AI 清版底路线改口为常规路线。不要把仍带着待移除前景的未处理源图当清版底用。
