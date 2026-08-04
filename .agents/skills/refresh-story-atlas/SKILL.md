---
name: refresh-story-atlas
description: 在 source、edition 或当前边界发生可审计变化后刷新版本化 Story Atlas；保留稳定实体 ID 和旧版本，不写入 Canon。
---

# Refresh Story Atlas

读取上一版 Atlas、当前 source/edition hash、最新初始化报告和变更证据；只生成新的不可变 `story_atlas/versions/<atlas_id>/` 派生版本。必须执行影响范围、实体 ID、证据、冲突、Rolling Horizon 和七张 SVG 校验。旧 Atlas 不覆盖、不删除；未来路线不能被写成逐章固定大纲。
