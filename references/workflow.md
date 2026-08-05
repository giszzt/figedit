# 重建工作流（Reconstruction Workflow）

本文件展开 `SKILL.md` 的四阶段执行顺序，不重新定义路由、元素、背景或质量判据。勘察以 `routing.md` 为准，字段以 `manifest_spec.md` 为准，交付放行以 `quality_checklist.md` 为准。

## 1. 勘察

先读用户要求，看一次源图整图，产出重建路径概要。此前不运行任何脚本，不写任何坐标。

顺序是先分区定底子，再成批扫对象：每个区判底子来源（SVG 画 / AI 清版 / 整块保留），然后过不了重绘门槛的对象一次扫完分成"可直接切"和"被压盖"两堆。概要六个槽位见 `routing.md`。

有待决项时把问题写进概要并一次问完，用户确认前不发起计费生成、不裁剪、不合成。OCR 不受此限。

## 2. 备料

开头无条件运行 `scripts/prepare_measurements.py`，保留 `draft_manifest.json` 的 `diagnostics.measurement_workspace`。OCR、风格 token、overlay 和 measurement report 都只是证据。只读会改变 manifest 的部分：低置信文字、公式和断行、坐标冲突。不要逐框复看高置信普通标签，也不要把草稿对象或 OCR 备选整批导入最终 manifest。

之后按概要指派的来源分支。**概要没指派到的分支整段跳过**——纯 SVG 图不跑生成，纯清版压平图不跑裁剪与吸附。各分支互不依赖，能并行就并行。

### 有 crop 或再生对象：吸附

为这些对象点粗框写进 `work/inventory.json`（只含走切或再生的对象），运行 `scripts/snap_boxes.py --exclude-text` 指向 OCR 结果，得到紧裁剪窗和 `clean / clean-on-fill / contaminated / snap-failed` 判定。看一次 `snap_sheet.png` 总览；只有 contaminated、snap-failed、带 warning 的项和 `closeup_ids` 才用 `inspect_regions.py` 局部放大。contaminated 的对象改路由，不改判据。

### 有清版区

1. 按区域提取 source region；前景深度已在勘察时由用户原话或检查点确定。
2. 写清版底简报和移除清单。
3. 调用支持参考图的后端。
4. 先跑尺寸、宽高比和配准等量化检查，再看一次整图候选；只有异常区域局部放大。
5. 将已验收底板写入 `background_plans[]`，按原图区域坐标放回 manifest。

不要把大块原图裁到底板上，不要把旧标签或引线裁回输出，不使用 rembg/GrabCut/临时阈值脚本替代既定路线。产不出合格底板时报告阻塞。

### 有再生对象

`probe_palette.py --boxes` 定键色与 sheet 数，在 chroma sheet 上再生并键控，整张 sheet 与一次切分 contact sheet 完成批量覆盖。重复元素只生成一次、按共享 id 多处放置。

**生成是长杆。**调用发出后立即并行推进文字清单、连接线和 manifest 草稿，不要把等待做成串行空档。

## 3. 组装：建立清单

- 结构：面板、卡片、边框、网格、分隔线、连接线和箭头，通常 `redraw`。
- 文字：标题、标签、注释、图例和图注，通常 `retype`。
- 公式：方程和行内数学片段，使用 `math`。
- 素材：按备料结果落 `decision`，干净的 `crop`、污染的 `regenerate-chroma`、区域内的 `flatten`。
- 背景：SVG 区不登记；清版区与整区保留写进 `background_regions`。

元素判据见 `element_decision_matrix.md`；背景可恢复性见 `background_reconstruction.md`；不要在本文件另造规则。

## 4. 编写 manifest

一次写出主要 panels、assets 和 elements，再用量测结果补精确坐标。每个决策贴着视觉证据写简短理由，不把字段当仪式。

普通标签和公式先记录源槽位、断行、基线和相邻碰撞约束。每个 `crop` 资产记录 `crop_window`，证据来自备料阶段的 `snap_report.json`，只有脚本点名项需要独立 1:1 图。把勘察结论记进 `reconstruction_plan`。

## 5. 首次 SVG 合成

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg
```

检查最终 SVG 总览、质量报告、placement overlay、视觉差异最差分块，以及实际有素材时的 contact sheet。先收齐所有问题，再一次批量修改 manifest。

修复阶段直接编辑最终 manifest。若首版由生成器产生，停用生成器，避免它覆盖人工修复。

## 6. 文字与公式排位

用 `fit_text.py` 辅助拟合密集文字槽位，用 SVG 预览修复碰撞。公式始终保持 `math` 和规范化 LaTeX；不要为回避排位把公式裁成图或留在普通 `text` 中。

SVG 冻结后运行 PPTX 阶段和静态回流审计：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage pptx
```

是否做原生 PowerPoint 渲染由 `reconstruction_plan.validation_tier`、实际 `math` 数和 `pptx_text_fit.py` 结果共同决定，不由“图看起来很密”单独决定。

## 7. 验收与修复

修复优先级：

1. 缺失信息。
2. 错误结构、箭头和连接关系。
3. 路线错误或静默降级。
4. 被错误重画、污染、切边或缺失的素材。
5. 检测/OCR 噪声和公式文字泄漏。
6. 文字/公式槽位、换行、溢出和碰撞。
7. 视觉抛光。

局部修改后只复查受影响区和一次总览一致性，不重新逐项扫描未受影响区域。独立问题批量修复；只有相互影响的布局问题才拆轮。

## 8. 打包

内容冻结、PPTX 已生成后运行：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage package
```

package 阶段不重建 SVG/PPTX，只更新证据、报告和打包状态。若 PPTX 早于 SVG，必须先运行 `--stage pptx`。
