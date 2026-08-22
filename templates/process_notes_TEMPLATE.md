# 经验笔记：{{topic_slug}}

> 日期：{{YYYY-MM-DD}} | 问题：{{知乎问题完整标题}} | 领域：{{...}}

## 本次有效关键词

- {{关键词组合 + 效果说明}}，示例：`- "天然气 占一次能源 15%"（Web，命中目标政策来源）`

## 踩坑点

- {{遇到的坑 + 下次规避方式}}

## 多轮迭代记录（追加式，每轮一条）

- **第 N 轮**：{{本轮问题清单要点（见 round_notes.md）+ 解决结果 + 新增数据/口径修正。多轮迭代时在下方持续追加，保留完整迭代轨迹}}

## 质量校验

- **结构校验**（check_report_structure.py）：{{通过 / 检出项及修复}}
- **quality_check**：{{命中项列表 + 人工确认结论（如"2 处为启发式误报，人工确认合规"）}}
- **去 AI 腔**（check_ai_voice.py）：{{通过 / 命中项及改写}}
- **国标**（check_gbt_refs.py）：{{通过 / 检出项及修复}}
- **违规引用**（check_citation_validity.py）：{{通过 / 检出项及修复；联网核验失败须重试或显式 --offline}}
- **矛盾与废话**（check_consistency.py）：{{通过 / 检出项及修复}}
- **轮次校验**（check_progress --require_round auto）：{{N/1 轮达标}}

## 必做收尾

- **KEYWORDS 回填**：{{新增领域 / 关键词数}}（SQLite 主存储：`python tools/keywords_db.py --add ...`，再 `--export docs/KEYWORDS.md` 同步可读文件）
- **plan.md 索引**：{{已完成（N 轮迭代）}}
- **git 推送**：{{commit hash，推送内容}}

## 待改进

- {{流程或模板的改进建议；如涉及模板改动，同步更新 templates/ 与 TEMPLATE_INDEX.md}}
