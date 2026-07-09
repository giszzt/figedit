<div align="center">
  <img src="./assets/figedit-logo.png" alt="FigEdit 图易编 Logo" width="220">

  <h1>FigEdit · 图易编</h1>

  <p><strong>让压平的图，重新可编辑。</strong></p>

  <p>把截图、论文配图、流程图、海报和 AI 生成图片重建为可编辑 SVG 与原生 PowerPoint。</p>

  <p>
    <a href="./README.md">中文</a> ·
    <a href="./README.en.md">English</a>
  </p>

  <p>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+"></a>
    <a href="./VERSION"><img src="https://img.shields.io/badge/Version-0.2.0-2563EB?style=flat-square" alt="Version 0.2.0"></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-F97316?style=flat-square" alt="MIT License"></a>
  </p>

  <p>
    <a href="#效果案例">效果案例</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#工作原理">工作原理</a> ·
    <a href="./CHANGELOG.md">更新日志</a> ·
    <a href="#致谢与第三方代码">致谢</a>
  </p>
</div>

---

## 这是什么

FigEdit（中文名「图易编」）是一个 AI Agent Skill。给它一张截图、论文配图、AI 生成的幻灯片、技术架构图、海报封面、或者任何图片格式的图形，它会把图片拆解重建成可编辑的矢量图形包——文字变成真正的文字，形状变成矢量形状，公式变成可编辑的方程，图标和照片作为可替换的图片资产保留，连嵌在照片和插画里的文字，也能连同背景一起重建成可编辑的分层结构。

## 应用场景

**AI 生成的图片不能编辑？** — GPT Image 2、Nano Banana 生成的幻灯片、架构图画面惊艳，但全是像素。FigEdit 把布局提取成真正的 PowerPoint 元素，文本框能编辑、形状能移动、背景能替换。

**看到好看的论文图想复刻？** — 想复刻优质图示的图框、形状、布局、配色。FigEdit 把图重建成可编辑结构，30 秒改完标签、替换元素，不用从头画一小时。

**图片原始可编辑版本丢失？** — 设计师交付的精美信息图，可编辑源文件丢了或从未共享。FigEdit 拆成可编辑的 SVG，框架变矢量，图标保留为干净的裁切图，文字变成可选中的文本。

**文字长在照片和插画上？** — 海报、封面、社交卡片、场景化信息图，标题和标注直接压在连续的视觉画面上，裁切和矢量重绘都救不了。FigEdit 会让参考图模型生成一张擦除前景、补全背景的干净底板，再把文字、公式和标记作为可编辑图层叠回去。

## 效果案例

下面均为原图与 FigEdit 重建结果的对比。

### 案例一：PPT 结构拆解

![生成式 AI 发展史信息图的原图与重建结果](./assets/examples/01-slide-layout.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/genai-history/)

### 案例二：图标与结构混合图

![Skill Compiler 架构图的原图与重建结果](./assets/examples/02-icon-diagram.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/skill-compiler/)

### 案例三：全矢量重绘

![Parallel Loops 论文图的原图与重建结果](./assets/examples/03-vector-redraw.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/parallel-loops/)

### 案例四：大量图片资产裁切

![虚拟试衣数据流程图的原图与重建结果](./assets/examples/04-raster-assets.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/tryon-pipeline/)

### 案例五：多要素混合重构

![TransitBench 信息图的原图与重建结果](./assets/examples/05-mixed-reconstruction.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/transitlm/)

### 案例六：复杂公式复现

![包含大量公式的 AST 方法图原图与重建结果](./assets/examples/06-formula-reconstruction.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/ast-reveal/)

### 案例七：公式与图片资产混合重建

![Camera Grid Rendering 的原图与重建结果](./assets/examples/07-camera-grid-rendering.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/camera-grid-rendering/)

### 案例八：多分组数据图表重建

![LLM 性能评估图表的原图与重建结果](./assets/examples/08-llm-performance-evaluation.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/llm-performance-evaluation/)

### 案例九：复杂背景封面清版

![Sciscover 封面的原图与重建结果](./assets/examples/09-sciscover-cover.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/sciscover-cover/)

### 案例十：清版底板与全前景提取

![ESA ISS 信息图的原图与重建结果](./assets/examples/10-esa-iss-pillars.png)

[查看并下载完整案例：原图、SVG、PPTX、Manifest 与质量报告](./assets/examples/esa-iss-pillars/)

## 为什么用它？

把一张扁平图片变回可编辑文件，难点不只是识别画面里有什么，而是判断每个元素应该以什么形式保留，现有方案各有各的问题：

| 方案类型             | 代表方案                                                     | 核心做法                                                     | 主要优势                         | 主要不足                                                         |
| ---------------- | -------------------------------------------------------- | -------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------ |
| 轮廓拟合式矢量化         | Potrace、VTracer、Illustrator Image Trace                  | 根据像素颜色和边界拟合贝塞尔曲线，将整张图片转换为矢量路径                            | 速度快、成本低，适合 Logo、线稿、剪影和扁平图标   | 不理解文字、公式和元素关系；复杂图片容易产生大量碎片路径，虽然“全是矢量”，但实际很难编辑                |
| OCR 文本覆盖         | OCR 转 PPT、部分图片转幻灯片工具                                     | 保留原图或分块图片，在对应位置覆盖可编辑文本框                                  | 实现简单、视觉还原度较高，文字可以直接修改        | 图形和结构仍是位图；原文字可能残留在背景中，移动文本后容易露馅，只能算局部可编辑                     |
| 视觉理解与代码重建        | DrawIO、Excalidraw、TikZ、AutoFigure-Edit、Draw with Thought | 由多模态大模型理解图片，再生成 SVG、DrawIO、Excalidraw 或 TikZ 等结构代码       | 文字、节点、箭头和连接关系可编辑，适合规则流程图和架构图 | 代码表达能力偏向规则图形；自定义图标、Logo、照片、地图和截图容易被简化、遗漏或替换                  |
| 端到端 Image-to-SVG | StarVector、VFig、dots.mocr-svg、RLRF                       | 使用专门训练的模型，直接从图片生成完整 SVG 代码或矢量图元序列                        | 自动化程度高，可以输出路径级矢量对象           | 通常需要专用模型和 GPU；复杂图片会生成很长的 SVG，照片、纹理和专有视觉元素容易失真，模型泛化能力也受训练数据限制 |
| 元素分解与结构化组装       | Edit-Banana、CraftEditor                                  | 先通过sam分割、OCR、生成式清理等方法拆出文字和视觉元素，再组装成 DrawIO、SVG、PSD 等分层格式 | 能保留较丰富的视觉元素，也支持对象级移动、替换和重新组合 | 工作流太重，通常依赖多个模型、外部服务或 GPU 环境；对复杂图形还原能力不足                      |

FigEdit 采用混合重建策略：

- 文字、标题、普通标注重建为可编辑文本；
- 公式识别为独立的语义对象，并在原生 PPTX 中导出为可编辑的 Office Math 公式；
- 面板、形状、边框、箭头和连接关系重建为矢量对象；
- Logo、照片、截图、地图、复杂图标等来源特异的视觉内容，直接从原图裁切保留；
- 被标注、引线遮挡或与背景纠缠的图形对象，由参考图模型在色键底色上再生，色键抠出后成为干净的透明资产；
- 复杂连续背景（照片、插画、渲染场景、不规则渐变）重建为 AI 清版底板，其上叠加可编辑前景层；
- 最终同时输出 SVG、内嵌资产 SVG 和原生可编辑 PPTX。

装好依赖后，把图片交给 Agent，一句话即可完成分析、拆解、重建、导出和质量检查。

## 工作原理

整个流水线分四步：测量 → 决策 → 组装 → 验证。

### 测量

用 PaddleOCR 识别图中的文字位置和内容，用 OpenCV 检测线段、矩形、箭头等几何结构，同时采样配色和字体信息。最后产出原始测量数据，供下一步 Agent 决策使用。

### 决策

模型拿到测量数据后，对图做整体分类，然后逐个元素判断处理方式：

| 元素类型             | 处理方式                         |
| ---------------- | ---------------------------- |
| 面板、箭头、网格、分隔线     | 重绘为可编辑 SVG 形状                |
| 标签、标题、图注、图例      | 重打为可编辑文本                     |
| 方程、变量、行内公式       | 重建为 LaTeX，导出为可编辑 Office Math |
| 图标、照片、地图、图表、Logo | 从原图裁切，保留为可替换图片资产             |
| 被遮挡或纠缠的图形对象      | AI 在色键底上再生，抠出为干净透明资产         |
| 复杂连续背景           | 生成擦除前景、补全像素的 AI 清版底板         |

对于复杂图，模型还会选择重建策略：简单图全矢量，混合图走混合重建，多面板图逐面板拆解，手绘图走语义近似，背景不可恢复的图走清版底板加可编辑前景。策略可以组合。走清版路线时，模型会先给出前景处理方案（全部提取为独立资产、只提取指定对象、或保留在底板中压平）供确认，再发起生成。

所有决策写入 `manifest.json`，整个过程可复现。

### 组装

根据 manifest 生成最终输出：矢量结构、可编辑文本、渲染后的公式、定位好的图片资产、清版底板，一起打包成 SVG 和原生 PowerPoint 文件。

### 验证

自动检查输出质量：有没有面板漏掉、文字被意外困在图片里、公式转换是否成功、结构是否完整，并将重建结果与原图做像素级对比，输出差异热力图和分块评分定位偏差最大的区域。发现问题会自动修复后重新组装。

## 快速开始

### 环境要求

- Python 3.10+
- 一个支持 skill 的 AI Agent 环境

FigEdit 的重建质量高度依赖模型视觉理解与 SVG 绘制能力，不同模型表现差异极大，优先推荐 Codex、Claude Code。

| Agent 环境        | 推荐模型                               | 说明                                                                               |
| --------------- | ---------------------------------- | -------------------------------------------------------------------------------- |
| **Codex**       | GPT-5.5                            | 优先推荐，视觉理解、空间推理与工具调用能力较强，且自带 image_gen 图像生成，清版路线开箱即用                              |
| **Claude Code** | Claude Fable 5（次选Claude Opus 4.8）  | Claude Fable 5 ≥ GPT-5.5，可惜暂时下架了，Claude Opus 4.8亦可用，但复杂图转换效果不及GPT-5.5            |
| **其他主流 Agent**  | GPT-5.5、Claude Opus 4.8、Gemini 3.5 | 不建议使用仅擅长代码、但缺少图片输入或空间视觉推理能力的模型。即使能够执行 FigEdit 脚本，也容易在元素分类、裁切边界、层级关系和布局判断上出现明显偏差。 |

### 安装

**方式一：手动安装。** 克隆到 skill 目录，装好依赖：

```bash
# Codex
git clone https://github.com/giszzt/figedit.git ~/.codex/skills/figedit
# Claude Code
git clone https://github.com/giszzt/figedit.git ~/.claude/skills/figedit

# 安装 Python 依赖
pip install -r ~/.codex/skills/figedit/requirements.txt
```

**方式二：让 Agent 帮你装。** 把项目地址发给你的 Agent，说一句：

```
请帮我安装配置好这个 skill：
https://github.com/giszzt/figedit
```

### 图像后端配置（可选）

只有涉及 AI 清版底板或色键再生的图才需要图像生成能力，普通图不用配置任何密钥。

Agent 环境自带图像生成时（如 Codex 的内置 `image_gen`）会优先使用，零配置。没有内置能力时，把 `env.example` 复制为 `.env` 并填入你有的密钥即可，支持 Labnana（GPT-Image-2 / Gemini / Nano Banana）和 OpenAI、Gemini 官方 API，按可用性自动排序回退。`.env` 已被 `.gitignore` 排除，不会被提交。

### 使用

装好之后，在 Agent 里对任意图片说一句话就行，不用记命令。默认情况下模型会自己判断每个元素怎么处理、走哪条重建路线；你在指令里明确提出的要求（走哪条路线、哪个元素怎么处理）始终优先于默认判断。

**日常转换**，说清目的就够了：

```
把这张图转成可编辑的 SVG 包。
```

```
这张图我想改几个字，帮我转成能编辑的 PPT。
```

```
复刻这张论文图的版式、图框和配色，文字内容我之后自己替换。
```

**控制元素的处理方式**，点名某类元素怎么办：

```
请将这张图全矢量化，图标也重绘成可编辑形状。
```

```
图里的柱状图不要整块裁切，重建成可编辑的图表元素。
```

```
截图和地图保持裁切原图就行，只把周围的标题和标注做成可编辑文字。
```

```
左上角这个徽章裁切下来边缘总是脏的，用 AI 重新生成一个干净的透明版。
```

**指定重建路线**，两条路线可以按需交叉：

```
这张海报的字压在照片上，帮我拆成背景底板加可编辑文字。
```

```
这张图虽然是普通白底流程图，但我要最干净的提取效果，直接走 AI 清版路线。
```

```
走清版路线，把画面里所有图标和人物都抠成独立透明素材，方便我重新排版。
```

```
生成底板时只把中间的火箭抠出来单独成素材，其他都留在背景里压平。
```

```
这张带照片背景的图先别生成底板，就用常规裁切拼，效果差点我能接受。
```

模型会跑完整个流水线，把输出包交付到你的项目目录。

## 输出包

```
output/
├── editable.svg              # 可编辑 SVG，外链资产
├── editable_embedded.svg     # 自包含 SVG，资产 base64 内嵌
├── editable.pptx             # 原生 PowerPoint，真实文本框与形状
├── preview.png               # 预览图
├── contact_sheet.png         # 所有裁切资产一览
├── manifest.json             # 完整重建计划
├── quality_report.md         # 质量检查报告
├── editability_report.md     # 文本提取率与资产文本风险
├── assets/                   # 裁切、再生与底板图片资产
└── diagnostics/              # 布局叠加图与像素级视觉对比（差异热力图、分块评分）
```

## 项目结构

```
figedit/
├── SKILL.md            # Skill 入口，完整工作流参考
├── README.md
├── README.en.md
├── CHANGELOG.md
├── LICENSE
├── VERSION
├── THIRD_PARTY_NOTICES.md
├── requirements.txt
├── env.example         # 图像后端密钥模板（复制为 .env 使用）
├── scripts/            # 测量、组装、色键再生、PPTX 导出、审计等脚本
├── references/         # 决策参考文档（分类、决策矩阵、背景重建、清版提示词等）
├── templates/          # Manifest schema 与模板
├── examples/           # 示例提示词
└── assets/examples/    # 可下载的完整重建案例
```

## 依赖

| 包             | 版本     | 用途             |
| ------------- | ------ | -------------- |
| opencv-python | ≥ 4.9  | 结构检测（4.x/5.x 均兼容） |
| paddleocr     | ≥ 3.7  | 文字检测（PP-OCRv6） |
| paddlepaddle  | ≥ 3.3  | PaddleOCR 后端   |
| Pillow        | ≥ 10.0 | 图像处理           |
| numpy         | ≥ 1.24 | 数组运算           |
| scipy         | ≥ 1.10 | 色键边缘分析         |
| matplotlib    | ≥ 3.7  | 公式渲染           |
| latex2mathml  | ≥ 3.81 | 公式转换           |
| lxml          | ≥ 5.0  | SVG/XML 处理     |
| cairosvg（可选）  | -      | 提升 PPTX 媒体渲染质量，未装时自动回退 svglib |

## 贡献

欢迎提交 issue 或改进建议，尤其是复杂版式、公式导出、OCR 校对、清版底板质量和 PowerPoint 兼容性方面的问题。

## 致谢与第三方代码

FigEdit 的原生 SVG → PPTX 导出层基于 [PPT Master](https://github.com/hugohe3/ppt-master) 改编。感谢 Hugo He 开源这一套将 SVG 转换为原生、逐元素可编辑 PowerPoint 的实现。FigEdit 在此基础上加入了单图重建工作流、Manifest 资产组织、可编辑公式和质量检查等适配。PPT Master 使用 MIT 许可证，上游版权声明与完整许可文本见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

内置图像生成的调用协议（先将源图显示为对话中的编辑目标，再发起生成）借鉴自 [GordenImage2PPTX](https://github.com/GordenSun/GordenSuperPPTSkills)。感谢 GordenSun 验证并分享了这条让 Agent 内置图像工具稳定接收参考图的路径。

## 许可证

FigEdit 自有代码使用 [MIT](LICENSE) 许可证；第三方代码沿用各自许可证，详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。
