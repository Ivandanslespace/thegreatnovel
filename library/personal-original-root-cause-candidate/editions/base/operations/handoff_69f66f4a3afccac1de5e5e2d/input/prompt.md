$process-novel-handoff

请先使用仓库内的 $process-novel-handoff Skill，领取并验证 handoff_id=handoff_69f66f4a3afccac1de5e5e2d。

领取成功后，根据 task.json 调用 $bootstrap-story-atlas，严格执行 requested_stage=ATLAS_BOOTSTRAP。

Atlas 输出必须先写入 task artifacts/story_atlas，再由 Python 校验并登记；不得直接修改 Canon。

严格读取任务目录中的 task.json、prompt.md、metric_context.json、context_manifest.json 和 output_schema.json。
不得修改 book；不得批准写入正史；不得批准改写 Campaign；不得启用 Edition。
结束时必须严格按 output_schema.json 写回 result.json 和 status.json；需要作者决定时写 waiting_for_user.json 并进入 WAITING_FOR_USER。