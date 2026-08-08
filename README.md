# zhihu-ask — 知乎深度回答项目

把「知乎问题 → 深度研究 → 事实陈述报告」固化为一条可复用流水线。

- 仓库：https://github.com/shushuzn/zhihu-ask
- 跨会话工具/环境限制与统一做法，先读 `docs/CONVENTIONS.md`。
- 研究产出（`research/`）仅存本地，绝不推入公开仓库。

## 目录结构

```
zhihu-ask/
├── README.md                      # 本文件，项目入口
├── docs/
│   ├── SOP.md                     # 五阶段可执行流程（核心标准）
│   ├── AGENT_PROMPTS.md           # 子代理可复制 Prompt 模板（A–E）
│   ├── KEYWORDS.md                # 领域预置检索关键词库
│   ├── CHECKLIST.md               # 发布前质量检查清单
│   ├── STYLE_GUIDE.md             # 知乎文风与排版指南（纯事实、零立场）
│   ├── TEMPLATE_INDEX.md          # 模板说明与使用规则
│   ├── TOOLS.md                   # 项目内工具说明
│   ├── CONVENTIONS.md             # 环境约定（乱码处理/git 用法/zhihu-cli/ima/领域连接器）
│   ├── IMA_INTEGRATION.md         # ima 知识库接入评估与隐私分级
│   └── IMA_LIBRARIES.md           # ima 领域-订阅库映射（通道 E2 候选库）
├── tools/
│   ├── research_start.py          # 一键研究启动器（通道 A 公众号 + 通道 Z 知乎）
│   ├── wechat_search.py           # 公众号检索包装
│   ├── zhihu_search.py            # 知乎开放平台检索包装（通道 Z）
│   ├── init_research.py           # 研究目录初始化
│   ├── iter_research.py           # 多轮迭代（问题清单模板 + 轮次记录）
│   ├── quality_check.py           # 报告质量自动检查
│   ├── check_progress.py          # 阶段进度校验
│   ├── git_protect.py             # 提交前检查
│   ├── install_git_hooks.py       # pre-commit hook 安装
│   ├── health_check.py            # 项目健康自检
│   ├── start.example.json         # 一键启动配置示例
│   ├── keywords.example.json      # 关键词文件模板
│   └── init.example.json          # 初始化配置示例
├── templates/
│   ├── research_plan_TEMPLATE.md      # 单次问题研究计划
│   ├── research_report_TEMPLATE.md    # 深度研究报告
│   └── process_notes_TEMPLATE.md      # 检索与踩坑记录
└── skills/zhihu-ask-research/         # 本项目研究流程 skill 入口
```

## 快速上手

0. 新会话先自检：`python tools/health_check.py`，确认环境就绪（含通道 Z 认证状态）。
1. 一键启动研究：写 `tools/start.json`（参考 `tools/start.example.json`）后运行
   `python tools/research_start.py --config tools/start.json`，自动初始化目录、跑公众号检索（通道 A）与知乎官方检索（通道 Z）并生成素材库。
2. 在 `research/<topic_slug>/plan.md` 补齐「问题界定」与「检索关键词」（可参考 `docs/KEYWORDS.md` 选词）。
3. 按 `docs/SOP.md` 阶段 1–3 执行检索与研究（主代理直执，**通道 E ima 先行** → 公众号/Web/领域数据源（finance、通达信、企查查）/知乎 五通道；ima 候选库见 `docs/IMA_LIBRARIES.md`）。
4. 按模板产出 `report.md`，进入多轮迭代（至少 3 轮，问题清单清空才收敛；质量检查见 `docs/CHECKLIST.md`）。
5. 完成后写 `process_notes.md` 记录检索与踩坑，有效关键词回填 `docs/KEYWORDS.md`，回填 `plan.md` 状态，删除临时 config 文件。

## 交付物约定

每次研究固定产出 3 类文件：计划（plan.md）、报告（report.md）、经验笔记（process_notes.md）。领域不设限；报告为纯事实陈述、零立场，数据分级标注只在正文，参考文献为纯链接列表。
