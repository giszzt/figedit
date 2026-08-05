---
name: figedit-v2
description: 将位图图形重建为高保真可编辑 SVG 与原生 PowerPoint，支持仅文字可编辑、文字/结构/公式可编辑、源图素材保真混合、选择性或完整前景拆分，以及复杂连续背景的 AI 清版底重建。当用户希望把截图、论文插图、流程图、架构图、信息图、UI、图表/地图、海报或封面转成可编辑图形，或提到“图片转可编辑 SVG/PPT”“仅文字可编辑”“图表重建”“FigEdit”时使用。
---

# FigEdit

把不可编辑的位图图形重建为高保真、可维护、可继续编辑的 SVG 与原生 PPTX 包。

**主流程：勘察 → 备料 → 组装 → 验收。**先判断，后执行。判断阶段不碰坐标也不跑脚本，只回答“每一部分从哪来”；执行阶段才按已定路线调工具。

## 核心原则

输出画面上的每一块像素只可能有四个来源：

1. **SVG 画的** —— 结构、文字、公式
2. **从源图切的** —— `crop`
3. **AI 生成的** —— 区域清版底（背景）、色键版再生（前景对象）
4. **整块原样保留的** —— `preserve-raster`

路由就是给每一部分指派来源，每部分有且只有一个。指派完成即可开工；指派不全就是漏了东西。

### 重绘门槛

只有“用三五笔基础图元能画得像”的图形才允许 `redraw`：朴素箭头、方框、分隔线、圆点、加减号、对勾、简单节点圆。有定制轮廓、渐变、阴影、多色细节、品牌或角色身份的对象一律按素材处理（切、再生或压平），哪怕它看起来简单。拿不准时按素材处理，不重画。重画产物必须与源图形状可对照，画不像就是路由错误，不是绘画技术问题。

## 工作位置

所有命令在用户项目目录运行，每张图建任务目录（`figure-task/work` 证据、`figure-task/out` 交付），绝不写回 skill 目录。Windows 路径用正斜杠，非 ASCII 路径先经文件系统验证。

## 1 勘察

看一次足够清晰的源图，产出一份**重建路径概要**。这是本阶段唯一的交付物，纯文字，**零坐标**，二十行以内，写给人看。槽位固定，缺项写“无”：

```
图型与分区    每个区域一行：这是什么、底子从哪来
需要生成的    清版底张数 + 色键版张数 = 计费调用总数，或“无”
不可重画的对象  可直接裁的一堆、需再生的一堆，按名字和位置点出来，或“无”
公式          有无、大致数量 → 验证档位
工作量重心    这张图的时间主要花在哪
需要用户定    具体问题，或“无”
```

对象用名字和空间关系指认（“标题右边那个地球仪，骑在面板边框上”），不写 bbox。坐标属于备料阶段。

概要写完路线即锁定，后续不翻案。写不出“工作量重心”说明没看懂图；“不可重画的对象”分不出两堆说明污染扫描没做。

### 图型速查表（按区域查，不是按整图）

| 看到的 | 底子从哪来 | 里面的对象从哪来 |
|---|---|---|
| 白底或平色底的流程图、架构图、论文插图 | SVG 画 | 通用图元画；专有图标按窗口干净与否切或再生 |
| 多面板拼接的复合图 | 每个面板分别查 | 同上，按面板成批扫 |
| 截图、图表主体、缩略图网格，内部不需要改 | 整块保留 | 不拆 |
| 地图、照片、插画上压着要改的标注 | 区域 AI 清版 | 要能单独动的再生；不用动的压平进底板 |
| 海报、封面、场景图，文字压在连续画面上 | AI 清版 | 同上 |
| 公式密集的论文图 | 按上面几行查底子 | 公式一律 `math`，验证档锁 `pptx-triggered` |

一张图的不同区域各查各的，不要用一个标签盖住整幅。判不准时回到四来源指派。

### 素材两堆

过不了重绘门槛的对象只分两堆，一次扫完，不逐个走流程：

- **窗口干净的** → 切。轮廓完整、四周无异物、外接矩形不含别人的像素。
- **被压盖的** → 边框、文字、箭头、连接线、邻居穿过或遮住它。需要单独动就再生；不需要单独动且落在清版区就压平进底板。确定性 SVG 区没有底板可压，那里的污染对象只能再生。

判据细则见 `references/routing.md`，元素语义见 `references/element_decision_matrix.md`。

### 编辑深度与提问

用户原话优先：说“仅文字可编辑”锁 `text-only`（连续场直接压平）；点名对象锁 `selective-assets`；要求全部可动锁 `full-extract`；检出公式且用户未表态时默认 `text+structure` 并锁 `pptx-triggered`。

**提问一次问完。**概要写完后若有待决项，把前景深度选项、生成预算和 PPTX 附着预授权（含公式时）合并成一次提问。只有不同选择会显著改变费用或交付能力时才问；能自己定的不问。拿到附着预授权后验收阶段直接用 `--allow-attach`，不再二次提问。

**用户确认前不得发起任何计费生成调用，也不得裁剪或合成。**OCR 不在此列，见下。

## 2 备料

按概要指派的来源把素材做出来。开头无条件先跑 OCR——它不计费、输出无论走哪条路都要用，可以和提问并行：

```powershell
python scripts/prepare_measurements.py input.png --out figure-task/work
```

只读会改变 manifest 的证据：低置信文字、公式与断行、坐标冲突。高置信普通标签不逐框打开。

以下分支按概要执行，互不依赖，能并行就并行。**概要没指派到的分支直接跳过**——纯 SVG 图不跑任何生成，纯清版压平图不跑任何裁剪。

### 有 crop 素材

此时才为这些对象点粗框（一眼精度，允许 10–20px 偏差），写进 `work/inventory.json`，只含走切或再生的对象；文字框来自 OCR，结构框在组装时确定，都不进来。路线已锁，点框是执行动作。

```powershell
python scripts/snap_boxes.py input.png --inventory figure-task/work/inventory.json --exclude-text figure-task/work/ocr_results.json --out figure-task/work/snap_report.json --sheet figure-task/work/snap_sheet.png
```

看一次 `snap_sheet.png` 总览。判定写进各资产的 `crop_window`，人工只复看脚本点名项：`contaminated` 的改路由（改走再生或压平），`snap-failed`、带 warning 的和概要点名看不清的用 `inspect_regions.py` 局部放大。三值语义——`clean` 窗口余量是画布底色；`clean-on-fill` 余量是单一均匀实色且四边有净空，manifest 用同色重画承载面；`contaminated` 不得继续切。`quality_audit.py` 的事后核验是兜底。切图由 `crop_assets.py` 在组装时执行。

### 有清版区

`prepare_clean_plate_mask.py` 准备掩膜，生成区域底板，`check_plate_registration.py` 验配准（scale ≈ 1.00 / offset ≈ 0）。底板必须是对源区域的编辑——移除待重建前景并补全其后像素，其余保持对齐和身份一致，不是新场景。细则见 `references/background_reconstruction.md`、`references/ai_clean_plate_prompting.md` 与 `references/image_backend_policy.md`。

### 有再生对象

`probe_palette.py --boxes` 定键色与 sheet 数，生成色键版，`chroma_key.py` 抠出，`slice_grid.py` 切分。全部候选合并到尽量少的 sheet 上，重复元素只生成一次、按共享 id 多处放置。细则见 `references/chroma_regeneration.md`。禁止 rembg、GrabCut、阈值抠图等即兴替代。

无可用图像后端或底板不合格时停止并报告，不静默降级。

**生成是长杆，不要干等。**调用发出后立即并行推进文字清单、连接线和 manifest 草稿。

## 3 组装

必读 `references/manifest_spec.md`、`references/svg_authoring.md`、`references/quality_checklist.md`，其余按路线加载（各文件开头有适用说明）。把勘察结论记进 manifest 顶层 `reconstruction_plan`，写文字 `retype`、公式拆 `math`、结构 `redraw`、素材按备料结果落 `decision` 与 `crop_window`。

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg
```

修复走批量通道，不手编大 JSON、不写临时 patch 脚本：

```powershell
python scripts/manifest_edit.py manifest.json --apply-snap figure-task/work/snap_report.json
python scripts/manifest_edit.py manifest.json --set "label-3,label-4:y+=4" --apply-fit figure-task/work/fit_report.json
```

告警收齐一批改完再 compose。SVG 冻结后 `--stage pptx` 导出，仅补元数据用 `--stage package`。

## 4 验收

每轮看 `preview.png` 与各报告；报告点名后只复查受影响区。最终至少看一次 SVG 总览。

- **档 0 / `svg-primary`**：无 `math` 且 `pptx_text_fit.py` 无换行、溢出、缺字、错位报告。SVG 即验收，不打开 PowerPoint。
- **档 1 / `pptx-triggered`**：含 `math` 或静态审计报结构风险。交付前原生渲染一次，只查公式越槽、意外换行、内容截断、元素错位。
- **档 2**：档 1 发现结构缺陷，批量修完最多再渲染一次；仍有问题写入交付说明，不无限循环。

不算缺陷：抗锯齿、笔画粗细、标点亚像素差、基线 ±1px、字距 ±0.5px、整体色彩管理差异。算缺陷：内容缺失、换行变化、溢出、公式越槽、元素错位超 3px。

交付说明附上重建路径概要，并说明实际执行与概要是否一致、不一致的原因。

### PowerPoint 安全规则

PPTX 原生渲染只能调 `python scripts/render_pptx.py figure-task/out/editable.pptx --out figure-task/out/pptx_render`。

- 禁止手写 `PowerPoint.Application` 自动化；禁止附着态调用 `Quit()`；禁止 `taskkill /IM POWERPNT.EXE`、`Stop-Process POWERPNT`。
- 检测到用户正在使用 PowerPoint 时脚本默认拒绝；只有用户同意（含勘察时的预授权）才加 `--allow-attach`。
- 附着态只关自己只读打开的 Presentation。未完成要求中的原生渲染时交付说明写“原生渲染暂缓”，不得伪称完成。

## 输出包

`editable.svg`、`editable_embedded.svg`、`editable.pptx`、`preview.png`、`manifest.json`、`contact_sheet.png`（有素材时）、`quality_report.md`、`editability_report.md`、`assets/`、`diagnostics/`、`timings.json`。PPTX 语义级顶层解组：文字、形状、连接线、素材可直接选中；公式、蒙版、旋转等按保真需要保持成组。

## 权威与职责

| 关注点 | 唯一权威 |
|---|---|
| 四阶段、四来源、重绘门槛、验证分档、PowerPoint 安全 | 本 `SKILL.md` |
| 勘察协议、路径概要槽位、`reconstruction_plan` | `references/routing.md` |
| manifest 字段 | `references/manifest_spec.md` |
| 背景与前景深度 | `references/background_reconstruction.md` |
| 元素语义 | `references/element_decision_matrix.md` |
| crop 执行语义 | `references/asset_extraction.md` |
| chroma 再生 | `references/chroma_regeneration.md` |
| 最终放行条件 | `references/quality_checklist.md` |

## 入口脚本

`prepare_measurements.py` OCR 与风格证据｜`snap_boxes.py` 粗框吸附与裁剪窗判定｜`inspect_regions.py` 异常项 1:1 放大｜`manifest_edit.py` 批量改 manifest｜`compose_svg_package.py` 分阶段合成｜`fit_text.py`、`pptx_text_fit.py` 文字拟合与结构风险报告｜`render_pptx.py` 安全原生渲染｜`crop_assets.py`、`probe_palette.py`、`chroma_key.py`、`slice_grid.py`、`prepare_clean_plate_mask.py`、`check_plate_registration.py` 切图与生成链｜`audit_editability.py`、`quality_audit.py`、`validate_manifest.py` 审计与校验

## 质量底线

保留源图全部重要信息、阅读关系和专有视觉；普通文字和每个检出公式保持可编辑；无检测噪声、公式文字泄漏、脏裁剪、源图补丁拼贴或静默路线降级。完整放行条件见 `references/quality_checklist.md`。
