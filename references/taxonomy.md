# 图形分类与重建模式（Figure Taxonomy and Reconstruction Modes）

## 分类维度

### 布局拓扑

选最接近的类别：

- `linear-flow`：有序序列，通常从左到右或从上到下
- `multi-column`：并列栏目或阶段
- `card-grid`：卡片或方块的模块化网格
- `panel-composite`：数个带内部子结构的大面板
- `radial-network`：中心节点加周边关系
- `hierarchical-tree`：父子或分支结构
- `ui-screen`：界面、仪表盘或软件样机
- `hand-drawn-explainer`：草图式讲解图
- `image-heavy-composite`：带叠层的海报、封面、社交卡片或视觉场景
- `mixed-complex`：多种拓扑混合

### 元素复杂度

- `low`：文字、方框、箭头、简单图标
- `medium`：文字、方框、箭头、图标、简单图表、小型示意图
- `high`：截图、地图、照片、密集缩略图、复杂图标、多层嵌套面板

### 风格类型

- `academic-grayscale`
- `academic-color`
- `benchmark-color`
- `flat-infographic`
- `hand-drawn`
- `ui-schematic`
- `technical-blueprint`
- `continuous-visual-field`
- `mixed-style`

### 重建意图

- `exact-layout`：严格保持布局
- `editable-layout`：优先可编辑性，视觉高度相似
- `asset-preserving-hybrid`：保留源图专有素材，同时提取文字/结构
- `clean-plate-plus-editable-overlay`：仅用 AI 修复不可恢复的连续背景
- `semantic-redraw`：保含义和关系，允许视觉整理
- `redesign`：保内容，改进视觉系统

## 重建模式

每种模式产出相同的包：可编辑 SVG（`editable.svg`、`editable_embedded.svg`）加原生 PowerPoint `editable.pptx`。模式只改变"重画矢量结构"与"保留位图素材"之间的配比。

### 模式 A：结构优先全矢量

使用条件：

- 元素以文字、线条、形状、箭头和简单图标为主
- 图形干净、结构化
- 用户要高可编辑性

典型配比：

- 以可编辑 SVG 为主
- 无或极少位图素材

例子：学术流程图、黑白工艺图、技术方法图、架构线图。

### 模式 B：保素材混合重建

使用条件：

- 图形含复杂视觉内容
- 结构和文字应保持可编辑
- 原始图标、象形图、插画、照片、截图、地图、缩略图或 logo 应保持视觉忠实
- 用通用矢量画替换源图专有对象会降低保真

典型配比：

- 可编辑 SVG 结构/文字
- 源图保留的位图素材
- 供裁剪复查的 contact sheet

例子：图像密集信息图、含地图或截图的图表、带示例图像的数据集图、含定制图形图标或手工视觉标记的图。

### 模式 C：逐面板重建

使用条件：

- 图形含多个大面板
- 每个面板内部布局各异
- 直接整幅重建难以管理

流程：

1. 识别外层面板边界。
2. 每个面板作为独立分组重建。
3. 在全局 SVG 中重新组装面板。
4. 统一字体、线宽和间距。

面板含定制图标、象形图、截图、地图、照片或缩略图时与模式 B 组合。

### 模式 D：语义重画

使用条件：

- 图形是手绘或强风格化的
- 原始边缘不规则
- 精确像素匹配不如清晰可编辑的含义重要
- 源图低分辨率或压缩严重

典型配比：

- 干净的可编辑 SVG
- 近似的风格保留
- 简化的形状和图标

源图专有 logo、截图、地图、证据图像或有辨识度的图标不要用模式 D，除非用户明确接受近似。

### 模式 E：AI 清版底背景混合

背景门选定 `ai-clean-plate` 时使用（权威判据在 `background_reconstruction.md`）：连续视觉场无法由简单图元或干净裁剪机械恢复，且前景标记遮住了其中的像素。

典型配比：

- 一张对齐画布的 AI 生成清版底
- 可编辑文字、公式、连接线和结构几何
- 按 `background_plan.foreground_mode` 提取的前景素材：chroma 再生的透明对象（full-extract/selective）或没有（flatten）
- 验收底板和再生素材的来源记录与候选复查

模式 E 用 `E-ai`。背景门到达 `ai-clean-plate` 类别就选它。源图已显示强 AI 路线信号时，不要等一次失败的 SVG 尝试之后再选。不要把本地蒙版修补的源图底板当模式 E 变体。

## 模式选择规则

- 图形以结构为主、源图专有图形素材少，用模式 A。
- 图形把可编辑结构和任何源图专有视觉素材结合时，默认模式 B。
- 图形有多个主要面板用模式 C；面板含定制图标、象形图、截图、地图、照片或缩略图时与 B 组合。
- 只有语义清晰和风格近似比精确源图保真更重要时才用模式 D。
- `background_reconstruction.md` 的背景门选定 `ai-clean-plate` 时用模式 E；不按密度、体裁或视觉观感选。
- 图形有大量看着定制或源图专有的图形图标时，不要当简单图标处理；用 B 或 C+B，除非背景本身需要 E。
- E 与 B 组合只用于少数真正需要干净独立源图裁剪的前景素材。
- 必要时组合模式，但路线说明保持简短、贴着视觉证据。
