# zhihu-ask — 知乎深度回答项目

本仓库提供一条可复用的研究流水线，将知乎问题转化为事实陈述型的深度研究报告。

- 仓库地址：https://github.com/shushuzn/zhihu-ask
- 环境约定与跨会话统一做法，请参阅 `docs/CONVENTIONS.md`。
- 研究产出（`research/` 目录）仅存本地，不得推入公开仓库。
- 完整流程标准见 `docs/SOP.md`，工具说明见 `docs/TOOLS.md`，架构图见 `docs/architecture.md`（PNG 不入库，本地渲染：`python docs/render_svg.py`）。

## 目录结构

```
zhihu-ask/
├── README.md                      # 项目入口
├── plan.md                        # 问题索引表（本地，不入库）
├── docs/
│   ├── SOP.md                     # 阶段化可执行流程（核心标准）
│   ├── TOOLS.md                   # 项目内工具说明
│   ├── CHECKLIST.md               # 发布前质量检查清单
│   ├── STYLE_GUIDE.md             # 知乎文风与排版指南
│   ├── TEMPLATE_INDEX.md          # 模板说明与使用规则
│   ├── CONVENTIONS.md             # 环境约定（乱码处理/git/领域连接器/参考文献学术纪律）
│   ├── KEYWORDS.md                # 关键词库可读导出（主存储为 SQLite，本地沉淀，不入库）
│   ├── IMA_INTEGRATION.md         # ima 知识库接入评估与隐私分级
│   ├── IMA_LIBRARIES.md           # ima 领域-订阅库映射
│   ├── architecture.md            # 流水线架构图（mermaid 源码 + 渲染 PNG）
│   ├── architecture_render.html   # 架构图 SVG 渲染源（render_svg.py 生成 PNG）
│   └── render_svg.py              # 架构图渲染脚本（playwright）
├── tools/                         # 44 个工具（详见 docs/TOOLS.md 测试登记表）
│   ├── research_start.py          # 研究启动器（初始化 + 领域判定 + 公众号初检）
│   ├── run_pipeline.py            # 一键流水线（启动 + 收尾八件套门禁编排）
│   ├── init_research.py           # 研究目录初始化（plan/report/process_notes/notes/.progress.json）
│   ├── iter_research.py           # 多轮迭代研究（round_notes.md）
│   ├── channel_state.py           # 通道单一真相源（F/E/A/B/C/P + 素材文件映射）
│   ├── mark_channel.py            # 通道完成态登记（done/empty/skip + note）
│   ├── check_progress.py          # 阶段/轮次/落报告门禁校验
│   ├── check_all.py               # 全库体检（九列汇总）
│   ├── check_report_structure.py  # 报告结构校验
│   ├── quality_check.py           # 报告质量自动检查
│   ├── check_ai_voice.py          # 去 AI 腔检查
│   ├── check_gbt_refs.py          # 参考文献 GB/T 7714 校验
│   ├── check_citation_validity.py # 违规引用联网核验（作者/题名/佚名/死链）
│   ├── check_consistency.py       # 矛盾与废话检查（项目自检）
│   ├── clean_workspace.py         # 工作区缓存/临时文件清理
│   ├── maintain.py                # 一键维护：清理+回归+一致性+git status
│   ├── check_flomo_note_refs.py   # flomo 笔记素材合规检测
│   ├── health_check.py            # 项目健康自检（会话启动）
│   ├── note_assemble.py           # 模块化笔记组装 report_draft 骨架
│   ├── note_upload.py             # 笔记逐条质检上传 flomo（--update 原地更新）
│   ├── flomo_search.py            # flomo 检索（查重）
│   ├── flomo_upload_full.py       # flomo 单条完整版上传（绕过客户端拦截）
│   ├── report_to_flomo.py         # 报告转 flomo 格式存档（本地，不上传）
│   ├── report_to_docx.py          # 报告转 Word（公式转 OMML）
│   ├── report_images.py           # AI 概念图封面生成
│   ├── web_search.py              # Web 多引擎搜索（ddgs/bing/tavily/openalex/crossref + curl 兜底）
│   ├── web_fetch.py               # Web 页面抓取（Jina→直连→代理 三级降级）
│   ├── wechat_search.py           # 公众号检索（通道 A，sogou/ddgs 降级）
│   ├── wechat_publish.py          # 公众号草稿推送（按需）
│   ├── preprint_search.py         # 学术预印本聚合（arxiv+bioRxiv+浪淘沙+PSSXiv，通道 P）
│   ├── arxiv_search.py            # arxiv 单独检索（WebFetch 降级/curl 兜底）
│   ├── rag_build.py / rag_search.py / knowledge_store.py / keywords_db.py  # RAG 与关键词库（SQLite）
│   ├── tdx_query.py               # 通达信查询（行情/K线/F10/选股）
│   ├── latex_unicode.py           # LaTeX → 可读 Unicode（公众号展示）
│   ├── syllogism_check.py         # 三段论逻辑校验（实验性）
│   ├── net_check.py               # 外网出口检测
│   ├── env_loader.py              # .env 敏感配置加载
│   ├── internal_files.py          # 内部文件保护公共模块
│   ├── git_protect.py             # 提交前检查
│   ├── install_git_hooks.py       # pre-commit hook 安装
│   └── start.example.json         # 启动配置示例
├── templates/
│   ├── research_plan_TEMPLATE.md      # 单次问题研究计划
│   ├── research_report_TEMPLATE.md    # 深度研究报告
│   ├── note_TEMPLATE.md               # 模块化笔记模板（标签+内容+来源+来源类型）
│   └── process_notes_TEMPLATE.md      # 检索与踩坑记录
├── skills/zhihu-ask-research/         # 研究流程 skill
└── research/                          # 研究产出（本地，不入库）
```

## 使用流程

1. **初始化研究**：写 `tools/start.json`（question/domain/slug/priority/keywords/days），执行 `python tools/research_start.py --config tools/start.json`——自动创建 `research/<slug>/`（plan.md/report.md/process_notes.md/notes/ + .progress.json）、判定领域档位（学术科研/科技产业/财经时政 → 通道优先级）、公众号初检；也可用 `python tools/run_pipeline.py --config tools/start.json` 一并打印 agent 待办清单。
2. **六通道检索**（顺序 F→E→A→B→C→P，优先级按领域矩阵，`docs/SOP.md`）：
   - F flomo 查重（最先）：`flomo_search.py`；≥0.9 复用/更新、0.5~0.9 参考（须 GB/T 合规，`check_flomo_note_refs.py`）、<0.5 正常检索；旧笔记过时信息原地更新
   - E ima（P1，未配置记 skip）· A 公众号（`wechat_search.py`，分档）· B Web（`web_search.py` 多引擎 + `web_fetch.py` 三级降级，P0 通用）· C 领域连接器（通达信/企查查/智慧芽，分档）· P 学术预印本（`preprint_search.py --platform all` 四平台，分档）
   - 素材落盘 `gathered_*.md`；通道完成态登记（A/P 落盘自动，F/E/B/C 用 `mark_channel.py`）；门禁 `check_progress.py --require report_channels`
3. **模块化笔记**：检索完成后撰写 `notes/*.md`（扁平目录、首行标签：`#维度1 #维度2 #主题/slug`；索引笔记 `00_index.md` 用 `#索引`；每篇含标签行+标题+正文+来源 GB/T+来源类型）；`00_index.md` 以 `## 问题/历史/证明/结论/缺口` 串联；`note_assemble.py --slug` 按索引组装 `report_draft.md` 骨架。
4. **产出 report.md**：默认一轮成稿；结论 ≤300 字符、首行无"结论"字样；公式一律 LaTeX；正文 [n] 引注；概念主体、独立组织、无过程字样；存在无法核实的内容或数据口径缺口时追加轮次（`iter_research.py`）。
5. **算式按需但必验**：有计算价值的内容算式必须写、融入小节叙述；数学/证明类给完整论证链（定理-引理-证明）；每条算式经 `verify_calcs.py` Python 实际验证，验证脚本留存研究目录；禁止凑数硬造也禁止该写不写。
6. **收尾门禁**：`python tools/run_pipeline.py --slug <slug>` 自动编排八件套——check_report_structure → quality_check → check_ai_voice → check_gbt_refs → check_citation_validity（作者/题名联网核验）→ check_consistency → check_progress（轮次+落报告），随后生成 `report.docx`（report_to_docx.py）与 `flomo_full.md` 本地存档（report_to_flomo.py，不上传），并跑 `check_all.py` 全库体检。
7. **产出与沉淀**：`note_upload.py research/<slug>/notes/` 逐条质检后上传 flomo（索引/报告禁止上传）；`report_images.py` 生成 AI 概念图封面 `ai_cover.png`（纯抽象视觉、合规/主题/构图三重复检）；按需 `wechat_publish.py` 推送公众号草稿；有效关键词写入 SQLite 关键词库（`tools/keywords_db.py --add`）并 `--export docs/KEYWORDS.md` 同步、写 `process_notes.md`、更新 `plan.md` 索引为已完成。
8. **收尾提交**：git 提交并推送（仅公开文件；research/ 与 plan.md 不入库；pre-commit hook 拦截内部文件）。

## 环境与配置

| 配置项 | 用途 | 位置 / 方式 |
|---|---|---|
| flomo MCP | 查重、笔记上传、素材合规检测 | WorkBuddy 连接器管理中配置；未配置时查重/上传跳过 |
| Agnes API key | AI 概念图封面生成 | 环境变量 `AGNES_API_KEY`；凭证不入项目文件与日志 |
| TAVILY_API_KEY | web_search tavily 引擎（免费层 1000 次/月） | 环境变量或项目根 `.env`（`tools/env_loader.py` 加载）；未配置自动跳过 |
| git 提交身份 | 提交时以 `-c user.name/user.email` 临时指定 | 或通过 `git config --global` 配置 |
| ima 连接器 | 通道 E 历史经验与素材检索 | 连接器托管授权；脚本化需 OpenAPI Client ID 与 API Key，存于 `~/.config/ima/` |
| 领域连接器 | 通达信（行情/财务）、企查查（工商穿透）、智慧芽（专利/论文） | 连接器托管授权，无项目内凭证；注意额度限制 |
| HTTPS_PROXY | 本机无外网出口时经代理联网（ArXiv 429 限流时降级 WebFetch） | 环境变量 `HTTPS_PROXY`，默认 `http://127.0.0.1:7897/` |

**凭证纪律**：所有凭证仅存于 `~/.config/` 或环境变量，不得写入项目文件、日志或提交至 git。

## 交付物约定

每次研究固定产出：研究计划（plan.md）、研究报告（report.md）、模块化笔记（notes/*.md + 00_index）、经验笔记（process_notes.md）、算式验证脚本（verify_calcs.py）、配图（ai_cover.png）及 flomo 上传记录。

**报告结构规范**：

- 标题不含「研究报告：」前缀、不带括号；结论置于报告开头：一两句话（≤300 字符、无标题、首行不写"结论"字样），直接给出事实判断
- 章节组织：结论段 → 关键事实与数据（`###` 小节不带编号、数量由内容决定）→ 参考文献（GB/T 7714-2015 著录，条目间空行分隔）
- 正文按顺序编码制标注 [n] 引注，来源著录归文末「参考文献」区；`check_gbt_refs.py` 校验引注与文献一一对应
- 参考文献区禁止 LaTeX（数学符号用 Unicode/文字）；正文公式一律 `$...$` LaTeX
- 报告为纯事实陈述、零立场；无法核实的数据在正文如实标注即为收敛终点

## 关键约定

- 领域连接器：通达信代码先 `tdx_lookup_stock` 查码；企查查先锁定实体、多候选须用户确认；智慧芽专利+论文各一次调用。
- flomo 查重命中已有笔记（relevance ≥0.9）不重复研究：本地目录缺失时拉取笔记只补新信息；命中的 flomo 条目可作参考素材，但须有符合 GB/T 7714-2015 的参考文献（`check_flomo_note_refs.py` 检测）。
- 参考文献学术纪律（`docs/CONVENTIONS.md`）：作者/题名须与注册库（CrossRef/arXiv）核验一致，佚名误用、编造作者、死链均为硬伤（`check_citation_validity.py` 联网核验，`check_all.py` 全库体检「违规引」列强制）。
- ima 隐私分级：素材库、研究计划与问题原文禁止上云；凭证存于 `~/.config/ima/`。
- 研究流程细节见 `skills/zhihu-ask-research/SKILL.md`。
