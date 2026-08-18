---
name: zhihu-ask-research
description: 知乎深度回答研究流程（唯一权威流程标准）。用于把知乎问题通过系统化检索、交叉验证、多轮迭代，产出纯事实陈述报告。
---

# 知乎深度回答研究

## 概述

研究流水线: 问题接收 → flomo 查重(命中已有笔记→复用还原, 不做标记不更新) → 多通道检索 → 写笔记 → 写索引 → 组装报告(前须过时终核 3.4) → 质检八件套 → 上传/更新笔记(4.4.3 按终核结论同步)。

报告为**纯事实陈述、零立场**，正文按 GB/T 7714-2015 顺序编码制在引用处标注 [n]。

> 本文件即项目唯一权威流程标准（`docs/SOP.md` 已删除，流程不再另立文档）。
> 工具用法见 `docs/TOOLS.md`，环境约定见 `docs/CONVENTIONS.md`，文风见 `docs/STYLE_GUIDE.md`。
> 自动化分工：初始化、检索登记、通道门禁、质检由脚本强制（见各阶段「脚本」行）；人工环节仅检索执行、交叉验证与写作。
> 执行纪律：阶段串行、P0 优先；每阶段输出不达标即回退该阶段开头重做（就近回退，不跨多阶段重启）；每一步的判定标准见本文件，不得跳过任何标「必做」的步骤。

## 触发判定（零容忍 · 最高优先级）

**任何以研究问题形态出现的内容，一律触发本 SOP，禁止直接作答。**

判定标准（满足任一即视为研究请求，必须走阶段 0→4）：
- 概念性 / 解释性 / 对比性问题：「是什么、为什么、怎么理解、区别、几何意义、本质、原理、讲清楚、研究、分析、整理」；
- 给出主题 / 现象 / 方法 / 定理 / 公式要求澄清；
- 哪怕只是一句短问（如「伴随矩阵的几何意义是什么？」），也**不得直接给概念性答复**——必须机械执行阶段 0→4。

**违规即执行错误**：直接输出概念性答案（无论质量高低）等同「未按 skill 执行」，按用户裁定「任何回答都是无用」，须丢弃并改走 SOP。唯一例外：用户显式豁免（「直接回答 / 不用 SOP / 只要简短说明」等明确指令）。

收到问题后第一动作：读本文件 → 从阶段 0 步骤 1 起逐条执行；**不得先抛出任何形式的结论性答复**。

## 何时使用

- 知乎问题深度研究
- 事实核查、数据汇编
- 口径澄清、多维对比

## 工作目录

```
research/<slug>/
├── plan.md              # 问题界定
├── report.md            # 成品报告
├── report_draft.md      # 组装骨架(中间产物)
├── process_notes.md     # 检索踩坑
├── .progress.json       # 进度
└── notes/               # 模块化笔记(扁平)
    ├── _TEMPLATE.md
    ├── 00_xxx.md
    ├── 01_xxx.md
    └── ...
```

## 通用约定

- **优先级档位**：P0=必做且最先（缺失须补足或记录原因）、P1=应做（无命中记"无有效素材"）、P2=可选（记 skip）。
- **领域分三档**：学术科研 / 科技产业 / 财经时政——`channel_state.classify_domain(domain)` 自动判定、`channel_plan(domain_type)` 输出优先级计划，`research_start.py` 初始化时打印领域档位+通道计划。
- **适用通道全部执行完毕**方可进入下一阶段（P0 缺失须补足、P1 无命中记"无有效素材"、P2 记 skip）；未完成前不得产出 report.md。

## 笔记格式与硬规则

所有笔记统一放 `notes/` 一个目录, 不分子目录。

```
#维度1 #维度2 #主题/xxx

笔记标题

笔记内容(用自己的话, 不照搬原文)

参考文献:
[1] 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
```

**硬规则:**
1. 首行必须是 3 个 tag: `#维度1 #维度2 #主题/xxx`
2. 参考文献段段名为「参考文献:」（不再用「来源:」），条目须按 GB/T 7714-2015 著录；且参考文献每条 [n] 须在正文以 [n] 引用、正文每个 [n] 引用须有对应条目——编号一一对应，不能少不能多（由 `quality_check.py` 笔记模式 `check_citation_correspondence` 与 `check_gbt_refs.py` 笔记模式在 flomo 上传前拦截）
3. 标记纪律：笔记内禁止 `#`/`*` 标题标记——`##`/`###`/`####` 等 markdown 标题行一律禁止，标题用纯文本；仅首行 tag 行允许 `#`（如 `#技术 #AI`），body 内不得出现 `#` 标题行；`*` 强调亦禁止。由 `quality_check.py` 笔记模式 `check_title_asterisk` 与 `check_title_hash` 在 flomo 上传前拦截（命中即阻断上传）
4. 索引笔记(00_index.md)和报告(report.md)禁止上传 flomo
5. 笔记上传前必须跑质检: `python tools/quality_check.py --file notes/xx.md`, 通过后再上传
6. **单篇独立可读**:
   - 每篇笔记自含出处：正文首次提到来源材料（论文/文章）时写全题名与出处（如"arXiv:2608.11313《…》（YYYY-MM-DD，作者）"），不得只写"本文/该文/前作"
   - 不依赖其他笔记：禁止"见笔记 02""如前文所述"等跨笔记指代；每条笔记是完整自足的单元
   - 不依赖来源材料内部编号：论文公式号/章节号/文献号（如"(4.50)""[31]""附录 C"）单独拿出无意义，一律改描述性表述（"论文附录中的单圈检验""其前期工作（JHEP 2025(10): 204）"）
   - 指代明确："本文/本篇/前作"在本篇笔记内必须有先行词或直接写全称
   - 公式书写：笔记允许 Unicode 手写公式（笔记用 Unicode、报告用 LaTeX）
   - **参考文献区禁止 LaTeX**：报告与笔记的参考文献/来源段一律不用 $...$——GB/T 7714 著录是纯文本格式，数学符号用 Unicode/文字（如 λ₁、10⁶）；正文 LaTeX 规则不变（正文仍用 $...$，仅参考文献区例外）

## 执行纪律（硬约束）

执行本流程时禁止以下越界，违者属执行错误：

1. **不重判下一步**：各阶段步骤是固定顺序，每步"做什么"已写死。到达任一节点直接照步骤执行，不得停下重新判断"现在该干什么 / 下一步是什么"。
2. **不做流程未规定的动作**：包括但不限于逐个读工具脚本、`--help` 探签名、列目录、`ls tools/`、建工具清单/索引、各类额外澄清或自作主张的代码改动。凡步骤未列出者，一律视为多余动作，禁止。
3. **"按流程做"= 机械照步骤执行**，不是把流程当待解问题去拆解、补充或优化。用户说"按 SOP / 别想 / 以最新指令为准"时，立刻停止一切 deliberation 与 extras，只执行给定步骤。
4. **最新指令优先**：用户若纠正或推翻早前的某次选择（含选项菜单选定项），以最新、最具体的指令为准，不得沿用已被推翻的旧选项。
5. **禁止先答后走流程**：收到研究问题后，任何「先给一个简短答案 / 先说结论」的动作都属违规；必须先把流程跑到阶段 4 产出 report.md，再由 4.5 验收。直接概念性答复一律视为无效、须丢弃重做（见上方「触发判定」）。
6. **J-Space 认知管理集成**：研究流程集成 J-Space 认知工作空间框架，用于状态跟踪、思维过程管理和接缝审计。在阶段转换时执行 `jspace.py seam` 审计，在研究开始时初始化 ledger，在交付前执行 `jspace.py ship` 检查。

## 核心流程

### 阶段 0 · 问题接收与范围界定

**产出**：`research/<slug>/plan.md` 问题界定完成。

1. 接收问题。知乎链接先 `web_fetch` 抓取；失败（403/登录墙）则请用户粘贴标题或描述。
2. **J-Space introspection sweep**：在回答前执行 `modules/introspection.md` 的 PRE-ANSWER SWEEP，检查是否已形成答案，防止直接作答。识别两个已形成的判断或疑问（如"这是概念性问题"、"需要机制解释"）。
3. 拆解问题：主概念、关键实体、隐含前提、真实诉求；评估阅读价值（增量信息/反常识点）。
4. 搜 flomo 查重：`python tools/flomo_search.py --keywords "主题词"`（判读与命中处理见阶段 1 通道 F）。
5. 搜本地 RAG：`python tools/rag_search.py "<主概念>"`（SQLite 索引，改动 docs 后先 `rag_build.py`）。
6. 判定查询类型：深度优先（五视角逐项）/ 广度优先（多子议题各按五视角）/ 直接查询（一轮即可）。
7. 关键词≥6 组（不足提示，不阻塞）。
8. 初始化（脚本）：`python tools/run_pipeline.py --config tools/start.json`（或 `research_start.py`）——自动完成：目录初始化（plan/report/process_notes/notes/ + `.progress.json`，含领域档位与通道计划、E/C 环境级 skip 预登记）→ F 通道 flomo 查重（第一步阻断门禁）→ 公众号 A 通道初检落盘 → 打印 agent 待办清单。
9. J-Space 初始化：在研究目录执行 `python "C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py" note --goal "研究问题：<问题摘要>" --next "执行阶段 1 六通道检索"` 初始化认知工作空间 ledger。

### 阶段 1 · 信息检索（六通道 F/E/A/B/C/P）

**执行顺序**：**F → E → A → B → C → P**，六通道全部执行并登记后过 **阶段 1 门禁**。

**领域优先级矩阵（F/B 为通用 P0）**：

| 通道 | 学术科研 | 科技产业 | 财经时政 | 登记方式 |
|---|---|---|---|---|
| F flomo 查重 | P0（最先·阻断） | P0 | P0 | 人工判读结论后 mark_channel 登记 |
| B Web | P0 | P0 | P0 | `web_search.py --out gathered_web.md` 落盘自动登记 |
| P 预印本聚合（arxiv/bioRxiv/浪淘沙/PSSXiv） | P0 | P2 | P2 | `preprint_search.py --platform all` 落盘自动登记 |
| C 领域连接器（企查查/通达信/智慧芽） | P1 | P0 | P0 | 未配置：环境级自动 skip；已配置手动登记 |
| A 公众号 | P2 | P1 | P0 | `wechat_search.py --output gathered_wechat.md` 落盘自动登记 |
| E ima | P1 | P1 | P1 | 未配置：环境级自动 skip；已配置手动登记 |

**检索通道（按主题领域分档，替代一刀切 P0）：**
- **内部搜索优先层**（阶段 0 步骤 4-5 + search_all.py 内置）：flomo_search + rag_search 必须在外部检索前执行。内部命中 ≥5 条 → 外部检索可聚焦补充视角（减少公众号 A 通道）；内部命中 ≥2 条 → 外部正常执行；内部命中 <2 条 → 外部全量执行。search_all.py 已内置此逻辑。
- **统一入口**：启动后跑 `python tools/search_all.py --config tools/start.json`——先执行内部搜索优先层（flomo+rag），再并行执行 B/A/P 三通道（B 多查询并行），各自落盘自动登记；F 判读登记仍人工。
- **F (flomo 查重, P0 通用)**：`memo_search` 查是否已有本主题笔记（中英双查纪律见下）。
- **B (Web, P0 通用)**：`web_search` / `tools/web_search.py`。
- **P (arxiv)**：`tools/arxiv_search.py`（落盘 gathered_arxiv.md 登记通道 P）。
- **P (预印本聚合, 含 arxiv, 学术科研 P0 / 科技产业·财经时政 P2)**：`tools/preprint_search.py --platform all --keywords "<主题词>" --days 30 --count 5 --out research/<slug> --slug <slug>`——arxiv→gathered_arxiv.md + bioRxiv（生物医学）/ 浪淘沙（中文跨学科）/ PSSXiv（哲学社会科学）→gathered_preprints.md；两文件同属通道 P，一次性登记。学术/数学/AI 主题另需：主论文 **HTML 全文直抓**（`arxiv.org/html/<id>v1` → 落盘 `arxiv_html.md` + 文本化 `arxiv_text.md`）+ 相关预印本元数据核验（`id_list=` API）。平台命中与主题无关时在素材文件内注明判读结论，不计入。
- **C (领域, 科技产业/财经时政 P0 / 学术科研 P1)**：通达信/企查查/智慧芽。
- **A (公众号, 财经时政 P0 / 科技产业 P1 / 学术科研 P2)**：`tools/wechat_search.py`。
- **E (ima, P1, 未配置时初始化自动登记 skip，无需逐篇检查)**：`search_knowledge` 逐库检索。

**领域分档**：学术科研类（数学/物理/生物医学/哲学社科/AI 理论）→ P 为 P0；科技产业类（AI 应用/半导体/机器人/3D 生成）→ C 为 P0、P 为 P2；财经时政类（股票/宏观/政策/民生）→ A/C 为 P0、P 为 P2。执行纪律：仍须登记全部六通道执行态（P0 缺失须补足、P1 无命中记"无有效素材"、P2 记 skip）；**环境级未配置连接器的通道（ima E / 领域连接器 C 默认未配置）由初始化自动登记 skip，无需逐篇手动检查**（连接器接入后设 `ZHIHU_ASK_UNCONFIGURED_CHANNELS` 调整）。

#### 1.1 F flomo 查重（第一步，阻断；命中复用分支见 1.1.3）

- **1.1.1 执行查重（必做，最先执行；中英双查纪律）**：`python tools/flomo_search.py --keywords "<主题词>" --limit 10`（或 WorkBuddy `memo_search`）——**必须双轮**：① 中文主题词；② **英文标题核心词/编号**（arXiv/英文论文主题用论文标题核心词与编号如 `2608.xxxxx`；公众号文章用标题关键词）——单一语言关键词会漏掉 flomo 内另一种语言标题的已有笔记（2608.13559 漏检复盘，2026-08-16）。两轮合并判读，命中登记到 1.1.2。
- **1.1.2 判读 relevance**：
  - **≥0.9（本主题已有笔记）** → 进入 1.1.3「复用 + 过时检查」；
  - **0.5–0.9（主题相近）** → 命中笔记可作参考素材（须有符合 GB/T 7714-2015 的参考文献，`check_flomo_note_refs.py` 检测；不合规/没有 → 联网找对应来源 → 找不到则不可用），正常检索；**引用其内容前须核对时效**（过时内容不引用）；
  - **<0.5（含命中但判定不相关的假阳性）** → 无本主题笔记，正常检索（新建）。
- **1.1.3 已有笔记复用（必做，不得跳过；过时终核在 3.4、更新动作在 4.4.3，本阶段不做任何标记）**：
  - ① **拉取全文**：`python tools/flomo_search.py --keywords "<主题词>" --limit 50 --full`（或 `memo_batch_get`）拉取命中笔记全文；
  - ② **忠实还原**：本地 `notes/` 缺失或疑似旧版本时，按拉回全文**忠实还原本地笔记文件**（仅解除平台转义，不重写内容、不新建主题），flomo 端不动；**权威源为 flomo**——本地文件与 flomo 原文内容等价即视为还原成功，还原本身不构成更新；本地文件若比 flomo 新（本地刚改写且未上传），保留本地版本并在 plan.md 注明。
  - ③ **初步观察（仅记录提示，不作为待办标记）**：来源论文/文章是否有新版本（arXiv API 查 `updated` 字段与版本列表）、是否已知有新信息，随 1.1.4 写入 F 通道 note，供 4.4.3 终核参考。
- **1.1.4 记录与登记**：判读结论（命中情况 / 复用决定 / 初步观察提示）写入 `research/<slug>/plan.md` 步骤 0 行；`python tools/mark_channel.py --slug <slug> --channel F --status done --note "memo_search 已执行：<命中概述>；判读：<复用/参考/正常检索>；过时终核在 3.4、更新同步在 4.4.3"`。

**flomo 笔记引用规则**：命中的笔记若用作素材，必须有符合 GB/T 7714-2015 的参考文献；不合规或没有 → 联网找对应来源；找不到 → 该笔记不可用。检测：`python tools/check_flomo_note_refs.py --keywords "<主题词>"`。

**旧笔记过时更新（命中时必做）**：新信息推翻旧笔记表述时，旧笔记过时句必须原地更新（如"尚无定论""待观察""未发布"被证实/证伪后补结局或改写），不得只新增而让新旧自相矛盾。时机：过时终核在阶段 3 末（3.4，写报告前，结论写 process_notes）；更新动作在阶段 4（4.4.3：本地改写后 `note_upload.py <文件>.md --update` 按 .flomo_ids.json memo_update 覆盖原 id，禁止新建多版本）。更新后的旧笔记与新增笔记一并质检上传。

#### 1.2 E ima 检索（P1）
连接器未配置 → 环境级自动 skip（无需逐篇检查）；已配置 → `search_knowledge` 逐库检索（候选库取全、每库 ≥2 个关键词），全部无命中记"通道 E 无有效素材"。

#### 1.3 A 公众号（优先级按领域：财经时政 P0 / 科技产业 P1 / 学术科研 P2）
`python tools/wechat_search.py --keywords tools/keywords_a.json --days 30 --output research/<slug>/gathered_wechat.md`；零结果 → 换词重试 1 次 → 仍无 → `mark_channel --status empty` 登记（落盘文件或 note 含"无命中/无结果"字样）。

#### 1.4 B Web（P0 通用）
`python tools/web_search.py --queries-file tools/queries_b.json --parallel N --out research/<slug>/gathered_web.md`（或 `search_all.py` 统一入口并行）；命中逐条判读，噪音不计入素材；落盘自动登记。

#### 1.5 C 领域连接器（企查查/通达信/智慧芽；科技产业/财经时政 P0、学术科研 P1）
连接器未配置 → 环境级自动 skip；已配置 → 按领域必做（专利+论文各一次调用等），无命中记"通道 C [数据源]无有效素材"。

#### 1.6 P 学术预印本聚合（学术科研 P0 / 科技产业·财经时政 P2）
`python tools/preprint_search.py --platform all --keywords "<主题词>" --days 30 --count 5 --out research/<slug> --slug <slug>`——arxiv → `gathered_arxiv.md`，bioRxiv/浪淘沙/PSSXiv → `gathered_preprints.md`（两文件同属通道 P）。学术/数学/AI 主题另需：主论文 HTML 全文直抓（`arxiv.org/html/<id>v1` → 落盘 `arxiv_html.md` + 文本化 `arxiv_text.md`）+ 相关预印本元数据核验。

#### 1.7 门禁（进入阶段 2 前必过）
`python tools/check_progress.py --slug <slug> --require report_channels`——「声明态 ⊕ 证据」双向交叉校验（声明缺失 / 证据缺失 / 有素材未登记 / 无 note 均阻塞）。有效通道 <2 须补充检索，仍不足告知用户降级。

**J-Space 接缝审计**：阶段 1 完成后执行 `python "C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py" seam` 记录阶段完成状态，更新 ledger 的 Verified 和 Next 字段。**额外审计点**：每个通道完成后执行 `seam` 审计，记录通道完成状态，防止状态漂移。

**落报告纪律**：通道"执行过"≠"交付完成"——每个适用通道的硬数据（事实/数字/实体/结论）必须写入 report.md 正文相应小节。

**笔记写入规则：**
- 每条笔记 3 个 tag：`#维度1 #维度2 #主题/slug`；来源必须 GB/T 7714-2015 格式；每个通道命中写一条笔记。
- `notes/` 下至少 2 个不同通道的笔记才进入阶段 2。

### 阶段 2 · 多视角信息收集

**前置校验**：进入阶段2前，必须通过阶段1完成校验：
```bash
python tools/run_pipeline.py --slug <slug> --check-phase phase1
```

1. **J-Space capacity check**：在开始多视角收集前，执行 `modules/capacity.md` 的 drill：命名当前舞台上的1-2个核心想法。如果超过2个，将多余想法写入 ledger 的 Open 字段。
2. 五视角逐项覆盖 (A公众号/B Web/C领域/D争议/E反方)；每视角至少一轮检索。
3. 搜 flomo 补充同类笔记：`python tools/flomo_search.py --tag "主题/slug"`。
4. 补充新笔记到 `notes/`。
5. 校验：子问题与视角清单逐一对照，有子问题未被任一视角覆盖即为缺陷（P0 补检索）；补后仍无 → 结论标注"该子问题无公开素材"。直接查询跳过本阶段。
6. 撰写模块化笔记（必做）：检索完成后撰写 `notes/*.md`（扁平目录、首行标签 `#维度1 #维度2 #主题/slug`；每篇含标签行 + 标题 + 正文 + 参考文献 GB/T 7714-2015）；写 `notes/00_index.md` 索引（`#索引`，以 `## 问题/历史/证明/结论/缺口` 串联各笔记）。阶段 1 判读为复用时，复用笔记已还原进本目录（不重写），与新建笔记一并构成笔记集。
7. **J-Space 接缝审计**：阶段 2 完成后执行 `python "C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py" seam` 记录笔记完成状态，更新 ledger。

### 阶段 3 · 交叉验证与量化

- **J-Space deep-reasoning check**：在开始交叉验证前，执行 `modules/deep-reasoning.md` 的检查：确保每个中间步骤在结论之前到达。如果结论先于步骤出现，使用"桥接概念"方法重新组织论证。
- 多源冲突取舍：最新 + 一手优先 + 口径一致。
- 数字口径：关键数字标注数据级别（一手/二手/推断）；媒体转述数字尽量回溯一手，无法取得标"仅媒体口径"。
- 论证完整：数学/证明/机制类给完整论证链（定理-引理-证明或步骤归约），来源论文论证以全文（arXiv HTML 版）为准；禁止只给方法名概述。
- 算式按需但必写：有计算价值的内容算式必须写、融入叙述，禁止凑数硬造也禁止该写不写；有计算价值的算式须经 Python 验证。
- 数据不可得 → 标注"待核实"。
- 决策点（用户审批）：关键数字缺失导致结论悬空且无法推断时，暂停询问用户。
- **3.4 复用笔记最终过时核对（仅当阶段 1 判读为复用已有笔记时必做；在材料收集齐备后、4.1 撰写报告前执行）**：
  - **web_fetch 验证（必做）**：每条复用笔记的关键事实声明，须 `web_fetch` 对应原始来源 URL 验证（实体名、数字、日期）。**禁止仅凭 flomo 笔记内容写入报告**——flomo 是内部摘要，可能含二手/三手来源，必须回溯一手来源。
  - 对照阶段 1–3 收集的全部材料，对每条复用笔记逐条复核（来源论文/文章是否有新版本、是否有新结果推翻笔记表述如"尚无定论/待观察/未发布"被证实/证伪）。
  - **确有过时 → 立即在本地笔记文件中改写**（补结局/改写过时句子，不新建多版本），使 4.1 报告引用的一律是已校正内容。
  - **终核结论（逐条：过时/未过时 + 依据 + 改写记录 + web_fetch 验证 URL）写入 `process_notes.md` 留痕**，作为 4.4.3 同步动作的依据。
  - 写报告若引用还原笔记内容，必须先经本步终核。
- **J-Space 接缝审计**：阶段 3 完成后执行 `python "C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py" seam` 记录验证完成状态，更新 ledger。

### 阶段 4 · 报告生成、自检与沉淀

**阶段校验（强制）**：进入阶段4前，必须通过以下校验：
- 阶段2：`notes/`目录至少有2篇结构化笔记（不含`_TEMPLATE.md`和`00_index.md`）
- 阶段3：阶段键为`phase3_done`或更后
- 阶段4沉淀：`process_notes.md`存在且>100字节

```bash
python tools/check_progress.py --slug <slug> --require phase2_done
python tools/check_progress.py --slug <slug> --require phase3_done
python tools/check_progress.py --slug <slug> --require phase4沉淀_done
```
完成各阶段后用`--mark`更新状态：`--mark phase2_done` / `--mark phase3_done` / `--mark phase4沉淀_done`。

#### 4.1 撰写 report.md
按 `templates/research_report_TEMPLATE.md` 产出：结论（≤300 字）→ 关键事实与数据（事实叙述+分析表格）→ 参考文献；公式一律 LaTeX，正文 [n] 引注，参考文献区禁 LaTeX。报告内容以阶段 1–3 收集材料为准；复用笔记的内容若被引用，须已经 3.4 终核。

#### 4.2 脚本收尾（八件套门禁）
`python tools/run_pipeline.py --slug <slug>` 一键执行——自动清理工作区 → 质检八件套门禁（见下 8 道，硬伤与提示级均阻断）→ `report_to_docx.py` → `report_to_flomo.py`（本地存档）→ `check_all.py` 全库体检。

**八件套明细**：
1. `check_report_structure` — 结构校验
2. `quality_check` — 综合质检（标题标记、引用对应等）
3. `check_ai_voice` — AI 腔/立场检测
4. `check_gbt_refs` — GB/T 7714 参考文献著录
5. `check_citation_validity` — 违规引用（学术纪律）
6. `check_consistency` — 矛盾与废话
7. `check_progress --require_round auto` — 轮次门禁
8. `check_progress --require report_channels` — 落报告门禁

**人工确认放行**：违规引用检查的「正文与题名疑似不符」为启发式提示，词面差异机器无法判定时，由主代理逐条判读——真引用则 `--ack <n1,n2,...>` 放行（判读理由逐条说明并留痕，见 `docs/CONVENTIONS.md` §8）；真张冠李戴则修正正文。

**J-Space 交付前检查**：在八件套门禁通过后、生成 docx 前，执行 `python "C:\Users\35234\.workbuddy\skills\J-Space-Cognition-Suite\scripts\jspace.py" ship report.md` 注册交付检查，确保报告符合认知管理标准。**额外检查**：执行 `modules/self-monitoring.md` 的检查：是否所有自信标签都一致？是否在表演角色？是否使用了自己不会选择的词语？

#### 4.3 配图（按需）
`tools/report_images.py --slug <slug>`——AI 概念图仅作封面 `ai_cover.png`（纯抽象、紧扣主题、构图饱满，合规复检见 `docs/CONVENTIONS.md` §8 与 `templates/research_report_TEMPLATE.md` 配图条）；数据图表按内容锚点插入正文、带图注；AI 概念图禁止进正文（quality_check 硬性拦截）。

#### 4.4 沉淀（必做）
- **4.4.1 关键词回填**：有效关键词写 SQLite 关键词库（`keywords_db.py --add`）+ `--export docs/KEYWORDS.md` 同步。
- **4.4.2 经验记录**：写 `research/<slug>/process_notes.md`（检索与踩坑记录，含 3.4 终核结论）。
- **4.4.3 笔记上传/同步（按 .flomo_ids.json 记录分流；复用笔记的过时结论以 3.4 终核为准）**：
  - **新建笔记（`.flomo_ids.json` 无记录的文件）**：逐条上传 `python tools/note_upload.py research/<slug>/notes/<文件名>.md`（无记录 → memo_create 并补记 id）。**禁止**对含已记录文件的目录跑无 `--update` 的整目录上传（工具对已记录文件也会 memo_create，造成重复笔记）；
  - **复用笔记（`.flomo_ids.json` 有记录的文件）**：按 3.4 终核结论执行——**判为过时（3.4 已改写本地文件）** → `python tools/note_upload.py research/<slug>/notes/<文件名>.md --update` 按记录用 `memo_update` 覆盖原 id（禁止新建多版本），同步 3.4 的改写结果；**终核未过时** → 不动（不执行任何上传/更新命令）。终核结论与改写记录已在 3.4 写入 `process_notes.md` 留痕。

#### 4.5 用户验收（决策点）
交付前用户验收；被拒（AI 味/质量）则按 STYLE_GUIDE 重写后重新提交（重写后须重跑 4.2 门禁）。用户 24h 未验收 → 再次提醒，交付物保留待查看。

#### 4.6 验收通过后收尾（必做）
- **4.6.1 索引回填（验收通过后）**：`python tools/run_pipeline.py --slug <slug> --backfill` 将 `plan.md` 状态回填"已完成"（收尾门禁 4.2 **不再自动回填**，避免验收前状态错误标记；`--backfill` 幂等，行缺失/已回填时无改动）。
- **4.6.2 推送**：公共文件有改动时提交推送（git commit + push）。

#### 4.7 多轮迭代研究
默认 1 轮成稿；仅当存在"仍无法核实"内容、数据口径缺口或质检需补检索时才追加轮次。`iter_research.py` 生成问题清单模板，历史轮次归档 `round_notes_r<N>.md`；直接在 report.md 更新，不建版本文件。问题清单清空即完成；领域最低轮次默认 1，`check_progress --require_round auto` 校验。

## 异常与回退

**回退原则**：就近回退——退回上一阶段开头修正，不跨多阶段重启；满足本阶段输出标准才向下流转。

| 异常 | 处理 |
|---|---|
| 知乎 403/登录墙 | 请用户粘贴问题内容（回到阶段 0） |
| 单通道失败/零结果 | 换关键词重试 1 次，仍无则记录"通道 X 无有效素材"（P2 记 skip） |
| E/C 连接器未配置 | 环境级自动 skip，不阻塞；连接器接入后恢复手动登记 |
| arxiv 直连 429 限流 | WebFetch 降级：`arxiv_search.py --print-web-prompt` → agent 抓取存 arxiv_raw.txt → `--raw` 解析落盘 |
| 子代理不可用 | 主代理直执 |
| 关键数据缺失 | 标注"待核实"+推断区间，必要时询问用户 |
| 数据与已发布事实冲突 | 更正并记录，阶段 3 重验 |
| 检索耗时超限 | 缩小范围、聚焦关键子问题 |

**异常分级**：阻断级（数据全缺失/信源全失败/权限问题）→ 立即暂停告知用户；非阻断级（单通道失败/子问题无素材/报告需重写）→ 降级继续并在交付物注明。

## 时限

单次研究建议 1 个工作日内完成：阶段 0: 0.5h / 1: 1–2h / 2: 1–2h（可与 1 合并）/ 3: 2–3h / 4: 3–5h（含 4.2 门禁与 4.5 验收）。超 2 个工作日未完成须向用户说明原因。

## 质量红线

- 所有可量化数据必须有来源；无法核实的标注「未证实」；不编造引用、不虚构数字、不替用户做决定（给权衡，不给单一路径）。
- 引用公众号文章须保留标题与作者信息。
- 报告为**纯事实陈述**：不设结论、不表立场、不贴标签、不给建议、不替读者判断；立场中立为硬性检查项。
- 报告禁止 A 股行情信息（股票代号/股价/涨跌幅/市值等，quality_check 拦截）；需产业背景用公司名+产业事实表述。
- 未经用户明确同意，不执行推送、强推、改仓库可见性等操作。

## flomo 搜索用法

```bash
# 按关键词搜
python tools/flomo_search.py --keywords "AI 编程"

# 按标签搜
python tools/flomo_search.py --tag "AI编程"

# 组合搜
python tools/flomo_search.py --tag "AI编程" --keywords "定价"
```

## GB/T 7714-2015 来源格式

```
网络文献: 作者. 题名[EB/OL]. (发布日期)[引用日期]. URL.
会议论文: 作者. 题名[C]//论文集名. 出版地: 出版者, 年: 页码.
期刊论文: 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
作者规则: 英文姓在前名缩写, 无作者写"佚名"
```

## 配套资源

- 工具: `tools/`
- 流程（本文件即权威标准）: `skills/zhihu-ask-research/SKILL.md`
- 工具详解: `docs/TOOLS.md`
- 环境约定: `docs/CONVENTIONS.md`
- 文风: `docs/STYLE_GUIDE.md`
- 词库: SQLite `.codebuddy/knowledge/knowledge.db`（`tools/keywords_db.py` 管理；`docs/KEYWORDS.md` 为导出物）
- 模板: `templates/`
