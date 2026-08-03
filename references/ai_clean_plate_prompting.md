# AI 清版底提示词（AI Clean Plate Prompting）

## 目的

决定可编辑重建需要什么的是 FigEdit，不是图像模型。调用图像后端前，先检视源图并写一份结构化生成简报。图像模型收到的是精确的编辑说明书，不是"把所有字都去掉"的泛泛请求。

源图含公式、代码、手写、低对比方程、UI 微缩文字或嵌在背景里的示意字形时，读 `text_layer_policy.md`。

向图像后端提交简报前，读 `image_backend_policy.md`。

## 生成简报

以下字段记入 `background_plan.generation_brief`。

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

**固定画幅后端的拉伸补偿措辞**（后端恒返固定画幅并重新取景时使用，见 `image_backend_policy.md` 的 Fixed-Aspect Backends）：参考图已被非等比拉伸成后端原生画幅，OUTPUT 段必须写明照抄拉伸几何：

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

## 后端路由

用 `image_backend_policy.md` 选择和调用后端。在 Codex 环境先试 `image_gen` / 内置图像编辑，遵循那里的内置调用协议：先把源图显示进对话使其成为可见编辑目标，再以"刚显示的图是唯一编辑目标"的提示词调用。参考图通过对话上下文传递，不通过工具参数，所以参数表没有参考选项不构成下沉理由。可脚本后备顺序是 Labnana GPT-Image-2、Labnana Gemini/Nano Banana、官方 OpenAI/Gemini API、已配置命令适配器。跨提供商保持同一份生成简报。记录后端、模型、提交的提示词、任务实际收到的参考、请求与实际宽高比、输出路径、失败或拒收原因。

简报写好后，下一步是真实的图像生成调用。不要把简报转译成本地脚本去涂抹、模糊、填充、克隆或修补源像素。本地脚本只能准备蒙版或复制已验收的生成文件。

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
