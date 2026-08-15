# 模板索引

| 模板文件 | 用途 | 产出位置 | 版本 |
|---|---|---|---|
| `research_plan_TEMPLATE.md` | 单次问题研究计划 | `research/<topic_slug>/plan.md` | |
| `research_report_TEMPLATE.md` | 深度研究报告 | `research/<topic_slug>/report.md` | |
| `note_TEMPLATE.md` | 模块化笔记（标签行 + 独立可读四要求） | `research/<topic_slug>/notes/<NN>_*.md` | |
| `process_notes_TEMPLATE.md` | 检索与踩坑记录 | `research/<topic_slug>/process_notes.md` | |

**变更机制**：模板内容变更须同步更新本表与 SOP；不维护版本号（项目已清除版本标注）。

## 使用规则

1. 复制模板，不直接修改 `templates/` 下的原件；模板改动需同步更新本索引与 SOP。
2. `topic_slug` 用英文小写短横线（如 `example-topic`、`topic-2026`）。
3. 每份计划、报告、笔记都必须来自对应模板骨架，保证结构与信息完整。
4. 模板中的 `{{...}}` 占位符为必填项，输出前全部替换为实际内容。
5. 领域差异（金融/产品/AI）通过模板「领域专项栏」体现，不另建模板。

## 质量约束

| 模板 | 内置质量约束 |
|---|---|
| `research_plan_TEMPLATE.md` | 步骤 0 flomo 查重（最先执行）；执行顺序 F→E→A→B→C→P；素材库命名 gathered_ima/wechat/web/arxiv/preprints；迭代轮次默认 1 轮（有内容无法一轮解决才追加）；五视角主代理直执（阶段 2 现状）；交付物含必做收尾（flomo 上传 + git 推送） |
| `research_report_TEMPLATE.md` | 过程字样零容忍（quality_check 拦截）；**报告形态**：H1 标题 → 结论段 → `###` 无编号小节（按主题切分，数量由内容自然决定，不设上限）→ `## 参考文献`（无顶层内容章节，check_report_structure 校验）；**组织按内容选型**：并列多条同类信息用 `1. 2. 3.` 有序列表（点数由内容自然决定、禁止凑数），多实体对照用表格，因果/演化逻辑链用连贯叙述段，正文无无序 bullet；**算式按需但必验**：有计算价值的内容算式必须写、在句中（如"时滞为 1948 − 1648 = 300 年"）且经 Python 验证（验证脚本留存研究目录），禁止凑数硬造也禁止该写不写；**论证完整**：数学/证明/机制类内容给完整论证链（定理-引理-证明或步骤归约），禁止只给方法名概述、禁止省略证明步骤，来源论文论证以全文为准；**未来预测必做多情景+历史周期检验+可迁移兜底+不确定性标注**（预测类报告硬性要求）；**测算未融入拦截**（check_report_structure：禁止"**测算 N：**"或"假设前提/计算口径"独立行）；概念主体（来源材料不当主语；句首禁裸"这篇/该篇/本篇/此篇"）；独立组织（不照搬单一来源）；公式一律 LaTeX；正文 [n] 引注；结论 ≤300 字符、事实归并；文风对照 `docs/STYLE_GUIDE.md` |
| `note_TEMPLATE.md` | 首行标签 `#维度1 #维度2 #主题/<slug>`；每篇自含出处（GB/T 7714 来源段 + 来源类型）；独立可读四要求（不依赖其他笔记/不依赖来源内部编号/指代明确） |
| `process_notes_TEMPLATE.md` | 追加式迭代记录；质量校验（结构/quality_check/去AI腔/国标/违规引用/矛盾/轮次）；必做收尾证据记录 |

**交付前必跑命令**（与 CHECKLIST 一致）：
```bash
python tools/check_report_structure.py --file research/<slug>/report.md
python tools/quality_check.py --file research/<slug>/report.md
python tools/check_progress.py --slug <slug> --require_round auto
```
