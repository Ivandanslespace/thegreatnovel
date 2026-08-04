---
name: render-story-atlas-assets
description: 为已验证 Story Atlas 生成七张可审计的离线 SVG 图；不使用在线地图、图片 API 或伪造坐标。
---

# Render Story Atlas Assets

读取已登记 Atlas 的 JSON 图谱和 manifest，生成 `visuals/character_graph.svg`、`faction_graph.svg`、`ability_graph.svg`、`resource_chain.svg`、`region_topology.svg`、`plot_thread_graph.svg`、`stage_ladder.svg`。优先使用 Graphviz/NetworkX；没有可选依赖时使用仓库内纯 Python SVG fallback。

每张图必须包含标题、Atlas 版本、source coverage、节点/边数量、状态图例、evidence 数量和 confidence 摘要；七种图使用不同布局。Region 只表达拓扑连接，不写 lat/lon/latitude/longitude 或伪造世界坐标。缺少图谱时可以生成明确的空状态图，但不得填充虚构节点。

CLI：`novel atlas render`、`novel atlas visuals`、`novel atlas export-snapshot`。渲染只写 Atlas 的派生 `visuals/` 和本地快照，不写 `book/`、Canon 或远端。
