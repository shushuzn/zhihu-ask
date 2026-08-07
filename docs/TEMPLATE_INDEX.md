# 模板索引

| 模板文件 | 用途 | 产出位置 |
|---|---|---|
| `research_plan_TEMPLATE.md` | 单次问题研究计划 | `research/<topic_slug>/plan.md` |
| `research_report_TEMPLATE.md` | 深度研究报告 | `research/<topic_slug>/report.md` |
| `process_notes_TEMPLATE.md` | 检索与踩坑记录 | `research/<topic_slug>/process_notes.md` |

## 使用规则

1. 复制模板，不直接修改 `templates/` 下的原件；模板改动需同步更新本索引与 SOP。
2. `topic_slug` 用英文小写短横线（如 `example-topic`、`topic-2026`）。
3. 每份计划、报告、回答、笔记都必须来自对应模板骨架，保证结构与信息完整。
4. 模板中的 `{{...}}` 占位符为必填项，输出前全部替换为实际内容。
5. 领域差异（金融/产品/AI）通过模板「领域专项栏」体现，不另建模板。
