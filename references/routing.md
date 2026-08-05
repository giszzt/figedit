# 勘察与重建计划（Survey & Reconstruction Plan）

**何时读我**：每个任务的第一步。本文件是勘察协议、对象清单和 `reconstruction_plan` 的唯一权威，回答“哪些区域用 SVG、哪些保留栅格、哪些做 AI 清版、每个视觉对象走哪条路、什么时候必须问用户”。背景执行细节见 `background_reconstruction.md`，元素语义见 `element_decision_matrix.md`。

## 核心模型

不要把整张图压成一个二选一标签。看一次源图后建立组合路线：

1. 规则结构与文字默认 SVG 重建。
2. 局部或全图连续视觉场单独登记为背景区域。
3. 源图专有视觉按“画得像吗 → 窗口干净吗 → 需要独立存在吗”决定裁剪、再生或压平。
4. 真正需要用户决定的事项与已知污染分开：前者进 `open_questions` 并停止，后者当场定路线。

复杂度只影响工作量，不决定路线。路线由背景能否机械恢复、对象能否干净分离、用户需要编辑什么决定。

## 对象级决策树

对每个非文字视觉对象顺序回答四问，第一个成立的答案即为路线：

1. **三五笔基础图元画得像吗？**（朴素箭头、方框、分隔线、圆点、加减号、对勾、节点圆）→ `redraw`。有定制轮廓、渐变、阴影、多色细节、品牌或角色身份的一律不算，哪怕看起来简单。
2. **窗口干净吗？**整图上看轮廓完整、四周无异物 → `crop`（精确判定交给 `snap_boxes.py`）。
3. **需要独立存在吗？**被压盖但必须能单独移动/替换 → `regenerate-chroma`。
4. **位于 AI 清版区域吗？**不需独立移动且区域底板能承载 → `flatten`。

四问都不成立（对象必须保真、又不可分离、AI 近似不可接受）时，让用户在整区栅格保留与保真损失之间选择，不要静默降级。

确定性 SVG 区没有可承载污染对象的底板，所以那里的污染对象只能 `regenerate-chroma`，不能 `flatten`。`regenerate-chroma` 是元素级方法，可用于任意区域，不是全图 AI 路线的附属步骤。

### 负向污染扫描

勘察时对每个 crop 候选直接在整图上扫一遍，任一成立就不写 `crop`：

- 轮廓被文字、箭头、卡片边框、分隔线、徽标或邻居穿过、遮住。
- 最小外接矩形不可避免地含有其他对象的像素。
- 与承载面边框、圆角、阴影或连续背景纹理相交。
- 对象自身有缺口，需要猜测相邻背景才能补全。

这一步是给路线定调，精确边界和净空由 `snap_boxes.py` 量。整图确实看不清的对象写进 `closeup_ids`，不要先裁出来再试错。

## 背景区域识别

- **确定性结构区**：面板、卡片、规则底色、规则渐变、几何结构。默认 SVG 重建，不必登记。
- **独立栅格证据区**：截图、地图、照片或图表主体可完整保留，且内部没有要移除或编辑的前景。直接 `source-preserve-region`，无需为保留本身提问。
- **连续视觉场**：照片、地图、插画、纹理或渲染场中存在待编辑文字、路线、标记或图标，移除会暴露未知像素。登记为 `ai-clean-plate`。

连续场可以覆盖整幅画布，也可以只是一个面板。只要区域内部存在待编辑前景就不得静默改成整区裁剪；只有用户明确接受“该区域整体保持不可编辑栅格并保留旧标注”时才可 `source-preserve-region`。

区域坐标在勘察时按整图给粗略 bbox 即可，量测阶段再收紧；不要为拿精确坐标提前跑 OCR 或资产脚本。

## 编辑深度

| 用户表达 | `edit_scope` | 连续场前景模式 |
|---|---|---|
| “仅文字可编辑”“只改文字”“翻译文字” | `text-only` | `flatten` |
| “文字、公式和框线可编辑” | `text+structure` | 图形对象深度可能仍待确认 |
| 点名对象需要移动或替换 | `selective-assets` | `selective` |
| “全部对象可移动/替换/完全打散” | `full-extract` | `full-extract` |

用户未说明编辑深度但检出公式时默认 `text+structure`，公式写成独立 `math`，验证档位 `pptx-triggered`。用户明确 `text-only` 时不扩大结构重画范围，但公式仍保持可编辑，除非用户明确允许压平。

## 对象清单 `work/inventory.json`

勘察在一个回合里写完整张表，不挤牙膏。

```json
{
  "image": "input.png",
  "objects": [
    {
      "id": "icon-robot",
      "bbox": [412, 188, 96, 90],
      "kind": "icon",
      "route": "crop",
      "note": "源图专有机器人图标，四周无异物",
      "ask_user": false
    },
    {
      "id": "panel-c-map",
      "bbox": [1200, 55, 478, 600],
      "kind": "region",
      "route": "ai-clean-plate",
      "note": "地图连续场，标注压在地图像素上",
      "ask_user": true
    }
  ]
}
```

- `bbox`：一眼精度的粗框，允许 10–20px 偏差。`text`/`math` 行可省略（OCR 负责）。
- `kind`：`icon | text | math | panel | marker | connector | region`。
- `route`：`redraw | crop | regenerate-chroma | flatten | retype | math | ai-clean-plate | preserve-raster | omit`。
- `note`：一句话判断依据，不写过程。
- `ask_user`：该对象处理方式需用户决定时为 true。

清单里 `crop / regenerate-chroma / flatten` 且带 bbox 的行会被 `snap_boxes.py` 吸附量测；其余行标记为 skipped。最终 `assets[].decision` 必须与清单 `route` 一致，validator 会检查。

## `reconstruction_plan`

写在 manifest 顶层，只锁影响后续执行的结论：

```json
{
  "reconstruction_plan": {
    "edit_scope": "text+structure",
    "background_regions": [
      {
        "id": "panel-c-map",
        "source_region": {"x": 1200, "y": 55, "w": 478, "h": 600},
        "strategy": "ai-clean-plate",
        "foreground_mode": "flatten",
        "reason": "标注压在连续地图像素上"
      }
    ],
    "validation_tier": "pptx-triggered",
    "open_questions": [],
    "closeup_ids": [],
    "inventory": "figure-task/work/inventory.json"
  }
}
```

- `edit_scope`：`text-only | text+structure | selective-assets | full-extract`。
- `background_regions`：只登记 AI 清版区和用户明确同意的整区栅格保留区；`strategy` 为 `ai-clean-plate | source-preserve-region`，AI 区必须写 `foreground_mode`（`flatten | selective | full-extract | pending-user-choice`）。确定性 SVG 区不登记。
- `validation_tier`：`svg-primary | pptx-triggered`。
- `open_questions`：待用户决定的事项，每项含 `id` 与 `question`。**非空即阻塞**：此时 manifest 不得含 assets 或 background_plans，脚本会拒绝裁剪与合成。
- `closeup_ids`：整图证据不足、需要 1:1 局部确认的区域。已知污染不属于这里。
- `inventory`：对象清单路径，供 validator 交叉检查。

最终区域执行计划仍写顶层 `background_plans[]`，通过 `scope_id` 关联 `background_regions[].id`。旧 manifest 的 `route_decision` 继续兼容读取，新任务不再写它。

## 用户检查点

任何 `ai-clean-plate` 区域的前景深度无法从用户原话确定时，设 `foreground_mode: pending-user-choice`，写入 `open_questions` 并停止。一次提问同时给出：

- 需要清版的具体区域，和区域内文字、标记、图形对象清单。
- `flatten / selective / full-extract` 的结果差异。
- 图像生成预算：每个 AI 区域计 1 张清版底；chroma 候选默认规划 K=2 张不同键色 sheet，整图已明显证明一种安全键色覆盖全部候选时才可写 K=1 并说明依据。总预算 `N = 清版底数 + K`，声明这是勘察估计。
- 含公式（`pptx-triggered`）时一并请求 PowerPoint 附着预授权。
- 推荐方案和理由。

检查点前不得运行 `probe_palette.py`、OCR、裁剪、生成或 compose。用户确认后再用 `probe_palette.py --boxes` 确认实际 K；实际会超预算时先重新告知，不得静默增加调用。

## 历史 manifest 复用

同源图历史产物只能复用 OCR 文本、公式内容、面板边界和已验证坐标。每次重新生成：`reconstruction_plan`、`background_plans`、`assets[].decision` 与 `crop_window`、旧质量状态。在 `provenance.reused_fields` 与 `provenance.recomputed_fields` 记录边界。同哈希历史路线不是当前勘察的结论。

## 禁止的编排

- 先逐元素裁图，再决定总体路线。
- 用一个全局二选一标签覆盖局部背景和元素策略。
- 因对象源图专有就默认 `crop`；因它看起来简单就默认 `redraw`。
- 把已知污染写成待确认项，等裁剪后再处理。
- 因地图、截图或照片边界是矩形，就默认其内部全部保持栅格。
- `open_questions` 非空时继续 OCR、生成、裁剪或合成。
- 复用历史 manifest 的路线冒充新勘察。
- 逐个对象量像素坐标：那是 `snap_boxes.py` 的工作。
