# 重建工作流（Reconstruction Workflow）

本文件展开 `SKILL.md` 的执行顺序，不重新定义全局路由、元素、背景或质量判据。整图路由以 `global_routing.md` 为准，字段以 `manifest_spec.md` 为准，交付放行以 `quality_checklist.md` 为准。

## 1. 整图总判

先读取用户要求并查看一次源图整图，再运行任何测量脚本。形成：

- 编辑深度、默认 SVG 策略与局部/全图背景 scopes。
- 结构、文字、公式、素材和背景批量清单。
- 干净裁剪组、明显污染再生组、连续场与真正未决区域。
- 初始验证档位。

将结论写入 Route Decision v2。若连续场 `foreground_mode` 未决，设置 `route_status: needs-user-input`，呈现区域/对象清单与生成预算后停止。只有 `route_status: ready` 才进入测量。

## 2. 一次性测量

运行 `scripts/prepare_measurements.py`，保留 `draft_manifest.json` 的 `diagnostics.measurement_workspace`。OCR、风格 token、overlay 和 measurement report 都只是证据。

只读会改变 manifest 的部分：低置信文字、公式和断行、坐标冲突、整图未决项。不要逐框复看高置信普通标签，也不要把草稿对象或 OCR 备选整批导入最终 manifest。

## 3. 批量建立清单

- 结构：面板、卡片、边框、网格、分隔线、连接线和箭头，通常 `redraw`。
- 文字：标题、标签、注释、图例和图注，通常 `retype`。
- 公式：方程和行内数学片段，使用 `math`。
- 素材：先锁定身份，再按可分离性分为干净 `crop`、污染 `regenerate-chroma` 或区域 `flatten`。
- 背景：默认 SVG；局部/全图连续场建立 `ai-clean-plate` scope；整区栅格保留必须有明确意图。

元素判据见 `element_decision_matrix.md`；背景可恢复性见 `background_reconstruction.md`；不要在本文件另造规则。

## 4. 编写 manifest

一次写出主要 panels、assets 和 elements，再用量测结果补精确坐标。每个决策贴着视觉证据写简短理由，不把字段当仪式。

普通标签和公式先记录源槽位、断行、基线和相邻碰撞约束。每个 `crop` 资产记录 `crop_window`；整图判断或一次带 ID 总览可以覆盖整批，只有异常项需要独立 1:1 图。

## 5. 准备路线专属资产

### 默认 SVG 区域

重建结构与文字。只裁 Route Decision 中已经判为窗口可分离的素材；污染组直接批量 chroma 再生。生成一次 contact sheet，统一检查，没有新异常就不逐项回看源图。

### AI 清版底区域

1. 按 `scope_id` 提取对应 source region；根据用户原话或检查点确定 `flatten`、`selective`、`full-extract`。
2. 写清版底简报和移除清单。
3. 调用支持参考图的后端。
4. 先跑尺寸、宽高比和配准等量化检查，再看一次整图候选；只有异常区域局部放大。
5. `full-extract/selective` 的范围内对象在 chroma sheet 上再生并键控，整张 sheet 与一次切分 contact sheet 完成批量覆盖。
6. 将已验收底板写入 `background_plans[]`，按原图区域坐标放回 manifest。

不要把大块原图裁到底板上，不要把旧标签或引线裁回输出，不使用 rembg/GrabCut/临时阈值脚本替代既定路线。产不出合格底板时报告阻塞。

## 6. 首次 SVG 合成

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg
```

检查最终 SVG 总览、质量报告、placement overlay、视觉差异最差分块，以及实际有素材时的 contact sheet。先收齐所有问题，再一次批量修改 manifest。

修复阶段直接编辑最终 manifest。若首版由生成器产生，停用生成器，避免它覆盖人工修复。

## 7. 文字与公式排位

用 `fit_text.py` 辅助拟合密集文字槽位，用 SVG 预览修复碰撞。公式始终保持 `math` 和规范化 LaTeX；不要为回避排位把公式裁成图或留在普通 `text` 中。

SVG 冻结后运行 PPTX 阶段和静态回流审计：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage pptx
```

是否做原生 PowerPoint 渲染由 `route_decision.validation_tier`、实际 `math` 数和 `pptx_text_fit.py` 结果共同决定，不由“图看起来很密”单独决定。

## 8. 验证与修复

修复优先级：

1. 缺失信息。
2. 错误结构、箭头和连接关系。
3. 路线错误或静默降级。
4. 被错误重画、污染、切边或缺失的素材。
5. 检测/OCR 噪声和公式文字泄漏。
6. 文字/公式槽位、换行、溢出和碰撞。
7. 视觉抛光。

局部修改后只复查受影响区和一次总览一致性，不重新逐项扫描未受影响区域。独立问题批量修复；只有相互影响的布局问题才拆轮。

## 9. 打包

内容冻结、PPTX 已生成后运行：

```powershell
python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage package
```

package 阶段不重建 SVG/PPTX，只更新证据、报告和打包状态。若 PPTX 早于 SVG，必须先运行 `--stage pptx`。
