# 文字层策略（Text Layer Policy）

## 目的

按视觉角色和编辑价值给类文字内容分类。不要从复杂清版底上抹掉所有字符，也不要保留所有公式、代码或背景感的文字。移除、保留还是重建，由内容在源图中的功能决定。

## 文字类别

### 可编辑前景

从背景底板移除、重建为可编辑文字/math/形状：

- 标题和副标题
- 节点标签、标注、图注和图例
- 引线标签和标记标签
- 需要保持可读可编辑的轴标签或表格文字
- 用户可能作为内容编辑的公式
- 作为主要解释内容（而非视觉纹理）的代码片段、UI 标签或公式块

### 融入式背景铭刻

属于场景、纹理或视觉语义的一部分时保留在底板内：

- 写在黑板、玻璃、墙面、天空、全息或技术背景上的淡色公式
- 作为视觉对象存在的代码窗口、终端样片段和密集微缩文字
- 营造领域身份的示意字形、图表碎片、图轴刻度和数学涂写
- 不是主要标签的低对比或被部分遮挡的文字
- 精确可编辑性不如保留视觉密度重要的标记

这些铭刻可以保持栅格化。除非用户明确要求、或图形的含义依赖编辑它们，否则不需要变成可编辑。

### 看似背景但应可编辑

有些文字视觉上嵌入很深，仍应重建：

- 传达图形核心方法的大型可读公式块
- 作为核心数据或算法（而非氛围）展示的代码
- 印在图形对象内部、定义该对象的标签
- 支撑解读的表格数值、图表标签或地图名称
- 用户可能独立更新的任何铭刻

这些情况只有在区域能被干净修复时才从底板移除，然后重建为可编辑文字或 math。移除会损伤视觉对象时，保留栅格副本，必要时才加可编辑叠层。

### 应抑制的伪影

移除或避免生成：

- 模型发明的伪文字
- 源标签将被重建时的乱码前景标签
- 重复标签、水印样幻觉和随机字母簇
- 可见文字区域之外的源 OCR 噪声

## 判断线索

用这些线索给每个类文字区域分类：

- **阅读角色**：主要解释、标签、图例或数据值，倾向可编辑前景。
- **视觉融合**：低对比、部分遮挡、透视、光照、模糊、辉光或画在对象上，倾向留在底板。
- **编辑价值**：用户可能编辑的重建；氛围性密度的保留。
- **精确性**：公式/代码/数据的精确性重要就重建或源图裁剪保留；近似的技术纹理可以栅格化。
- **层次关系**：与引线、标记、节点、轴或图例相连的文字通常是前景，哪怕背景很复杂。
- **修复风险**：移除嵌入文字会损伤重要对象时，保留并记录取舍。

拿不准时，选损失源图含义更少的那边：氛围性标记保视觉密度，主要可读信息保可编辑重建。

## PPTX 字符集约束

交付目标包含 PPTX 时，优先使用 ASCII 直引号 `'` 和 `"`。不要为还原源图字形使用 U+2018 / U+2019 / U+201C / U+201D——PowerPoint 对当前字体缺字的字符执行字体回退，回退字体的字宽与主字体不一致，会在这些字符前后留下明显空档（实例："Sam's" 被渲染成 "Sam ´ s"）。其他易触发回退的字符同理：各类破折号、特殊空格、装饰性符号。

这类缺陷只在 PPTX 渲染中暴露，SVG 预览完全正常、查不出来。因此密集文本图必须实际导出 PPTX 并渲染核对，不能只看 SVG 预览。

## AI 清版底的提示词要求

文字密集源图的每个清版底提示词都必须包含源图专属的判断，不是固定规则：

- 要移除并重建的前景文字
- 要保留的融入式背景铭刻
- 要抑制的伪影文字
- 双向拒收标准：既拒"该保留的铭刻丢了"，也拒"发明了伪文字"

措辞示例：

```text
PRESERVE BACKGROUND INSCRIPTIONS:
- Keep only the source-classified background inscriptions, such as faint
  equations, code fragments, graph ticks, or schematic glyphs that function as
  background texture or pictorial detail. They may remain rasterized and do not
  need to be perfectly editable, but their density, placement, and visual role
  should stay close to the reference.

REMOVE FOREGROUND TEXT:
- Remove the main title, node labels, callout labels, legends, and any labels
  that will be rebuilt as editable overlays.

DO NOT:
- Do not remove the ambient formulas or code-like texture that was explicitly
  classified for preservation.
- Do not invent new readable words or random pseudo-text.
```

## Manifest 字段

决策记入 `background_plan.text_layer_policy`：

```json
{
  "editable_foreground": ["title", "node labels", "legend"],
  "preserve_in_plate": ["faint formulas at right", "code panel inside globe"],
  "suppress_or_reconstruct": ["model-invented pseudo-text", "garbled duplicate labels"],
  "ambiguous_handling": "preserve in plate unless it conflicts with editable overlays"
}
```

同一策略应体现在 `generation_brief.preserve`、`generation_brief.remove`、`generation_brief.constraints` 和 `generation_brief.reject_if` 中。
