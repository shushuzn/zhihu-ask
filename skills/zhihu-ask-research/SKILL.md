---
name: zhihu-ask-research
description: 知乎深度回答研究流程。用于把知乎问题通过系统化检索、交叉验证、量化测算、多轮迭代，产出智库级事实陈述报告。当用户提出"知乎问题研究/深度回答/做一份研究报告/查证一个议题"等请求时使用，也适用于任何需要"事实汇编、零立场、可溯源"的深度议题研究。
---

# 知乎深度回答研究

## Overview

把"知乎问题 → 研究报告"压缩为一条可重复的流水线：初始化研究目录 → 五通道检索（公众号/Web/领域数据源/知乎官方/ima）→ 五视角收集 → 交叉验证与量化 → 多轮迭代（至少 3 轮）→ 产出成品报告。报告为**纯事实陈述、零立场**，数据可溯源，无法核实的数据在正文如实标注即收敛终点。

## 何时使用

用户请求符合以下任一情况时使用本 skill：

- 提出知乎问题并要求深度研究（"怎么看 XX""如何看待 XX""XX 是否属实"）。
- 要求把某议题做成研究报告、事实核查、数据汇编。
- 要求对某事件做量化测算、口径澄清、多维对比。
- 需要公众号文章 + Web 信源交叉验证的议题。

注意：单纯闲聊、单句事实速查（"今天几号"）、不涉及研究深度的话题不使用本 skill。

## 工作目录约定

研究工作在本项目（d:\OpenClaw\zhihu-ask）内进行：

- `research/<slug>/`：每个问题一个目录，含 `plan.md`（问题界定）、`report.md`（成品报告）、`process_notes.md`（检索与踩坑记录）、`round_notes.md`（迭代问题清单）、`.progress.json`（轮次/阶段进度）。
- `templates/`：报告、计划、笔记模板。
- `docs/KEYWORDS.md`：检索词库，有效关键词回填于此。
- **隐私边界**：`research/`、`plan.md`、`.codebuddy/` 仅存本地，绝不推入公开仓库；`git add -A` 前必查 `git status`，pre-commit hook 自动拦截。

## 核心流程

### 阶段 0 · 问题接收与范围界定

1. 接收问题。若为知乎链接，先 `web_fetch`；失败（403/登录墙）则请用户粘贴标题或描述。
2. 拆解问题：主概念、关键实体、隐含前提、真实诉求（科普/建议/案例）。
3. 检索项目内经验：`python tools/rag_search.py "<主概念 关键实体>"`，把命中片段（流程规则/关键词词库/模板结构/踩坑沉淀）作为本次检索起点；索引缺失时先 `python tools/rag_build.py`。
4. 判定查询类型：深度优先（单议题多角度）/ 广度优先（多个独立子议题）/ 直接查询（事实速查，一轮即可）。
5. 写 `tools/start.json`（参考 `tools/start.example.json`，可含 `zhihu_keywords` 与 `zhihu_mode: zhihu|global|both`），执行 `python tools/research_start.py --config tools/start.json`（自动初始化目录 + 公众号检索 + 知乎官方检索 + 素材库落盘）。

### 阶段 1 · 信息检索（五通道，执行顺序 F → E → A → B → C → Z）

- 步骤 0 · flomo 已有报告查重（**执行顺序最先**）：用问题主题词（从 plan.md/start.json 的 question 取，主代理判断）调 flomo MCP `memo_search`——relevance ≥0.9（已有本报告）→ 复用/更新不重复研究；0.5-0.9（主题相近）→ 参考已有笔记素材；<0.5 → 正常检索；结果记 plan.md；flomo 未配置时跳过不阻塞（详见 `docs/SOP.md` 阶段 1 步骤 0 与 `docs/TOOLS.md` flomo 章节）。
- 通道 E（ima 知识内容，**执行顺序第一**，可用时必用）：两级检索——E1 经验检索（`search_knowledge_base` 定位库 → 个人库 `search_knowledge`，命中片段纳入检索起点，与本地 `rag_search.py` 互补）；E2 内容素材检索（按领域取 `docs/IMA_LIBRARIES.md` 候选订阅库逐库 `search_knowledge`，命中落盘 `gathered_ima.md`，计入有效通道；原文用 `fetch_media_content`）。连接器未连接时跳过不阻塞（见 `docs/TOOLS.md` ima 章节与 `docs/IMA_INTEGRATION.md` 隐私分级）。
- 通道 A（公众号，必用）：经 `tools/wechat_search.py` 检索，UTF-8 文件传参规避中文乱码，带时间参数（默认近 1 年），`--output` 落盘素材库。
- 通道 B（Web）：`web_search`/`web_fetch` 获取官方数据、研报、新闻，优先一手来源。
- 通道 C（领域数据源，按需）：金融/企业类优先用——finance 插件（财务建模）；通达信 `tdx-connector`（行情/K线/F10 财务/选股/宏观/新闻/公告/研报，code 先 `tdx_lookup_stock` 查码）；企查查 `qcc-company`（工商/股东/实控人穿透/财务/上市信息，先 `get_company_by_query` 锁定实体，多候选须用户确认）。纪律见 `docs/TOOLS.md`「领域连接器」与 `docs/CONVENTIONS.md` 第 8 节。
- 通道 Z（知乎官方，可用时必用）：经 `tools/zhihu_search.py` 调用 zhihu-cli（知乎开放平台官方 CLI），检索知乎站内与全网，`--output` 落盘素材库 `gathered_zhihu.md`；前置为 zhihu skill 已 setup 且 Access Secret 已配置（`zhihu-cli auth set --secret-stdin`），未认证报 AUTH_REQUIRED 不阻塞其余通道。
- 校验：素材库必须非空且含标题/公众号（或作者）/链接；至少两个通道有有效素材才进入阶段 2。

### 阶段 2 · 多视角信息收集

按五视角逐项覆盖，每个视角至少一轮检索：A 公众号观点、B Web 事实、C 领域分析、D 差异化（高赞/争议）、E 反方风险。关键子问题逐一覆盖不遗漏。子代理 Prompt 模板见 `docs/AGENT_PROMPTS.md`（当前 `research_subagent` 不可用，主代理直执，把五视角当检索清单逐项完成）。

### 阶段 3 · 交叉验证与量化

- 每个关键数字标注数据级别（一手/二手/推断）；多源冲突以「最新 + 一手优先 + 口径一致」取舍。
- 媒体转述数字尽量回溯一手来源；无法取得的一律标"仅媒体口径"。
- 做至少一项量化测算（市场规模/成本结构/情景推演），把模糊判断变成数字。
- 数据不可得 → 标注"待核实"或"仍无法核实"，用推断+区间呈现，不编造。

### 阶段 4 · 报告生成与多轮迭代

1. 按 `templates/research_report_TEMPLATE.md` 产出 `report.md`。
2. **多轮迭代（强制，禁止询问用户是否继续）**：
   - 最低轮次按领域：**财政/宏观/金融 ≥10 轮**，其他领域 ≥3 轮；用户说"继续迭代"即必须进入下一轮，直至问题清单清空。
   - 跑 `python tools/iter_research.py --slug <slug>` 生成下一轮问题清单模板（历史轮次自动归档 round_notes_r<N>.md）。
   - **问题清单由主代理人工编写**：阅读报告中标注"仍无法核实/推算"的内容与数据口径缺口，逐条整理成明确、可执行的问题。不用自动提取（机械拆句语义不清）。
   - 带着问题补检索/深化 → 直接在 `report.md` 上更新（不创建 vN 版本文件）。
   - 3 轮后问题清单仍有未处理内容必须继续，直到处理完；无法补足的标注"仍无法核实"后移除。
3. **报告必须是成品**：正文禁止"第 N 轮/迭代"等过程性字样；无法核实的数据在正文如实标注即为收敛终点。
4. 写 `process_notes.md`：有效关键词与踩坑点（参考 `templates/process_notes_TEMPLATE.md`）。
5. **沉淀（必做）**：有效关键词回填 `docs/KEYWORDS.md` 对应领域区块。
6. 回填本地 `plan.md` 索引状态为"已完成"。

### 质量检查（交付前必跑）

```bash
python tools/quality_check.py --file research/<slug>/report.md
```

自动扫描：立场词、框架词、评价词、感叹号/反问句、无来源数字（启发式）、**参考文献标注（参考文献区链接行不得带"一手/二手/推断"等分级标注，分级只在正文）**。检出项为启发式，需人工确认。退出码 1 表示有待确认项。

### 进度校验（阶段 2 前）

```bash
python tools/check_progress.py --slug <slug> --require phase1_done
```

通过退出码 0，阻塞退出码 1，对应 SOP「输出未达校验即阻塞」。

## 报告风格（纯事实陈述，零立场）

- 只陈述事实、数据、结构、口径，不做价值判断；不设结论、不表立场、不贴标签、不给建议、不替读者判断，判断权留给读者。
- 数字、日期、百分比、金额必须带来源（括注或脚注链接），标注数据口径（如"展示产品口径""媒体估算"）。
- 拆解/推算必须标注"推算"和口径假设。
- 参考文献为**纯链接列表**（`[标题](url)`），不带"一手/二手/推断"标注；数据分级标注只在正文。
- 去 AI 味：删框架词（先说结论/总结一下/综上所述）、不用"其一其二"、不用感叹号/反问句、数字嵌叙述、小标题像事实目录。
- 完整规范见 `docs/STYLE_GUIDE.md`。

## 配套资源（项目内，直接引用，不在本目录复制）

- 工具：`tools/`（research_start、init_research、iter_research、quality_check、check_progress、wechat_search、zhihu_search、git_protect、install_git_hooks、health_check），详细用法见 `docs/TOOLS.md`（含 ima 连接器通道 E）。
- 流程：`docs/SOP.md`（完整 SOP + 附录 A 执行级流程）、`docs/CHECKLIST.md`（发布前检查清单）。
- 词库：`docs/KEYWORDS.md`（预置关键词 + 回填机制）。
- 环境约定：`docs/CONVENTIONS.md`（PowerShell 中文乱码文件传参、git 约定、禁止 force、隐私边界、ima 约定）。
- 模板：`templates/`（research_report_TEMPLATE.md、research_plan_TEMPLATE.md、process_notes_TEMPLATE.md）。
- ima：`docs/IMA_INTEGRATION.md`（接入评估、工具用法、隐私分级矩阵）。
