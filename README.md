# zhihu-ask — 知乎深度回答项目

把「知乎问题 → 深度研究 → 可发布回答」固化为一条可复用流水线。

- 仓库：https://github.com/shushuzn/zhihu-ask
- 跨会话工具/环境限制与统一做法，先读 `docs/CONVENTIONS.md`。

## 目录结构

```
zhihu-ask/
├── README.md                      # 本文件，项目入口
├── docs/
│   ├── SOP.md                     # 五阶段可执行流程（核心标准）
│   ├── AGENT_PROMPTS.md           # 子代理可复制 Prompt 模板（A–E）
│   ├── KEYWORDS.md                # 领域预置检索关键词库
│   ├── CHECKLIST.md               # 发布前质量检查清单
│   ├── STYLE_GUIDE.md             # 知乎文风与排版指南
│   ├── TEMPLATE_INDEX.md          # 模板说明与使用规则
│   ├── TOOLS.md                   # 项目内工具说明
│   └── CONVENTIONS.md             # 环境约定（乱码处理/git 用法）
├── tools/
│   ├── research_start.py          # 一键研究启动器
│   ├── wechat_search.py           # 公众号检索包装
│   ├── init_research.py           # 研究目录初始化
│   ├── git_protect.py             # 提交前检查
│   ├── install_git_hooks.py       # pre-commit hook 安装
│   ├── health_check.py            # 项目健康自检
│   └── keywords.example.json      # 关键词文件模板
├── templates/
│   ├── research_plan_TEMPLATE.md      # 单次问题研究计划
│   ├── research_report_TEMPLATE.md    # 深度研究报告
│   └── process_notes_TEMPLATE.md      # 检索与踩坑记录
```

## 快速上手

0. 新会话先自检：`python tools/health_check.py`，确认环境就绪。
1. 一键启动研究：写 `tools/start.json`（含问题/领域/slug/关键词，参考 `tools/TOOLS.md`）后运行
   `python tools/research_start.py --config tools/start.json`，自动初始化目录、跑公众号检索并生成素材库。
2. 在 `research/<topic_slug>/plan.md` 补齐「问题界定」与「检索关键词」（可参考 `docs/KEYWORDS.md` 选词）。
3. 按 `docs/SOP.md` 阶段 1–3 执行检索与研究（主代理直执）。
4. 按模板产出 `report.md`（质量检查见 `docs/CHECKLIST.md`）。
5. 完成后写 `process_notes.md` 记录检索与踩坑，回填 `plan.md` 状态，并删除临时 config 文件。

## 交付物约定

每次研究固定产出 3 类文件：计划、报告、经验笔记。领域不设限，优先支持金融/产品/AI 三类（对应挂载插件）。
