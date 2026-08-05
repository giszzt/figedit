# 全局路由（Global Reconstruction Read）

本文件是整图总判与 `route_decision` 的唯一权威。它负责回答“哪些区域用 SVG、哪些区域保留栅格、哪些区域做 AI 清版、哪些视觉对象裁剪或再生，以及何时必须询问用户”。背景执行细节见 `background_reconstruction.md`，元素身份见 `element_decision_matrix.md`。

## 核心模型

不要把整张图压成 `regular-hybrid / ai-clean-plate` 二选一。一次整图查看后建立组合路线：

1. 用 SVG 重建默认的规则结构与文字。
2. 为局部或全图连续视觉场建立背景区域路线。
3. 对源图专有视觉按“身份、可分离性、编辑价值”选择裁剪、再生或压平。
4. 把真正未决的用户选择与已知污染分开记录。

复杂度只影响工作量，不直接决定路线。路线由背景是否能机械恢复、对象是否能干净分离，以及用户需要编辑什么决定。

## 决策顺序

### 1. 锁定用户已表达的编辑深度

| 用户表达 | `editability_depth` | 连续场前景模式 |
|---|---|---|
| “仅文字可编辑”“只改文字”“翻译文字” | `text-only` | `flatten` |
| “文字、公式和框线可编辑” | `text+structure` | 图形对象深度仍可能待确认 |
| 点名对象需要移动或替换 | `selective-assets` | `selective` |
| “全部对象可移动/替换/完全打散” | `full-extract` | `full-extract` |

用户未说明编辑深度但检出公式时，默认 `text+structure`，公式写成独立 `math`，验证档位为 `pptx-triggered`。用户明确 `text-only` 时不扩大结构范围，但公式仍保持可编辑，除非用户明确允许压平。

### 2. 按背景机械性质识别区域

先判断整图默认区域能否用纯色、规则渐变、测量几何和简单 SVG 忠实恢复，再识别例外区域：

- **确定性结构区**：面板、卡片、规则底色、规则渐变和几何结构。由 `base_strategy: svg-rebuild` 处理，不必逐区登记。
- **独立栅格证据区**：截图、地图、照片或图表主体可以完整保留，而且区域内部没有需要移除或编辑的前景。可直接使用 `source-preserve-region`，`field_type` 写 `self-contained-raster`。
- **连续视觉场**：照片、地图、插画、纹理或渲染场中存在待编辑文字、路线、标记、图标或其他前景；移除它们会暴露未知像素。使用 `ai-clean-plate`。

连续视觉场可以覆盖整幅画布，也可以只是一个面板或局部区域。只要区域内部存在待编辑前景，就不得静默改成整区裁剪。此类 `continuous-field` 只有用户明确接受“区域内部整体保持不可编辑栅格并保留旧标注”时，才允许 `source-preserve-region`；用户未表态时进入前景深度检查点。没有内部编辑需求的 `self-contained-raster` 不需要为保留本身提问。

路由发生在精确量测前，但 `source_region` 仍写源图像素坐标：根据整图给出覆盖目标区域的粗略 bbox，并标 `region_accuracy: estimated-from-global-read`；路由 `ready` 后量测再收紧坐标并改为 `measured`。不得因为坐标尚未精确而省略 scope，也不得为拿精确坐标提前运行 OCR/资产脚本。

### 3. 对视觉对象判断身份与可分离性

先判断对象是否应保留源图视觉身份，再判断能否从源图干净分离。不要把“源图专有”直接等同于“裁剪”。

先做一次**负向污染扫描**，再考虑裁剪。对每个候选对象直接在整图上看它的视觉轮廓和最小外接矩形；出现任一项就判为 `contaminated`，不进入 crop：

- 对象轮廓被文字、箭头、卡片边框、分隔线、徽标、邻居或其他前景穿过/遮住。
- 最小外接矩形不可避免地包含属于其他对象的像素，哪怕这些像素只占一角或一条边。
- 对象与承载面边框、圆角、阴影或连续背景纹理相交，无法把承载面作为单一实色重画。
- 对象自身有缺口或缺失像素，需要凭相邻背景猜测才能补全。

只有整图已能确认“对象完整、四周无异物”才允许 `clean`。`clean-on-fill` 更严格：外接矩形余量必须全部是同一均匀实色，且对象完整轮廓与边框、圆角、阴影、渐变、纹理、连接线、标签和邻接对象之间**四边都有可见净空**。紧凑窗若必须贴着或穿过卡片边、标题线、连接线、徽标或邻居，即判 `contaminated`；“对象位于彩色卡片上”本身不能证明 `clean-on-fill`。整图看不清才把该对象列入 `exception_ids`，不要先裁出来再逐个试错。

| 对象 | 可分离性与编辑价值 | 策略 |
|---|---|---|
| 通用结构、简单图元 | 能用少量 SVG 图元忠实表达 | `redraw` |
| 源图专有视觉 | 裁剪窗为 `clean` 或合法 `clean-on-fill` | `crop` |
| 源图专有视觉 | 被文字、卡片、边框、箭头或邻居压盖，且需要独立存在 | `regenerate-chroma` |
| 污染对象 | 不需要独立移动，且位于 AI 清版区域 | `flatten` |
| 精确像素不可漂移的污染对象 | AI 近似不可接受 | 用户明确同意区域栅格保留，否则报告取舍或阻塞 |

整图已经能看出的污染是已知决策，不是 `exception_ids`。为它分配 `regenerate-chroma`、`flatten` 或阻塞路线；只有整图确实看不清、边界或身份未决的对象才进入异常清单。

`regenerate-chroma` 是元素级恢复方法，可与 SVG 结构区、局部清版区或全图清版区组合；不得把它限定为全图 AI 路线的附属步骤。

确定性 SVG 区没有可承载污染对象的底板，所以不能把“无需独立移动”当作 `flatten` 理由。只要该对象必须保留、周围文字/边框/连接线又要可编辑，污染对象就走 `regenerate-chroma`；只有对象位于 AI scope 时才可 `flatten`。若再生近似不可接受，必须让用户在区域栅格保留与保真损失之间选择。

### 4. 合并用户检查点

任何 `ai-clean-plate` 区域的 `foreground_mode` 若无法从用户原话确定，设置为 `pending-user-choice`，把 `route_status` 设为 `needs-user-input` 并停止后续处理。一次提示同时给出：

- 需要清版的具体区域。
- 区域内文字、简单标记和图形对象清单。
- `flatten / selective / full-extract` 的结果差异。
- 污染素材再生与清版底的预计生成调用数。
- 推荐方案和理由。

用户选择前不要运行 OCR、资产裁剪、图像生成或 compose。用户已明确深度时直接记录，不重复提问。

## Route Decision v2

新任务先写一个最小路由骨架：

```json
{
  "route_decision": {
    "schema_version": 2,
    "source": "fresh-global-read",
    "route_status": "needs-user-input",
    "editability_depth": "text+structure",
    "base_strategy": "svg-rebuild",
    "background_scopes": [
      {
        "id": "panel-c-map",
        "source_region": {"x": 1200, "y": 55, "w": 478, "h": 600},
        "region_accuracy": "estimated-from-global-read",
        "field_type": "continuous-field",
        "strategy": "ai-clean-plate",
        "foreground_mode": "pending-user-choice",
        "foreground_inventory": [
          {"id": "map-worker", "kind": "source-specific-visual", "resolved_strategy": "pending-user-choice"}
        ],
        "reason": "Labels, routes and markers overlap continuous map pixels."
      }
    ],
    "asset_groups": [
      {
        "strategy": "crop",
        "ids": ["asset-clean-icon"],
        "separability": "clean",
        "reason": "Source-specific visual with a clean separable window."
      },
      {
        "strategy": "regenerate-chroma",
        "ids": ["asset-overlapped-person"],
        "separability": "contaminated",
        "observed_overlap": ["card border", "label"],
        "reason": "Source-specific visual overlaps a card border and label."
      }
    ],
    "unresolved_decisions": [
      {"id": "panel-c-depth", "type": "foreground-depth", "scope_id": "panel-c-map", "question": "该地图区域只需文字可编辑，还是需要提取指定或全部图形对象？"}
    ],
    "exception_ids": [],
    "validation_tier": "pptx-triggered"
  }
}
```

字段约束：

- `source`：新整图判断用 `fresh-global-read`；只有用户明确指定清版、裁剪、栅格保留、再生等**重建方法**时才用 `user-directive`。用户只说明编辑深度不把整条路线来源改成 `user-directive`。
- `route_status`：`ready` 或 `needs-user-input`。
- `base_strategy`：新任务固定为 `svg-rebuild`，背景例外写入 `background_scopes`。
- `background_scopes[].strategy`：`ai-clean-plate` 或 `source-preserve-region`。
- `background_scopes[].region_accuracy`：路由草案用 `estimated-from-global-read`，路由 ready 后量测收紧为 `measured`。
- `background_scopes[].foreground_mode`：`flatten`、`selective`、`full-extract`、`pending-user-choice`；只对连续场使用。
- `background_scopes[].foreground_inventory`：只列处理方式随前景深度变化的源图专有非结构对象；用户未决时用 `resolved_strategy: pending-user-choice`，确认后改成 `flatten` 或 `regenerate-chroma`。文字、公式、通用箭头、圆点和路线不进入该清单，仍分别 `retype / math / redraw`。
- `asset_groups[].strategy`：`redraw`、`crop`、`regenerate-chroma`、`flatten`、`preserve-raster` 或有理由的 `omit`。
- `asset_groups[].separability`：`not-applicable`、`clean`、`clean-on-fill`、`contaminated` 或 `embedded-in-continuous-field`；crop 只接受前两项。
- `asset_groups[].observed_overlap`：污染组列出整图上看见的压盖类型，不要求先裁小图证明。
- `unresolved_decisions` 只记录需要用户决定的事项；`exception_ids` 只记录需要补证据的视觉歧义。

最终 `assets[].decision` 必须与 `asset_groups` 一致；最终区域执行计划用顶层 `background_plans[]` 与 `scope_id` 关联。旧 manifest 的 `reconstruction_route` 与单个 `background_plan`继续兼容，但不再作为新任务的路由权威。

## 路由完成条件

只有以下条件全部满足，才把 `route_status` 改为 `ready`：

- 每个连续场要么有 `ai-clean-plate` 计划，要么有用户明确的整区栅格保留指令。
- 每个明显污染的源图专有对象已分配非 crop 策略。
- 所有 `pending-user-choice` 已解决，`unresolved_decisions` 为空。
- 每个 crop 组都说明其窗口为什么可分离。
- 图像生成预算已根据背景区域与 chroma sheet 数量计算并呈现。

检查点前不得运行 `probe_palette.py`。预算采用确定的保守算法：每个 AI scope 计 1 张清版底；没有 chroma 候选时 K=0；存在候选时默认把全任务候选合并规划为 K=2 张不同键色 sheet，只有整图已明显证明一种安全键色覆盖全部候选时才可写 K=1 并说明依据。总预算 `N = 清版底数 + K`，同时声明这是 `global-read estimate`。用户确认后再用 `probe_palette.py --boxes` 确认实际 K；若实际会超过估计预算，先重新告知用户，不得静默增加调用。

## 历史 Manifest 复用

同源图历史产物只能复用 OCR 文本、公式内容、面板边界和已验证坐标。每次测试新 skill 或新路由版本时，重新生成：

- `route_decision`
- `background_plan` / `background_plans`
- `asset_decision_policy`
- `assets[].decision` 与 `crop_window`
- 旧质量状态

在 `provenance.reused_fields` 与 `provenance.recomputed_fields` 记录边界。不要把同哈希历史路线当作当前 Global Reconstruction Read 的结论；这不是源图缓存机制。

## 禁止的编排

- 先逐元素裁图，再决定总体路线。
- 用一个全局二选一标签覆盖局部背景和元素策略。
- 因对象源图专有就默认进入 crop。
- 把已知污染写成异常项，等裁剪后再处理。
- 因地图、截图或照片边界是矩形，就默认其内部全部保持栅格。
- 在用户未决定连续场前景深度时继续 OCR、生成、裁剪或合成。
- 复用历史 manifest 的路线与资产决策冒充新整图判断。
