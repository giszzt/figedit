# 入口脚本接口卡（Entry Script Interface Cards）

只列模型直接运行的脚本。`scripts/` 下其余模块由 `compose_svg_package.py` 内部 import，不直接运行。

卡片没写的参数就是不需要用的参数；卡片写了输出格式就照着读，不必先跑一遍看输出长什么样。

**每个脚本跑完都把结论打印在屏幕上。**看屏幕就够了，不要再写代码去解析它写出来的 JSON。

---

## prepare_measurements.py
用途  一次取证：OCR、风格采样、结构探测；也负责建任务目录
调用  `python scripts/prepare_measurements.py <image> --init <name>`
      `python scripts/prepare_measurements.py <image> --out figure-task/work`
参数  `--init NAME` 建 `NAME/{work,out}` + 拷源图 + 写含 canvas 尺寸的 manifest 骨架，然后测进 `NAME/work`
      `--no-geometry` 只跑 OCR 和风格，跳过结构探测
      `--ocr-profile` v6_medium(默认) / v6_small / v6_tiny / v5_mobile / auto
输出  `work/ocr_results.json` items[].{id,text,confidence,bbox{x,y,w,h},polygon}
      `work/style_tokens.json`、`work/geometry.json`、`work/draft_manifest.json`
      `work/diagnostics/{ocr_overlay,style_overlay,geometry_overlay}.png`
      `work/measurement_report.md`
注意  不计费，勘察提问期间就可以并行跑。`draft_manifest.json` 的 `elements` 恒为空，那是骨架不是草稿

## measure.py
用途  一次调用问完所有像素问题，同时出数字表和放大拼图。**不要为量尺寸手写 `python -c`**
调用  `python scripts/measure.py <image> --q "名字:类型@参数" ... --sheet work/measure_sheet.png`
类型  `info` 图片尺寸与色彩模式（`info@别的路径` 查其他文件）
      `bbox@x,y,w,h` 窗口内墨迹紧边界，附带四边各裁掉多少
      `color@x,y,w,h` 主色、均值、是不是单一实色
      `clearance@x,y,w,h` 四边净空，贴边的边会点名
      `alpha-bbox@路径` RGBA 文件里不透明像素的紧边界
      `fontfit@x,y,w,h` 由该窗口渲染出的文字反算 font_size（拉丁与中日韩两个值）
      `diff@路径,x,y,w,h` 某文件与源图某区域的缩放比、平均色距、对不对得上
      `zoom@x,y,w,h` 不要数字，只把该窗口放大贴进 sheet
参数  `--json 路径` 另存完整结果
输出  每行一个查询的一句话结论；`--sheet` 是一张带标签的拼图，一次 Read 覆盖所有查询窗口
注意  查询数量不限，**一次问十个跟问一个花的时间一样**。单个查询出错不影响其余查询
      要看某处长什么样就用 `zoom`，不要自己裁图存盘再 Read

## probe_geometry.py
用途  结构证据：面板/卡片的 bbox 与颜色、每行文字的槽位与字号色值
调用  `python scripts/probe_geometry.py <image> --out work/geometry.json --ocr work/ocr_results.json --overlay work/diagnostics/geometry_overlay.png`
输出  `image_profile.{flat_design_score,abstained}`
      `fill_regions[].{id,bbox[x,y,w,h],color,stroke,stroke_width,kind,corner_radius_est,parent,confidence}`
      `text_slots[].{id,bbox,text,font_size_est,fill,baseline_y_est,ocr_ids,ocr_confidence}`
注意  由 `prepare_measurements.py` 默认调用，通常不需要单独跑
      **候选不是结论。**采纳前对着 `geometry_overlay.png` 校验一次
      `text_slots` 的位置和文字来自 OCR，可靠；`font_size_est` 和 `fill` 是估计值，
      按每三条要改一条来预期，靠 `fit_text.py` 和视觉比对收敛
      照片、插画、海报会 `abstained: true` 并只给极少候选，那里本就没有面板可找
      **不检测分隔线。**面板边缘的抗锯齿条与发丝分隔线在像素上无法区分，
      给出的候选绝大多数是噪声，分隔线自己量，一条就一次测量

## draft_elements.py
用途  把 geometry.json 变成可采纳的 manifest 元素草稿
调用  `python scripts/draft_elements.py work/geometry.json --out work/draft_elements.json`
参数  `--min-confidence 0.85`、`--no-rects`、`--no-text`
输出  `elements[]`，每项是完整的 manifest 元素，带 `provenance`(draft-geometry/draft-ocr) 与 `confidence`
注意  **绝不直接进 manifest.json**，走 `manifest_edit --adopt`；采纳即担责

## manifest_edit.py
用途  批量改 manifest 的官方通道。不手编大 JSON，不写临时 patch 脚本
调用  `python scripts/manifest_edit.py manifest.json --adopt work/draft_elements.json [--ids a,b] [--min-confidence 0.8]`
      `python scripts/manifest_edit.py manifest.json --apply-snap work/snap_report.json`
      `python scripts/manifest_edit.py manifest.json --apply-fit work/fit_report.json`
      `python scripts/manifest_edit.py manifest.json --set "label-3,label-4:y+=4"`
      `python scripts/manifest_edit.py manifest.json --select "type=text&layer=labels" --set "fill=#333"`
      `python scripts/manifest_edit.py manifest.json --patch patch.json`
参数  `--patch` 收一个完整元素对象的 JSON 数组，按 id 替换或插入，用于大批量重排
      `--dry-run` 只打印不写
输出  每次运行备份成 `manifest.json.bak`，写完自动跑 `validate_manifest.py`，校验失败自动回滚并退出非零
注意  id 找不到是错误不是静默跳过；`--apply-snap` 的 contaminated 项只打到 stderr，永不写入

## snap_boxes.py
用途  把粗框吸附成紧裁剪窗，量净空，判 clean / clean-on-fill / contaminated / snap-failed
调用  `python scripts/snap_boxes.py <image> --inventory work/inventory.json --exclude-text work/ocr_results.json --out work/snap_report.json --sheet work/snap_sheet.png`
输入  `inventory.json`: `{"objects":[{"id","bbox":[x,y,w,h],"route":"crop|regenerate-chroma|flatten"}]}`
输出  `objects[].{verdict, snapped_bbox, suggested_crop_window, clearance{4}, margin_fill, reasons[], warnings[]}`
注意  verdict 是证据不是裁判；contaminated 由模型改路由，不改判据

## inspect_regions.py
用途  异常项 1:1 局部放大，只给脚本点名的项用
调用  `python scripts/inspect_regions.py <image> --regions work/snap_report.json --ids a,b,c --out work/closeups`

## compose_svg_package.py
用途  分阶段合成。svg → pptx → package，唯一的产出入口
调用  `python scripts/compose_svg_package.py manifest.json --out figure-task/out --stage svg`
参数  `--stage svg|pptx|package`
输出  `editable.svg`、`preview.png`、`quality_report.md`、`editability_report.md`、`diagnostics/`
注意  `package` 不重建 SVG/PPTX，只更新证据；PPTX 早于 SVG 时必须先跑 `--stage pptx`

## fit_text.py / pptx_text_fit.py
用途  文字拟合与 PPTX 结构风险报告（换行、溢出、缺字、错位）
调用  `python scripts/fit_text.py manifest.json --out work/fit_report.json`
输出  `items[].{id,font_size,x,baseline_y}`，直接喂 `manifest_edit --apply-fit`

## render_pptx.py
用途  唯一允许的 PowerPoint 原生渲染入口
调用  `python scripts/render_pptx.py figure-task/out/editable.pptx --out figure-task/out/pptx_render [--allow-attach]`
注意  禁止手写 `PowerPoint.Application` 自动化，禁止 `taskkill`；`--allow-attach` 需用户授权

## 生成与切图链
`probe_palette.py --boxes` 定键色与 sheet 数｜`chroma_key.py` 抠出｜`slice_grid.py` 切分（多部件图标用 `--cells`）
`prepare_clean_plate_mask.py` 备掩膜｜`generate_clean_plate.py` 生成｜`check_plate_registration.py` 验配准（scale≈1.00 / offset≈0）
`crop_assets.py` 按 manifest 的 `source_region` 执行裁剪

## 审计
`validate_manifest.py` 字段校验｜`quality_audit.py` 19 个质量门｜`audit_editability.py` 可编辑性
三者都由 compose 自动调用，单独运行只用于定位问题
