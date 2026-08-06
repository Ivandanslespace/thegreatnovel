# Generated skill schema

Create only files justified by selected dimensions.

```text
<generated-skill>/
├── SKILL.md
├── sources.md
├── synthesis.md
├── craft-controls.md
├── <selected-dimension>.md
└── books/<source-id>/overview.md
```

系统导入器随后会在发布副本中生成 `machine/` Distillation Package。该目录只包含实际
产生的结构化 artifact：`package.json`、`observations.jsonl`、`evidence_mappings.jsonl`，
以及可选的 `literary_arcs.json`、`craft_controls.json`、`continuity_candidates.jsonl`、
`character_voice_profiles.json` 和 `theme_questions.json`。这些文件使用严格 Pydantic
合同；Literary Arc 不是 Initialization Processing Arc，任何观察都不是 Canon。

`SKILL.md` stays concise and links to source and dimension files. `sources.md` records source ID,
metadata, extraction status, chapter confidence and warnings. Dimension findings use observation,
mechanism, transferable principle, controls, risks and confidence, with a source ID plus locator.
Cross-source synthesis separates convergence, divergence, incompatible assumptions and new
combinations. Never store a quote bank or a searchable substitute for the original.

Depth controls scale chapter evidence: compact uses overviews and high-signal findings, standard
uses a chapter map plus selective cards, and deep uses bounded analysis of every chapter.
