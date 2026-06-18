# Camera Grid Rendering

这个案例展示了复杂论文图的混合重建。版面、标题、流程线、张量示意和公式被重建为可编辑对象，视频帧、相机网格和三维图等视觉证据则作为可替换图片资产保留。

This case demonstrates a mixed reconstruction of a complex paper figure. Layout, labels, connectors, tensor diagrams, and formulas are editable, while video frames, camera grids, and 3D plots remain replaceable image assets.

## Original / 原图

![Original Camera Grid Rendering figure](./source.png)

## Reconstructed preview / 重建预览

![Reconstructed Camera Grid Rendering figure](./preview.png)

## Files / 文件

- [Editable SVG](./editable.svg)
- [Self-contained SVG / 内嵌资产 SVG](./editable_embedded.svg)
- [Native PowerPoint / 原生 PPTX](./editable.pptx)
- [Reconstruction manifest](./manifest.json)
- [Quality report](./quality_report.md)
- [Editability report](./editability_report.md)

The reconstruction contains 55 editable text elements, 117 structural vector elements, 15 editable equations, and 25 source-preserved assets.
