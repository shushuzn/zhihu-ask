# 项目内工具说明

解决开发环境中命令行中文参数乱码、外部脚本路径耦合等问题。所有工具放在 `tools/`。

## 工具清单（按职责分组）

| 分组 | 工具 |
|---|---|
| 研究生命周期 | `init_research.py` · `research_start.py` · `iter_research.py` · `run_pipeline.py` |
| 通道检索 | `wechat_search.py`（A）· `preprint_search.py`（P：arxiv/bioRxiv/浪淘沙/PSSXiv）· `flomo_search.py`（F 查重） |
| 素材引用校验 | `check_flomo_note_refs.py`（flomo 笔记须有参考文献；无→联网找→找不到不可用） |
| 数据落库 / 转换 | `report_to_docx.py` · `report_to_flomo.py` · `report_images.py` |
| 质检门禁 | `quality_check.py` · `check_report_structure.py` · `check_ai_voice.py` · `check_gbt_refs.py` · `check_citation_validity.py` · `check_progress.py` · `check_all.py` |
| 通道登记 | `mark_channel.py` · `channel_state.py`（共用核心） |
| 知识库 | `rag_build.py` · `rag_search.py` · `knowledge_store.py` · `keywords_db.py` |
| 环境与提交 | `health_check.py` · `net_check.py` · `git_protect.py` · `install_git_hooks.py` · `internal_files.py` |
| 验证（实验性） | `syllogism_check.py` |

> 连接器类通道（ima E / 企查查·通达信·智慧芽 C）由主代理直执 MCP 工具，非脚本，见下方对应小节。

## 测试套件（回归守护）

`tests/run_all.py` 逐模块子进程运行全部测试、聚合 PASS/FAIL，任一失败退出码 1；`check_all.py` 体检前自动先跑。

| 模块（项数） | 覆盖 | 模块（项数） | 覆盖 |
|---|---|---|---|
| test_quality (125) | quality_check 全部规则正/负断言 | test_research_start (27) | config 校验 / 进度合并 / ima 提示 |
| test_check_progress (14) | report_channels 双向交叉门禁 | test_install_git_hooks (10) | hook 装/卸行为 |
| test_channel_state (43) | 通道登记纯函数 + 环境级未配置 | test_run_pipeline (15) | 收尾门禁顺序 |
| test_wechat_norm (31) | 消费端防御 / 自动登记 A / 路径归一化 | test_syllogism_check (22) | 三段论纯逻辑 |
| test_arxiv_automark (5) | 落盘自动登记 P | test_report_images (19) | 锚点插入 / 图表冒烟 |
| test_arxiv_query (23) | OR 语义提示 / curl 兜底四态 | test_ai_voice (12) | 两级检出 + 负例 |
| test_report_structure (21) | 五类结构规则 | test_latex_unicode (13) | LaTeX→Unicode |
| test_report_to_flomo (26) | convert_text / pick_tags | test_note_upload (21) | 上传质检链 / 拦截 |
| test_git_protect (15) | 提交保护分流逻辑 | test_web_search (52) | 解析纯函数 + B 自动登记 |
| test_internal_files (31) | 内部文件红线单一真相源 | test_check_flomo_note_refs (29) | 笔记参考文献判定 |
| test_init_research (47) | slug / CLI / 模板替换 / 索引 / 初始进度 | test_citation_validity (34) | 违规引用核验 |
| test_check_all (25) | 体检工具纯函数 | test_consistency (28) | 项目矛盾/废话检查 |
| test_rag_build (23) | is_indexable / chunks | test_clean_workspace (8) | 清理路径收集 |
| test_rag_search (29) | tokenize / bm25 / highlight | test_env_loader (16) | .env 加载 |
| test_knowledge_store (17) | 关键词库 roundtrip | test_gbt_refs (23) | 国标著录 |
| test_health_check (26) | REQUIRED_FILES 一致性守护 | test_flomo_search (10) | token 环境变量 / F 自动登记 |
| test_report_to_docx (41) | md→docx 转换契约 | test_web_fetch (20) | 抓取降级 |
| test_iter_research (27) | 轮次推进 / 归档 | test_preprint_search (31) | 四平台聚合 |
| test_net_check (9) | 外网出口探测 | | |

**纪律**：修改任一被测工具后先跑 `python tests/run_all.py` 确认无回归再提交；运行器取子进程输出**最后一个** `TOTAL: PASS=.. FAIL=..` 为权威结果（防嵌套输出干扰）。
## init_research.py — 研究目录初始化

**作用**：一键创建新研究——生成 plan/report/process_notes（从模板填充问题/日期/领域/slug，元信息行供 report_to_flomo 解析标签）、落盘 `.progress.json`（stage/round/domain，含环境级 E/C skip 预登记）、创建 `notes/` 目录及模板、在 plan.md 索引表登记一行。

**用法**（PowerShell 中文走 --config）：
```bash
python tools/init_research.py --config tools/init.json   # config 参考 tools/init.example.json（question/domain/slug/priority）
# 或直接传参：--question "标题" --domain "领域" --slug <slug> --priority <级别>
```

**注意**：slug 须英文小写短横线；config 用完即删（gitignore 已忽略）；元信息行领域/slug 已实填勿改回占位符（否则 flomo 标签兜底错误）；走 `research_start.py` 时 .progress.json 合并更新（保留 round）。
## note_assemble.py — 模块化笔记组装工具

**作用**：从 `notes/` 目录读取索引笔记和普通笔记，自动组装成报告骨架。

**用法**：

```bash
python tools/note_assemble.py --slug <slug>            # 组装并生成 report_draft.md
python tools/note_assemble.py --slug <slug> --dry-run   # 只预览，不写文件
python tools/note_assemble.py --slug <slug> --output custom.md  # 指定输出路径
```

**流程**：
1. 读取 `research/<slug>/notes/` 下的索引笔记（tag 含 `#索引`），确定报告结构
2. 按索引引用顺序读取对应笔记
3. 组装成报告骨架（标记需要补过渡段的位置）
4. 生成参考文献列表（GB/T 7714-2015 格式，自动去重）

**输出**：`research/<slug>/report_draft.md`

## flomo_search.py — flomo 笔记搜索

**作用**：flomo MCP 搜索笔记（关键词/标签），用于阶段 0 查重、阶段 1 补充、阶段 4 写索引前盘点。

**用法**：
```bash
python tools/flomo_search.py --keywords "AI 编程"                  # 关键词搜索
python tools/flomo_search.py --tag "AI编程" --keywords "定价"       # 组合搜
python tools/flomo_search.py --keywords "定价" --full              # 拉完整正文（memo_batch_get）
python tools/flomo_search.py --keywords "主题词" --slug <slug>     # 查重后自动登记通道 F（done，note 含 memo_search 证据）
```

**要点**：
- **凭证**：Token 只从环境变量 `FLOMO_MCP_TOKEN` 读取（不读 .env，见 docs/CONVENTIONS.md）；此前硬编码进公开仓库，**须在 flomo 后台撤销旧 token 重建**。
- **F 自动登记**：带 `--slug` 即登记 done（note 含 memo_search 证据）；≥0.9 复用/更新、0.5~0.9 参考等结论由主代理阅读结果后用 `mark_channel.py` 补充/覆盖 note。
## research_start.py — 一键研究启动器

**作用**：把「启动一次知乎问题研究」压缩为一条命令，并落地 SOP 附录 A 的执行级逻辑。自动完成：配置校验（question/slug 必填、关键词下限提示）→ 初始化研究目录（阶段 0）→ 公众号检索并落盘素材库 `research/<slug>/gathered_wechat.md`（阶段 1 通道 A）→ 素材库非空校验 → 记录阶段进度 `.progress.json`（含 `domain` 字段，供 `check_progress --require_round auto` 按领域判定最低轮次）→ 打印后续步骤（阶段 2-4 上下文，其中通道 E 提示按领域从 `docs/IMA_LIBRARIES.md` 列出候选订阅库）。

**用法**：

```bash
python tools/research_start.py --config tools/start.json
```

**config 格式**（UTF-8，完整示例见 `tools/start.example.json`）：
```json
{
  "question": "问题完整标题",
  "domain": "示例领域",
  "slug": "example-slug",
  "priority": "高",
  "keywords": ["主题词 突破", "主题词 产业化"],
  "days": 30,
  "min_keywords": 6
}
```

**注意**：keywords 为公众号检索关键词组，days 为时间范围（天，默认 365），min_keywords 为关键词下限（默认 6，不足时提示但不阻塞）。脚本做「阶段 0 初始化 + 阶段 1 通道 A」，产出素材库后按 SOP 附录 A 进入阶段 2。

## iter_research.py — 多轮迭代研究

**作用**：把"单轮研究"扩展为"多轮迭代"。每完成一轮，生成下一轮问题清单模板（写 round_notes.md，历史轮次自动归档为 `round_notes_r<N>.md` 保留迭代轨迹）并更新 `.progress.json` 的 round 记录。问题清单由主代理人工编写——阅读报告中标注"仍无法核实/推算"的内容与数据口径缺口，逐条整理成明确、可执行的问题；不用自动提取（机械拆句语义不清）。**默认 1 轮成稿**：一轮后问题清单已清空（无"仍无法核实"内容、无口径缺口、质检通过）即完成；仅当一轮存在无法解决的内容时才追加轮次，直至问题清单清空。领域最低轮次见 SOP A.8（默认统一 1 轮）——工具按 `.progress.json` 的 domain 自动提示当前轮次与达标状态（未达标显示还需 N 轮）。

**用法**：

```bash
python tools/iter_research.py --slug <slug>            # 生成下一轮问题清单（当前轮+1）
python tools/iter_research.py --slug <slug> --round 2  # 指定目标轮次
```

**默认流程（1 轮成稿，不询问用户）**：
- 第 1 轮：`research_start.py` 启动 → 阶段 2/3/4 产出 report.md → 质检八件套通过 → 完成。
- 追加轮次条件（满足任一）：①报告存在"仍无法核实/推算"内容；②存在数据口径缺口；③质检拦截项需补检索才能修复。本工具生成问题清单模板 → 人工填写未尽问题 → 补检索/深化 → 直接在 report.md 上更新，直至问题清单清空。

**注意**：工具只生成问题清单与更新轮次，不替代主代理的分析写作。报告路径 research/<slug>/report.md；迭代直接在原文件更新，不创建 vN 版本文件。**禁止无谓追加轮次**（默认 1 轮即可交付）；追加轮次后若问题清单仍有未处理内容必须继续，直到问题清单处理完。报告必须是成品，正文禁止出现"第 N 轮/迭代"等过程性字样。

## run_pipeline.py — 一键研究流水线驱动

**作用**：把「阶段 0→4」中可由脚本确定的环节串起来，带 checkpoint 与质检门禁，并明确标出必须由 agent 介入的步骤（Web 检索 / ima E 通道 / 企查查·通达信·智慧芽 C 通道 / arxiv 的 WebFetch 降级流程 / flomo 上传 / AI 封面）。脚本只做确定性动作 + 质检门禁；外网检索与主观写作交 agent，由工具打印可复制命令清单。每段失败即阻断。

**用法**：
```bash
# 启动一次新研究（阶段 0-1 初始化 + 公众号 A 通道），随后打印 agent 待办清单
python tools/run_pipeline.py --config tools/start.json

# 报告写好后的收尾（自动清理工作区 + 质检门禁 + docx + flomo 格式化 + 全库体检提示）
python tools/run_pipeline.py --slug <slug>

# 一步到位：启动 + 收尾（中间需 agent 自行完成检索与写作）
python tools/run_pipeline.py --config tools/start.json --slug <slug>

# 无外网环境：违规引用检查改用离线模式（跳过 CrossRef/arXiv 联网核验）
python tools/run_pipeline.py --slug <slug> --offline
```

**说明**：`--config` 触发 `research_start.py`（会预警 `WECHAT_ARTICLE_SEARCH_SCRIPTS` 未设置；config 含 slug 时 F 查重自动登记通道 F）；`--slug` 触发 **clean_workspace → 质检八件套 → report_to_docx → report_to_flomo**（仅格式化，未上传）→ 门禁全过后**自动回填 plan.md 索引"已完成"** → 打印 agent 待办（笔记上传 / AI 封面 / 发布前 `check_all.py`）。`--offline` 让违规引用门禁以 `check_citation_validity.py --offline` 运行，适合当前无外网环境；联网核验仍建议在外网环境补跑。收尾前的 Web/ima/C/arxiv 检索与 report.md 写作由 agent 完成。

## quality_check.py — 正文质量自动检查

**作用**：把报告模板/CHECKLIST 中的「去 AI 味 + 立场中立」检查落地为自动扫描。检测立场词（我认为/应该/总之等；"证明"按组合词匹配——"足以证明/这证明"算立场，"收入/纳税/实验证明"为名词/事实用法不误报）、框架词（先说结论/总结一下等）、评价词（太猛/离谱等）、感叹号/反问句、无来源数字（启发式）、模板占位符残留（`{{...}}`）、**过程性字样**（成品报告禁止"R1-R9/第 N 轮/本轮/上一轮/**通道 X**（检索通道标记）"等迭代/流程过程标记；URL 字母段与技术名词"迭代/更新"与"电离通道"等技术含义不误报）、**标题含括号**（标题不带来源/口径说明）、**提示性套话**（"判断权留给读者/留给你"等元话语提示词；结论用事实映射句式）、**AI 腔句式**（"不是…是/而是…"转折、之所以…是因为、随着…发展、在此背景下、在 XX 时代、可以看出）、**分级词括注**（正文禁止"（一手/二手/推算）"等数据强度括注；"日本二手设备"物理含义与"单一手段"相邻字不误报）、**证据分级词**（正文禁止"证据较强/证据中等/证据强度"）、**交叉引用校验**（检测旧式“见 2.x 节”编号引用；无编号小节的标题引用由人工核对）、**内部标识检测**（成品报告禁止"flomo 笔记/内部笔记/信号笔记/gathered_"等内部工具与流程标识，及六通道检索过程痕迹词"智慧芽/企查查/通达信/产业无对应/无适用主体/无约定主题布局"——C 通道无命中是内部研究记录，只落 process_notes 不写正文；"公众号/媒体/新闻"等正文来源词不误报）、**A 股行情信息**（正文禁止股票代号如 603986、股价/现价/涨跌幅/总市值/PE(TTM) 等行情字段，check_stock_info 拦截；"兑现价值"等正常词语不误报）、**事实规模**（小节内 bullet 单行报"小点未叙述化"——小点须写成连贯叙述段，表格是唯一允许的列表形式；小节数量不设上限）、**段落长度**（叙述段 >5 行报"段落过长"）、**AI 概念图禁令**（check_cover_ban：ai_*.png 禁止插入正文，封面仅作独立文件 ai_cover.png）、参考文献标注（参考文献区链接行不得带分级标注）、**参考文献区禁止 LaTeX**（GB/T 7714 著录为纯文本格式，$...$ 会破坏著录结构且 docx 转换器不做 OMML 转换；数学符号在参考文献区用 Unicode/文字，如 λ₁、10⁶；报告与笔记均适用）、结构完整性（必须有 `## 参考文献` 章节含 [标题](url) 链接或纯文本标题条目、正文无"待补充/TODO"等未决标记）。测算/研究问题/多维分析已融入小节（无独立章节、无"**测算 N**"块），相关旧检查（测算过简/测算不足/逻辑链四要素）已随结构演进移除。

**用法**：

```bash
python tools/quality_check.py --file research/<slug>/report.md
python tools/quality_check.py --slug <slug>            # 等价写法（自动指向 research/<slug>/report.md）
python tools/quality_check.py --slug <slug> --verbose
```

**输出**：全部通过退出码 0；检出待确认项退出码 1 并列出位置与命中词。检出项为启发式规则，需人工确认是否真正违规（如"不构成投资建议"中的"建议"为合法用法）。来源特征词含来源/口径/媒体/测算/预算等，带来源括注的列表行与表格行不误报。

**回归测试（必跑）**：`tests/test_quality.py` 对以上每条规则做正向（必命中）/负向（必不命中）断言（当前 125 项）。新增或修改任何规则后，先跑 `python tests/run_all.py` 确认无回归，再提交——规则静默回退会连累每一篇报告。该自测已接入 `check_all.py`（经 `tests/run_all.py`），逐篇体检前自动执行；自测未过则中止逐篇体检。

**注意**：扫描范围为正文（自动跳过"数据与来源备查"及之后的来源区）；表格行数字不判为无来源。数字溯源与逻辑终审仍需人工复核。

## check_ai_voice.py — 去 AI 腔自动检查

**作用**：把用户「中文写作去 AI 腔」规则固化为机器检查，与 quality_check.py 互补（该工具已覆盖的立场/框架/评价词与 AI 因果句式不在此重复）。两级检出：
- **[硬伤]**（命中即退出码 1）：空转过渡（需要强调的是/众所周知/说到底/归根结底/划重点等）、开头预告（话说到前头/话说在前头/说在前头/话说回来）、「一句话」类（一句话/就一句话/一句话讲清等）、对词动手术（把 X 这个词拆开/拆解 X 概念等）、标题禁词（先/必须/清楚/反直觉）、自问后垫宣告（为什么…？背后是/原因有三）、「先说/先给/先看」宣告。
- **[提示]**（默认同样阻断）：装饰词（非常/核心/至关重要等）、转折词（但/然而/其实）、对称排比（不仅…而且/既…又/一方面…另一方面）、「不是 X，是 Y」立靶子句式、破折号长插入语与同行扎堆、引号包裹日常词。

**用法**：

```bash
python tools/check_ai_voice.py --file research/<slug>/report.md
python tools/check_ai_voice.py --slug <slug>            # 等价写法；默认严格阻断，提示级命中同样失败
python tools/check_ai_voice.py --slug <slug> --verbose
```

**接入**：`run_pipeline.py finish()` 收尾门禁（在 quality_check 之后，硬伤与提示级均阻断）；`check_all.py` 全库体检新增「AI腔」列（硬伤与提示级均判 X）。**回归测试**：`tests/test_run_pipeline.py` 断言收尾门禁顺序含本工具；`tests/test_health_check.py` 断言已登记 REQUIRED_FILES。检出项为启发式，默认同样阻断；如「但」多为真实转折、「关键」可能是合法术语语境、引号若为非字面义/术语首现属合规，需修正或说明。

## check_gbt_refs.py — 参考文献国标（GB/T 7714-2015）合规检查

**作用**：把用户「引用参照国标」要求固化为机器检查，检测 markdown 报告中「参考文献」块的著录是否合规。两级检出：
- **[硬伤]**（命中即退出码 1）：
  1. **无参考文献块**：未找到「参考文献」标题（支持 `## 参考文献` / `**参考文献（GB/T 7714-2015）**` / `参考文献`）
  2. **缺文献类型标识**：每条须含 [M]/[J]/[C]/[D]/[R]/[S]/[Z] 或电子版 [M/OL]/[EB/OL] 等（GB/T 7714-2015 附录）
  3. **编号不连续**：文献条目 [n] 须从 1 连续递增、无跳号重复
  4. **电子资源缺引用日期**：含 http(s):// 的条目须带 [YYYY-MM-DD]
  5. **引注对应**：正文 [n] 须都能在文献列表找到（无悬空）、文献编号须全部被正文引用（无未被引用）、正文引注编号连续
- **[提示]**（默认同样阻断）：转引条目（含「见:」）未标注中间文献名；参考文献标题未标注「GB/T 7714」或「国标」

**用法**：

```bash
python tools/check_gbt_refs.py --file research/shanhaijing/02_流沙考.md
python tools/check_gbt_refs.py --slug <slug>            # 检查 research/<slug>/report.md；默认严格阻断，提示级命中同样失败
python tools/check_gbt_refs.py --file x.md --verbose
```

**适用场景**：任何带参考文献块的 md（研究 report.md、创作稿如山海经活动内容）。**回归测试**：`tests/test_gbt_refs.py`（14 条正/负/strict 用例）；已登记 REQUIRED_FILES。注意：正文 [n] 识别按顺序编码制假设，[20xx-xx-xx] 引用日期不会误判为引注。

## check_consistency.py — 矛盾与废话检查

**作用**：检测报告正文的自相矛盾与无信息量表述。两级检出：
- **[硬伤]**（命中即退出码 1）：
  1. **同指标数值冲突**：同一"数字+强单位"（万亿/亿/吉瓦/千瓦时/倍/%/帧等）在报告中出现不同数值——如"5万亿元"与"4万亿元"同时出现且未标注口径；豁免：同行并列且带口径词（"4万亿（国网口径）/5万亿（全国口径）"）、数值差异 <10%（近似表述）
  2. **方向性矛盾**：同一行内同一主体同时出现"上升类"与"下降类"动词（如"负荷上升但负荷下降"）；跨行时间演变（"上半年上升、下半年下降"）不误报
- **[提示]**（默认同样阻断）：无信息量套话（具有重要意义/影响深远/值得关注等且句内无数据）、冗余元话语（需要说明的是/需要注意的是等）、空泛结论句（"由此可见，。"类）

**用法**：
```bash
python tools/check_consistency.py --file research/<slug>/report.md
python tools/check_consistency.py --slug <slug>          # 默认严格阻断，提示级命中同样失败
```

**设计原则**：只保留同报告内必然同一主体的强单位（移除"分/条/个/次"等跨主体极常见的泛化单位，避免"53分 vs 57分"不同模型分数误报）。**回归测试**：`tests/test_consistency.py`（12 条）；已登记 REQUIRED_FILES。

## check_citation_validity.py — 违规引用检查（作者真实性/题名一致性/URL 伪造，学术纪律）

**作用**：把两类引用违规机器化——编造作者（"Li Y, et al." 系虚构，CrossRef 核验真实作者为 Miao Yuchun 等）与张冠李戴（正文描述与引用文献实际内容不符）。check_gbt_refs 只查著录格式，本工具查「引用本身是否真实」。**学术纪律**：核验失败 ≠ 核验通过——联网核验失败默认硬伤阻断，不得静默放行；显式 `--offline` 才允许跳过并声明"离线模式"**。两级检出：
- **[硬伤]**（命中即退出码 1）：
  1. **URL 伪造/占位符**：URL 含 `#related`/`#anchor` 等伪锚点（真实文献 URL 不带此类锚点），或 example.com/\<...\>/TBD 等占位符
  2. **arxiv URL 非法**：arxiv.org/abs/<id> 中 id 不合法（须 YYMM.NNNNN 格式）
  3. **疑似编造作者**（联网核验，`--offline` 跳过）：条目含 doi.org URL 时调 CrossRef works API，著录作者与注册作者比对不一致；arXiv 条目同样比对作者（Given Family 全名 → 取姓）
  4. **题名与文献不符**（联网核验）：DOI 条目经 CrossRef、arxiv 条目经 arXiv API 核验题名，规范化后不一致（连字符/破折号变体已归一化）
  5. **作者误用（佚名）**：著录"佚名"但 CrossRef/arXiv 注册库有作者 → 硬伤（GB/T：无作者才写佚名）
  6. **引用日期早于发布日期**：著录引用日期 < 注册库发布日期 → 硬伤
  7. **普通 URL 死链**：非 DOI/arxiv 的 URL 返回 404/5xx → 硬伤（引用须可溯源）
  8. **联网核验失败**：含 DOI/arxiv 条目但 CrossRef/arXiv 核验网络失败 → 硬伤（默认模式；`--offline` 显式声明后跳过）
- **[提示]**（默认同样阻断）：英文作者未按 GB/T 规范（姓全大写 名首字母）；正文 [n] 引注处上下文与题名关键词不匹配（启发式）；普通 URL 可达性无法验证

**用法**：

```bash
python tools/check_citation_validity.py --file research/<slug>/report.md
python tools/check_citation_validity.py --slug <slug>            # 检查 research/<slug>/report.md
python tools/check_citation_validity.py --file x.md --offline    # 显式声明放弃联网核验（输出注明"离线模式"）
python tools/check_citation_validity.py --file x.md --verbose    # 默认严格阻断，提示级命中同样失败
```

**接入**：`check_all.py` 全库体检新增「违规引」列（硬伤判 X，联网核验）；`note_upload.py` 上传前以 `--offline` 模式拦截 URL 伪造/占位符/arxiv 非法 id/作者格式（上传链不阻塞；报告质检阶段执行完整联网核验）。**回归测试**：`tests/test_citation_validity.py`（26 条正/负/mock 联网用例）；已登记 REQUIRED_FILES。注意：作者比对忽略大小写与顺序、比对前 3 位；`--offline` 是显式纪律声明而非默认降级；DOI 含括号（Elsevier 格式）与引用日期紧邻 URL 均已正确处理。

## check_progress.py — 阶段进度校验

**作用**：读取 `research/<slug>/.progress.json`，校验前置阶段是否完成，供阶段 2-4 进入前确认（对应 SOP 附录 A「输出未达校验即阻塞」）。**领域 P0 校验**：`--require report_channels` 时按领域矩阵判定 P0 通道——P0 通道登记 skip 且 note 无原因（未连接/不适用/未配置等）即阻塞，防止"名义跳过、实际未做"。

**用法**：

```bash
python tools/check_progress.py --slug <slug>                      # 展示当前进度
python tools/check_progress.py --slug <slug> --require phase1_done # 校验前置阶段（通过退出码0，阻塞退出码1）
python tools/check_progress.py --slug <slug> --require_round auto # 校验迭代轮次（auto 按 .progress.json 的 domain 自动判定：默认统一 1 轮，）
python tools/check_progress.py --slug <slug> --require_round 1   # 或显式指定轮次
python tools/check_progress.py --file research/<slug>/report.md  # 等价写法（由路径反推 slug）
```

**说明**：当前已知阶段键为 `phase1_done`（阶段 0 初始化 + 阶段 1 通道 A 完成）。进入阶段 2 前先跑本工具确认前置就绪。`--require_round auto` 依赖 `.progress.json` 的 `domain` 字段；该文件由 `init_research.py` 初始落盘（`round=1`）、`research_start.py` 合并更新；旧进度文件无 `domain` 时回退为 1 轮。

**参数口径**：四个质检工具的 `--slug` 与 `--file` 互为别名（`--slug <slug>` ≡ `--file research/<slug>/report.md`），传哪个都能跑，不必记忆各自的历史写法。

## check_report_structure.py — 报告章节结构校验

**作用**：校验 report.md 章节结构完整性——`###` 小节不带编号且标题不重复、顶层仅 `## 参考文献`、参考文献含 GB/T 7714 编号条目（兼容 `[标题](url)` / 纯文本标题旧格式）、无模板占位符残留。防止在报告上迭代插入章节时覆盖/错位标题（实战多次发生，人工发现成本高）。

**用法**：

```bash
python tools/check_report_structure.py --file research/<slug>/report.md
python tools/check_report_structure.py --slug <slug>   # 等价写法
```

**输出**：全部通过退出码 0；检出问题（标题重复/缺参考文献/占位符）退出码 1 并列出位置。开头结论段不设标题，直接跟在标题行后；不再要求「执行摘要」章节。

## check_all.py — 全库一键体检（交付前必跑）

**作用**：批量对所有 `research/*/report.md` 跑六项检查——结构校验（check_report_structure）、质量检查（quality_check）、轮次校验（check_progress auto）、结论检查（一段式/≤300 字，结论段为标题行后首个标题行前的段落）、落报告纪律（check_progress report_channels）、docx 存在性，输出汇总表（每篇 OK/X + 问题数）。交付前快速确认全库健康，避免逐篇跑。

**用法**：

```bash
python tools/check_all.py          # 全库体检（含 PASS 报告）
python tools/check_all.py --quiet  # 仅输出不达标报告
python tools/check_all.py --offline  # 违规引用检查使用离线模式（无外网环境）
python tools/check_all.py --jobs 8   # 并行体检并发数（默认最多 4）
python tools/check_all.py --quick    # 跳过工具自测/项目自检，快速体检
```

**说明**：历史报告（前按 3 轮标准完成）轮次列可能标 X，属标准升级遗留，不影响内容；质量列的非启发式命中（评价词/立场词等）需人工查看明细确认是否误报（如"暴涨"描述 JKM +60% 事实）。

## report_to_docx.py — 研究报告 → docx 转换

**作用**：把 report.md（URL 引用版）转换为 Word 文档——标题映射 Heading 1/2/3（微软雅黑）、段落/列表/表格转 Word 样式、图片从公网 URL 下载嵌入（失败保留 URL 文本）、图注转图片下方灰色小字。**只转格式、一字不改**。

**用法**：
```bash
python tools/report_to_docx.py --slug <slug>          # 生成 research/<slug>/report.docx
python tools/report_to_docx.py --slug <slug> --out x.docx   # 自定义输出名
```

**依赖**：python-docx（隔离 venv，默认仓库根 `venv/`，可用环境变量 `ZHIHU_ASK_VENV_PY` 覆盖）。`ensure_docx()` 在主解释器缺包时会**自动创建 venv 并 `pip install python-docx`** 后重跑自身，无需手动安装；依赖清单见仓库 `requirements.txt`。图片需公网可访问（`--url-base` 部署的 CloudStudio 托管）。

**注意**：docx 与 report.md 同级存放（单一文件约定）；图片下载失败不中断转换，位置保留 alt（URL）文本并提示。

## report_to_flomo.py — 研究报告 → flomo 格式存档（本地，不上传）

**作用**：把研究报告【完整内容】转换为 flomo 兼容格式（**只转格式、一字不改**），供上传到 flomo 个人笔记。参考 mynews 项目（外部项目，本地路径已省略）的 flomo 集成模式。flomo 仅支持加粗/高亮/下划线/有序/无序列表，不支持标题/引用/代码块/链接/表格，故做机械转换：标题（#）→ 加粗、引用（>）→ 正文、表格行 → 列表（- a / b）、链接 [标题](url) → 标题（url）、图片按来源分流（**公网 URL** `![alt](https://…)` → alt（url），保留地址供追溯；**本地相对路径** `![alt](chart_x.png)` 独占一行时**整行丢弃**——本地路径在 flomo 既不可点也不显示，且报告规范里其后紧跟「图 N｜…」图注行，保留 alt 会与图注重复）、反引号 → 去掉。

**flomo 图片能力（官方文档研究结论）**：flomo 平台**支持图片**——URL Scheme `flomo://create?image_urls=[...]`（最多 9 个公网图片 URL，需 PRO 会员 + flomo 客户端）；存储免费 500M（压缩）/PRO 20G（原图）。但当前接入的 flomo 官方 MCP 的 memo_create/memo_update 无图片参数，故文本版不含图片；未来带图上传可走官方 webhook API（`https://flomoapp.com/iwh/{token}`，需 PRO）或 URL Scheme。

存档内容首行追加 `#知识基座 #一级领域 #二级领域` 标签（分类元信息，非报告内容）。

**用法**：

```bash
python tools/report_to_flomo.py --slug <slug>                     # 打印完整转换结果
python tools/report_to_flomo.py --slug <slug> --out flomo_full.md # 写文件（research/<slug>/）
```

**注意**：
- **不修改报告内容**：脚本只做格式转换，不摘要、不截断、不改写。
- **报告/索引禁止上传 flomo**：本工具仅生成本地存档 `flomo_full.md`（不上传）；上传动作由 `note_upload.py` 对模块化笔记逐条执行（上传前自动质检）。
- **隐私边界**：本工具仅生成本地存档 `flomo_full.md`（报告/索引禁止上传 flomo；上传动作由 note_upload.py 对模块化笔记执行）；素材库（gathered_*）、plan.md 仅存本地 `research/`（与 ima 隐私分级一致，见 docs/CONVENTIONS.md 第 7 节）。

## note_upload.py — 模块化笔记上传 flomo

**作用**：把 `research/<slug>/notes/` 下的模块化笔记逐条质检后上传 flomo；自动拦截违规文件（00_index.md 索引、report.md/report_draft.md 报告）。

**用法**：
```bash
python tools/note_upload.py research/<slug>/notes/            # 批量（逐条质检后上传）
python tools/note_upload.py research/<slug>/notes/01_x.md     # 单条
python tools/note_upload.py research/<slug>/notes/ --update   # 原地更新已上传 memo
python tools/note_upload.py research/<slug>/notes/ --max-retries 3   # 调整重试次数
```

**规则**：
- 上传前自动跑**双重质检**：`quality_check.py`（**笔记模式**：notes/ 目录自动启用——允许 Unicode 公式、识别「来源:」文献段）+ `check_gbt_refs.py`（**笔记模式**：识别「来源:」段，校验条目空行/编号连续/类型标识/URL 引用日期/悬空引注；笔记文献区是参考来源清单，不查"文献未被引用"），任一不过拒绝上传。
- **flomo 调用失败自动重试**：网络错误/超长 content 假报 toolName 等一律**重试单条完整版**（默认 5 次 × 间隔 30s，`--max-retries 0` 关闭重试但**仍会尝试 1 次**），禁止分段/精简/测试——对应记忆硬规则"反复重试直到成功"。
- **`--update` 原地更新**：上传成功把 `{笔记文件名: memo id}` 持久化到 `research/<slug>/.flomo_ids.json`；`--update` 按记录用 `memo_update` 原地更新（id 不变，对应"禁止新建多版本"纪律），无记录的文件回退 `memo_create` 并补记。ids 文件为内部文件（不入 git、不上云）。
- 质检与上传共用 quality_check 的笔记模式；`--force` 跳过质检（慎用）。

## wechat_search.py — 微信公众号检索包装（通道 A）

**背景**：wechat-article-search 技能脚本经命令行传中文会乱码——本包装从 UTF-8 关键词文件读取检索词，进程内直调，绕开命令行。

**降级**：`sogou_search.py` 缺失时自动降级为 ddgs 检索 `site:mp.weixin.qq.com <关键词>`（多关键词并行 `--parallel N`、命中后抓页面补真实标题/公众号名、去虚词重试）；实测 7 词串行 10+ 分钟 → 并行 27–40 秒。

**用法**：
```bash
# 1. 准备关键词文件 tools/keywords.json（UTF-8，参考 keywords.example.json）：{"queries": ["<主题词> 突破", ...], "count": 10}
# 2. 检索最近 N 天并落盘素材库（推荐）：
python tools/wechat_search.py --keywords tools/keywords.json --days 30 --output research/<slug>/gathered_wechat.md
```

**自动登记通道 A**：`--output` 写到标准路径 `research/<slug>/gathered_wechat.md` 即自动登记 A（done/empty 按命中数；`--slug` 可显式指定，否则从路径反推）。

**注意**：
- 关键词文件必须 UTF-8；必须设置环境变量 `WECHAT_ARTICLE_SEARCH_SCRIPTS` 指向技能 scripts 目录（`/c/...` 风格路径自动归一化；`run_pipeline.py` 启动时会预警）。
- 冷门词搜狗可能补旧文章，按 time 字段过滤；验证码提示稍后重试。
- **消费端防御**：`_normalize_results` 剥离 HTML 标签/实体、丢弃噪声记录；原始有内容但归一化后 0 条 → 判「解析结构漂移」并报错，避免坏解析污染通道 ledger（13 场景测试覆盖）。
## git_protect.py — 提交前检查

**作用**：提交前双检查——①阻止 `plan.md`、`research/`、`.codebuddy/`、`docs/PLAN__ARCHIVE.md`、临时 config 等内部文件被误提交；②**关键文件完整性校验**：docs/ 等核心规范文件缺失时阻止提交（曾因 docs/ 整体丢失后固化，防止"带着缺失状态继续提交"）。

**用法**：

```bash
python tools/git_protect.py    # 检查暂存区；发现问题则退出码 1 并列出
```

**注意**：内部文件清单（起）见 `tools/internal_files.py`（公共模块，与 health_check 共用）；关键文件清单（起）**复用 `health_check.py` 的 `REQUIRED_FILES` 作为单一真相源**（含全部 docs/ 模板/工具，共 30+ 文件），并追加项目级 skill 校验——不再独立维护清单，改清单只需改 health_check.py 一处。已通过 `install_git_hooks.py` 接入 pre-commit hook，提交时自动执行；如需手动校验也可单独运行本脚本。

## install_git_hooks.py — pre-commit hook 安装

**作用**：把 `git_protect.py` 接入 git，使每次 `git commit` 自动执行检查，暂存区含内部文件时阻止提交。

**用法**：

```bash
python tools/install_git_hooks.py          # 安装/更新 hook
python tools/install_git_hooks.py --remove # 移除 hook
```

**注意**：hook 写入 `.git/hooks/`（本地，不入库），重新 clone 后需重跑本脚本。安装后可验证：`git add -f <内部文件>` 后 `git commit` 会被阻止，再 `git reset HEAD <file>` 恢复。

## clean_workspace.py — 工作区清理

**作用**：删除运行产生的缓存与临时文件（`.tmp/`、`__pycache__/`、`*.pyc`、`*.tmp`、`*.bak`、`*.log`、`Thumbs.db`、`.DS_Store`），不触碰源码、研究产出、配置与文档。

**用法**：

```bash
python tools/clean_workspace.py            # 实际清理
python tools/clean_workspace.py --dry-run  # 只列出将删除路径
```

## maintain.py — 项目一键维护

**作用**：按固定顺序执行“清理工作区 → 全量回归测试 → 一致性检查 → 展示 git status”。任一环节失败立即阻断，不自动提交。

**用法**：

```bash
python tools/maintain.py
python tools/maintain.py --skip-clean
```

## health_check.py — 项目健康自检

**作用**：一键验证项目就绪状态，适合新会话启动或排障时运行。检查 Python 环境、git 分支/远程/同步状态、pre-commit hook、内部文件是否被跟踪、关键文件完整性。

**用法**：

```bash
python tools/health_check.py
```

**输出**：逐项 `[OK]/[FAIL]`，全部通过退出码 0，有失败项退出码 1。新会话开始时先跑一遍，可快速确认环境是否就绪。

## net_check.py — 外网出口检测

**作用**：本环境沙箱 Bash 通常无外网出口（`curl`/`urllib` 即使放开沙箱也返回 0 字节），只有 agent 的 WebFetch/WebSearch 走 WorkBuddy 后端代理才能联网。`report_to_docx`（图片下载）、`report_images` 等需要外网的脚本先调用它检测出口，缺失时打印清晰提示（而非静默失败让人误以为成功）。

**用法**：
```bash
python tools/net_check.py                       # CLI：打印出口状态
# 作为模块：from net_check import require_egress
#   if require_egress("报告图片下载"): ... 执行外网动作 ...
```

## rag_build.py / rag_search.py — RAG 知识库（检索项目内经验）

**作用**：把公开文档（docs/ + templates/）变成可检索知识库，研究启动前先查项目内已有经验——流程规则、关键词词库、模板结构、写作规范、踩坑沉淀，避免每次研究从零开始。

**用法**：

```bash
python tools/rag_build.py                # 构建索引（改动 docs/ 后需重跑）
python tools/rag_search.py "笔记本 8000 学生"     # BM25 检索，默认前 5 条
python tools/rag_search.py "关键词 回填" -k 10    # 指定条数
python tools/rag_search.py "立场 纯事实" --file docs/STYLE_GUIDE.md  # 限定文件
```

**说明**：零第三方依赖（中文按字符 bigram + 英文按词切分，BM25 打分）；索引为派生缓存，存 `.codebuddy/knowledge/knowledge.db`（SQLite）仅本地，不进入 git。建议研究流程中在阶段 0/1 前执行一次，把命中片段作为检索起点。

## keywords_db.py — 关键词库 SQLite 管理

**作用**：关键词库主存储从 `docs/KEYWORDS.md` 迁到 `.codebuddy/knowledge/knowledge.db`；`docs/KEYWORDS.md` 保留为可读导出物，由本工具同步。

**用法**：

```bash
python tools/keywords_db.py --init                          # 首次初始化并导入 docs/KEYWORDS.md
python tools/keywords_db.py --import docs/KEYWORDS.md       # 从 Markdown 覆盖导入
python tools/keywords_db.py --add --section "数学 / 概率论" --kind "已验证有效组合" \
    --content "- `Equi-dependence implying independence`（arXiv 直查）" --slug foo
python tools/keywords_db.py --export docs/KEYWORDS.md       # 同步回可读 Markdown
python tools/keywords_db.py --list --section "数学"         # 按领域列出
python tools/keywords_db.py --search "arXiv"                # 内容检索
python tools/keywords_db.py --path                          # 打印数据库路径
```

**说明**：新增/回填关键词统一走 `--add`，需要保留可读文件时再 `--export`；不要直接手改 `docs/KEYWORDS.md`，否则下次 `--import` 会覆盖。

## ima 连接器 — 通道 E（ima 知识内容检索）

**两级检索**（主代理直执连接器工具，无 CLI）：
- **E1 经验检索**：`search_knowledge_base` 定位库 → 个人库/项目沉淀 `search_knowledge`，与本地 `rag_search.py`（SQLite BM25）互补。
- **E2 内容素材检索（核心）**：按领域从 `docs/IMA_LIBRARIES.md` 取候选订阅库（取全），逐库 `search_knowledge` 检索（每库 ≥2 个不同关键词），命中落盘 `research/<slug>/gathered_ima.md`（条目含 库名/标题/类型/media_id），与 A/B/C 并列计入有效通道；阶段 3 需原文时 `fetch_media_content(media_id)` 读取。全部候选库+全部关键词无命中才可记"通道 E 无有效素材"。

**纪律**：
- 连接器未配置 → 环境级自动 skip（见 `docs/SOP.md` 阶段 1），无需逐篇检查；接入后设 `ZHIHU_ASK_UNCONFIGURED_CHANNELS` 恢复手动登记。
- 隐私：读取无限制；写入仅限公开级内容（docs/、templates/、脱敏经验与词库；定稿 report.md 须用户确认）；gathered 素材、plan.md、问题原文禁止写入。
- 凭证：连接器方案无需凭证；脚本化（OpenAPI）才需 Client ID + API Key（agent-interface 生成，仅显示一次），存 `~/.config/ima/` 或环境变量。
## 领域连接器 — 通道 C 数据源（通达信 / 企查查 / 智慧芽）

**作用**：通道 C 一手数据源（主代理直执连接器）：行情/K线/F10（通达信）、企业工商/股东/实控人/财务（企查查）、专利/论文（智慧芽）。三者为通道 C 对应领域必做项（科技产业/财经时政 P0、学术科研 P1）；finance 插件按需。

### 通达信 tdx-connector（金融行情与数据）

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `tdx_lookup_stock` | 名称/别名 → 证券代码（**行情类工具前置步骤**） | query；range: AG=A股(默认)/HK-GP/QH 期货/QQ 期权等 |
| `tdx_quotes` | 实时行情快照（含 PE/PB/ROE/市值，hasCwInfo="1"） | code（纯数字）, setcode（1=沪 0=深 31=港） |
| `tdx_kline` | 历史 K 线走势 | code, period |
| `tdx_api_data` | F10 深度数据：财报 6 年/股东/资金流向/龙虎榜/分红/研报评级等 30 接口 | entry（精确接口名）, code, fixedTag |
| `tdx_screener` | 条件选股 | 选股条件 |
| `tdx_indicator_select` | 技术指标（MACD/KDJ/RSI）NLP 查询 | 指标+标的 |
| `wenda_macro_query` | 宏观数据问答 | 宏观指标 |
| `wenda_news_query` / `wenda_notice_query` / `wenda_report_query` | 新闻 / 公告 / 研报检索 | 关键词 |

### tdx_query.py — 通达信 TQ 本地查询（本地 HTTP 模式）

**作用**：连接器不可用时的本地兜底——调本机通达信客户端内置 HTTP 服务（`127.0.0.1:17709`，JSON-RPC）取行情/财务/板块/分红，零 Python 依赖（tdx-tq-local SKILL 方案，实测可用）。

- 前置：通达信客户端（TdxW.exe）运行中且已登录；K线历史条数取决于客户端本地已下载数据（先盘后数据下载）。
- 用法：`python tools/tdx_query.py <lookup|snapshot|kline|info|more|relation|divid|all> --code 600519.SH [--period 1d --count 10 --fields A,B --json]`；查代码用 `lookup --name 贵州茅台`。
- 输出：格式化中文摘要或 `--json` 原始 JSON；退出码 0 成功 / 1 连接失败或业务错误 / 2 参数错误。
- 纪律：取数仅供研究素材，A 股行情字段仍禁止进报告正文（quality_check check_stock_info 拦截）；财务数值逐字引用不自算。

### 企查查 qcc-company（企业尽调）

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `get_company_by_query` | 模糊搜索锁定企业实体（**尽调类工具前置步骤**） | searchKey；多候选必须展示给用户确认，禁止自动选第一条 |
| `get_company_profile` | 企业画像（业务/行业） | 完整企业名或统一社会信用代码 |
| `get_company_registration_info` | 工商登记（法定代表人/注册资本/成立日期） | 同上 |
| `get_shareholder_info` | 一层直接股东 | 同上 |
| `get_actual_controller` | 实控人（穿透终值，服务端已聚合） | 同上 |
| `get_financial_data` | 核心财务（比率均为服务端精算） | 同上 |
| `get_listing_info` | 上市信息（代码/市值/股本） | 同上 |

**使用纪律（金融数据红线）**：
- 通达信 code 只接受纯数字，中文名必须先 `tdx_lookup_stock` 查码；code 与 setcode 必须匹配。
- 接口返回空结果时**如实报告"该数据暂无"**，禁止用训练知识填充数字（金融场景虚假数据会严重误导）。
- 企查查 `get_company_by_query` 返回多候选时**必须将候选列表完整展示、等待用户确认**后再调下游工具；自动选第一候选属于错误操作。
- 企查查穿透类结果（实控人持股比例、受益股份、财务比率）为服务端精算终值，**逐字引用，禁止自行乘法重算或臆测中间层**（模型多位小数乘法不可靠，已实测算错案例）。
- 智慧芽 `patsnap_search` 的 search_strategy 与参数**严格绑定**：含 "semantic" 才传 semantic_query（技术问题描述）、含 "keyword" 才传 keywords（原子术语 3-8 个）、含 "filter" 才传 filters（申请人/IPC/日期/法律状态等）；**专利与论文两个独立调用**（source=patent/paper）；全文用 `patsnap_fetch`（一次 ≤100 条）。无命中记录"通道 C 智慧芽无有效素材"。
- 通达信/企查查同为必做（先 lookup 查码 / 先 by_query 锁定实体），无命中记录"通道 C [数据源]无有效素材"；各数据源只读，不执行交易、不写回。
- 各数据源均为只读：只做查询引用，不执行交易、不写回任何数据。
- 连接器未连接/返回空时跳过该数据源，改用 Web 或其他插件补位，不阻塞流程（见 SOP 异常表）。

## wechat_publish.py — 微信公众号草稿推送

**作用**：研究报告 → 公众号草稿箱（半自动：推送草稿箱，后台人工勾选原创声明/赞赏后发表）。按用户指示执行。

- 凭证：环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET`（后台→开发→基本配置，IP 白名单需含本机出口 IPv4）/ `WECHAT_AUTHOR`（作者，如"清杯浊酒"）
- 用法：`python tools/wechat_publish.py --slug <slug> --source-md [--title ...] [--author ...] [--cover ...]`
- 能力：access_token 2 小时缓存、自动封面（900×500 标题渐变图）上传永久素材、md→美化 HTML（内联样式：标题蓝线/两端对齐/引用块/表格/代码块）、**公式 $...$ 经 latex_unicode 转可读 Unicode 文本**（微信 HTML 不支持公式渲染）、draft/add 推送草稿箱
- 限制：**API 不支持 docx 上传**（material/add_material 仅 image/voice/video/thumb，实测 40113）与原创声明/赞赏（字段被静默忽略）；docx 只能后台手动上传（OMML 公式正常显示）；图文标题由 title 字段承载，md 首行 # 标题自动跳过
- 依赖：requests 可选；latex_unicode 为内置模块
## env_loader.py — 本地敏感配置加载（.env）

**作用**：加载项目根 `.env` 中的敏感配置（API key 等）到 `os.environ`。背景：沙箱下 `[Environment]::SetEnvironmentVariable` / `setx` 写用户级注册表被拒（registry access not allowed），`.env` 为后备通道（.gitignore 已忽略 `.env`/`.env.local`，不入库）。

- 用法：`from env_loader import load_dotenv; load_dotenv()` 后 `os.environ.get("TAVILY_API_KEY")`
- 优先级：真实环境变量优先（`.env` 不覆盖已存在的键）；重复键以首个为准
- `.env` 格式：`KEY=VALUE` 每行一条，`#` 开头为注释，值可带引号（自动剥除）；只读加载不写回
- 已在 `web_search.py`（tavily 引擎）接入；测试 `tests/test_env_loader.py`（16 项）

## web_search.py — Web 搜索兜底（多引擎聚合）

**作用**：agent 的 WebSearch 工具不可用时的检索兜底——**多引擎聚合，无需 API key**：

- `ddgs`（DuckDuckGo 元搜索库，通用网页/新闻，默认首选）
- `openalex`（OpenAlex 学术论文 API，免费稳定，学术主题质量高）
- `crossref`（CrossRef DOI API，免费稳定，学术条目）
- `hn`（Hacker News Algolia API，技术社区讨论）

- 安装：`pip install ddgs`（已入 requirements.txt；openalex/crossref/hn 引擎用标准库 urllib，无需额外依赖）
- 用法：`python tools/web_search.py "关键词" [--max 10] [--news] [--engine auto|ddgs|openalex|crossref|hn] [--timelimit year] [--timeout 30] [--out 素材.md] [--json]`；`--out` 追加式落盘（标题/链接/摘要）
- 引擎选择：`--engine auto`（默认）**并行**尝试 ddgs / openalex / crossref / hn / bing / tavily，首个返回非空结果的引擎胜出；`--news` 仅 ddgs/bing/tavily 支持；`--timelimit`（day/week/month/year）时间过滤，仅 ddgs/bing；`--timeout` 为 auto 模式单轮引擎总超时（秒，默认 30）
- 通用增强：ddgs 后端容错链（duckduckgo → bing → brave）+ 重试退避（重试轮数 3→2 减少空转）；查询变体自动重试（去引号/截断超长）；低质量域名过滤（图片/视频/盗版/成人/游戏站 40+ 域）；region 自适应（含中文 → cn-zh）；**news 模式 cn-zh 全灭自动回退 us-en（实测 cn-zh 三后端均 "No results found" 而 us-en bing/brave 正常）**
- **curl 兜底**：openalex/crossref/hn 引擎的 `http_get_json` 在 urllib SSL/代理栈失败时自动改调系统 curl（libcurl/OpenSSL 独立栈，实测本机 urllib 偶发"无外网出口"而 curl 正常）；双通道都失败才抛异常交调用方容错
- **加速**：auto 模式引擎并行化（首个非空即返回，其余引擎在 daemon 线程后台收尾，主进程退出即终止——初版用 ThreadPoolExecutor 的 `with` 退出会 `shutdown(wait=True)` 等慢引擎跑完，实测 ddgs 反爬空转把整体拖到 30+ 秒，改为 daemon 线程后单查询 31.8s → 3s）；ddgs 反爬时单后端失败约 11s，无法再快
- 顶层自动设置 `SSL_CERT_FILE`（certifi CA bundle），消除 Windows ssl 证书存储加载失败的 C 层 stderr 噪音（该噪音不走 warnings 系统，filterwarnings 无效，且被 PowerShell 误判为 NativeCommandError）
- 退出码：0 成功 / 1 搜索失败 / 2 参数错误；全部引擎+重试+变体仍失败时如实报错，提示走 WebFetch 降级
- **Bing HTML 引擎（免费无 key）**：`--engine bing`——直抓 Bing 搜索结果页（b_algo 块解析），含中文查询自动走 cn.bing.com（国内可达、中文结果质量高，实测 IT之家/知乎/LINUX DO 等），英文走 www.bing.com；支持 `--news` 与 `--timelimit`（cn.bing 用 `qft=+filterui:age-ltN` 时间过滤）；auto 模式已纳入并行候选。实测背景：SearXNG 公共实例普遍反爬（浏览器验证/429）、Mojeek API 403、DDG lite/百度反爬，Bing HTML 是本机（经代理）唯一稳定可用的免费无 key 通用引擎；英文查询受中国市场局限（镜像站污染已入 LOW_QUALITY_DOMAINS 过滤，英文通用搜索仍靠 ddgs）。
- **Tavily AI 搜索引擎**：`--engine tavily`——POST api.tavily.com/search，返回 title/url/content + AI 摘要（answer 兜底作 body）；支持 `--news`（topic=news）；依赖 `TAVILY_API_KEY`（环境变量或项目根 `.env`，见 tools/env_loader.py），未配置时自动跳过不报错。实测英文与中文查询质量均高（Forbes/新浪/36氪/TechNews 等，含 AI 摘要）。auto 模式已纳入并行候选。

## web_fetch.py — Web 页面抓取（Jina/直连/代理三级降级）

**作用**：抓取单个网页全文。Substack、ai.google.dev、deepmind.google 等站点直连常超时（WinError 10060），代理可通但部分页面只返回 JS 截断版；实测 r.jina.ai（Jina Reader）经代理对上述站点稳定返回完整 Markdown 正文。

- 用法：`python tools/web_fetch.py --url <URL> [--out <file>] [--mode md|html|text] [--proxy http://127.0.0.1:7897] [--timeout 40]`
- 三级降级（首个成功即返回）：① Jina 经代理（Markdown 全文，优先）→ ② Jina 直连 → ③ 直连 HTML → ④ 代理 HTML
- `--mode md`（默认）输出 Markdown（Jina 结果；Jina 失败则从 HTML 提取正文文本）；`--mode html` 输出原始 HTML；`--mode text` 输出纯文本
- `--no-proxy` 禁用代理；`html_to_text()` 提供 HTML→纯文本提取（剥 script/style/标签、解实体、保留表格/列表结构），可作库函数复用
- 无 `--out` 时打印到 stdout；退出码 0 成功 / 1 全部路径失败（stderr 打印各路径错误摘要）
- 测试：`tests/test_web_fetch.py`（html_to_text 提取 + 降级顺序 monkeypatch + 参数解析，20 项）

## arxiv-watcher + tools/arxiv_search.py — arxiv 平台（归入通道 P）

**作用**：arxiv 预印本检索（学术主题与智慧芽已发表论文互补）。日常用统一入口 `tools/preprint_search.py --platform all`；本工具用于单独检索 arxiv 或 WebFetch 降级。`arxiv-watcher` 的 shell 脚本（curl 实现）在本环境**永远空返回**，不要依赖。

**用法**：
```bash
python tools/arxiv_search.py --query "constrained decoding JSON" --count 5 --out research/<slug>/gathered_arxiv.md   # 直连
python tools/arxiv_search.py --query "..." --print-web-prompt   # 429 限流时：打印 URL 与 prompt → agent 用 WebFetch 抓取存 arxiv_raw.txt
python tools/arxiv_search.py --raw arxiv_raw.txt --out research/<slug>/gathered_arxiv.md   # 解析落盘（Atom XML / 分隔符文本均可）
```

**要点**：
- urllib 直连/代理失败自动 curl 兜底（curl 独立 SSL 栈本机实测可用），仍失败才走 WebFetch。
- 多词裸查询自动 AND（空格=OR 是 ArXiv API 陷阱，`sortBy=relevance`）；精确短语用引号。
- **自动登记通道 P**：`--out` 写到标准 `research/<slug>/gathered_arxiv.md` 即自动登记（done/empty 按命中数；`--slug` 可显式指定）。
- 检索词用英文（元数据为英文），2-3 组主题词；零结果换词重试 1 次，仍无记录"通道 P 无有效素材（arxiv）"。
- 需全文时 `web_fetch` PDF 链接提取（`arxiv.org/pdf/<id>`）。
## preprint_search.py — 学术预印本聚合（通道 P：arxiv + bioRxiv + 浪淘沙 + PSSXiv）

**作用**：预印本检索统一入口，聚合四个来源——**arxiv**（复用 arxiv_search 逻辑）、生物医学 **bioRxiv**、跨学科中文预印本 **浪淘沙**（LangTaoSha，OJS 3.5）、哲学社会科学预印本平台 **PSSXiv**（中国人民大学复印报刊资料运营，zsyyb.cn）。四平台接入方式：

- **arxiv**：复用 `tools/arxiv_search.py` 的 build_url/fetch_atom/fetch_atom_curl/parse_atom_xml（含 curl 兜底与 AND 语义）。
- **bioRxiv**：公开 REST API `api.biorxiv.org/pubs/biorxiv/<start>/<end>/<cursor>/<count>`（JSON：preprint_doi/title/authors/date）。服务端偶发 500，内置 3 次重试 + 分页（每页 100 条）。
- **浪淘沙**：OJS 3.5 `WebFeedGatewayPlugin` Atom feed（公开、无认证）——`langtaosha.org.cn/lts/gateway/plugin/WebFeedGatewayPlugin/atom`，全量条目本地按关键词过滤；摘要做 HTML 实体+标签清理。
- **PSSXiv**：POST `zsyyb.cn/user/search.htm`（`searchVal=<关键词>`），服务端渲染 HTML，解析 PSSXiv 编号/标题/摘要；平台已按关键词检索、不额外本地过滤。

**用法**：

```bash
python tools/preprint_search.py --platform all --keywords "RNA" --days 30 --count 5 \
    --out research/<slug> --slug <slug>   # 四平台聚合；--out 为目录，按平台分流落盘
python tools/preprint_search.py --platform arxiv --keywords "constrained decoding" --count 5
python tools/preprint_search.py --platform biorxiv --keywords "immunotherapy" --days 30
python tools/preprint_search.py --platform langtaosha --keywords "RNA"
python tools/preprint_search.py --platform pssxiv --keywords "人工智能"
```

**落盘分流**：`--out` 为目录（默认 `research/<slug>/`）；**arxiv 命中 → `gathered_arxiv.md`**，**bioRxiv/浪淘沙/PSSXiv 命中 → `gathered_preprints.md`**——两文件同属通道 P，检索完成后一次性自动登记通道 P（`done`/`empty` 按累计命中判定）。**回归测试**：`tests/test_preprint_search.py`（31 条 mock 用例）；已登记 REQUIRED_FILES。注意：bioRxiv 标题过滤（pubs 端点无摘要）、浪淘沙全量拉取慢（feed ~138KB）、PSSXiv 结果信任平台检索、arxiv 走 arxiv_search 的网络栈（直连→代理→curl 兜底）。

## mark_channel.py — 通道完成态结构化登记（落报告纪律条目级）

**作用**：将六通道（F/E/A/B/C/P）的执行态以结构化形式写入 `research/<slug>/.progress.json` 的 `data.channels_done`，供 `check_progress --require report_channels` 做「声明态 ⊕ 证据」双向交叉校验。替代旧版扁平 `channels:[...]` 列表（该字段从未被任何门禁读取，形同虚设）。通道清单与素材文件映射统一由 `channel_state.py` 维护（`file_to_channel()`/`files_for()` 供 check_progress 等推导，消除各工具手写清单的维护漂移）。

**用法**：
```
python tools/mark_channel.py --slug <slug> --channel A --status done
python tools/mark_channel.py --slug <slug> --channel E --status skip --note "ima 连接器未连接"
python tools/mark_channel.py --slug <slug> --channel P --status empty --note "通道 P 无有效素材"
python tools/mark_channel.py --slug <slug> --all-skip --note "未连接/不适用"   # 一键批量 skip 未声明通道
python tools/mark_channel.py --slug <slug> --list
```

`--all-skip`：把未登记的通道批量登记为 skip（已登记的保留原状）——适合 E 未连接、P 不适用等常见场景，避免逐个手动登记。

**status 取值**：
- `done`：通道已执行且产出有效素材（须有对应 `gathered_*.md` ≥200 字节；F 仅需 note 说明查重结论）。
- `empty`：通道已执行但零命中（须有 `gathered` 文件或 note 含「无有效素材/无命中」）。
- `skip`：通道不适用 / 连接器未连接（须有 note 说明原因）。

**校验**：登记后跑 `python tools/check_progress.py --slug <slug> --require report_channels`；声明 `done` 但对应素材文件缺失会提示（先登记后落盘属正常顺序，最终以门禁为准）。

**自动登记**：通道 A（公众号）在 `wechat_search.py` 落盘 `gathered_wechat.md`、通道 P（学术预印本聚合，含 arxiv）在 `arxiv_search.py` / `preprint_search.py` 落盘 `gathered_arxiv.md` / `gathered_preprints.md` 时**自动登记**对应通道（`done`/`empty` 按命中数判定），无需再手动跑本工具——前提是输出路径为标准 `research/<slug>/gathered_*.md`（可显式加 `--slug`）。本工具保留用于：E/F/B/C 通道登记、`--all-skip` 批量 skip、覆盖性重登记、以及 `--list` 查看。核心逻辑在 `tools/channel_state.py`，各工具共用。

**环境级自动 skip（连接器未配置通道无需逐篇检查）**：本环境未配置连接器的通道（ima E / 领域连接器 C 为默认值）由 `research_start.py` / `init_research.py` 初始化时**自动登记为 skip**（note 注明"环境级默认 skip"），跨研究共享——新建研究后 E/C 已预登记，无需手动检查或 `--all-skip`；`mark_channel.py --list` 会用「（环境级）」标注。连接器接入后用环境变量 `ZHIHU_ASK_UNCONFIGURED_CHANNELS` 覆盖（逗号分隔通道字母，如 "C" 表示仅 C 未配置；空字符串 = 全部已配置），`check_progress` 对未配置通道缺失声明也不阻塞。

## 三段论逻辑校验（实验性，syllogism_check.py）

**定位**：给报告关键推理做形式化结构诊断（半自动，中文语义解析需人工）。

**`tools/syllogism_check.py` — 三段论层验证**（半自动，中文语义解析需人工）：
- `--extract`：从报告提取三段论候选句式（凡/所有…都、因为…所以、因此/可见 引导结论），自动做**三件套齐备性检查**——识别省略三段论（enthymeme：缺大前提即提示"需补全后才能验证"，补不出大前提 = 推理不完整）。
- `--verify --major "∀ x, M x → P x" --minor "M a" --concl "P a"`：结构诊断——中项是否在大小前提同义出现（无交集即提示**四名词谬误/偷换中项**风险）、大前提是否全称。
- `--lean FILE`：运行 .lean 并诊断——`type mismatch` 自动判为"疑似偷换中项"。
- **边界（诚实版）**：形式有效 ≠ 前提为真（大前提真假是 axiom 层人工判断）；三段论只覆盖演绎子集，归纳/类比/统计推断不适用；中文→逻辑命题的形式化必须人工完成。

**纪律**：
- 三段论层：只对报告 2-3 条**关键断言**做（全量成本高）；补不出大前提的推理标记为"待补全"。
- 本机 lean 在 `~/.elan/bin` 或 `~/.local/bin`（已探测 4.31）；工具用 `lean --version` 探测，未装则报错提示。

## report_images.py — 报告配图（AI 封面 + 数据图表）

**作用**：AI 概念图**仅作封面** `ai_cover.png`（不插入正文）；量化数据一律用 Markdown 表格承载，数据图表（PIL 绘制）已弃用（工具保留但不向新报告插入 chart_*.png）。

**用法**：
```bash
AGNES_API_KEY=<key> python tools/report_images.py --slug <slug>          # 生成 AI 概念图封面
python tools/report_images.py --slug <slug> --skip-ai                    # 仅数据图表（旧报告用）
python tools/report_images.py --slug <slug> --embed-base64               # 图片内嵌单文件 report_embedded.md
python tools/report_images.py --slug <slug> --url-base https://...       # 图片 URL 引用版 report_url.md（在线发布首选）
```

**引用模式**：默认相对路径（report.md，本地 Typora/Obsidian）；base64 内嵌（自包含，体积 +33%）；公网 URL（`report_url.md`，知乎/公众号发布首选——图片先部署静态托管）。

**纪律**：
- 图片落盘 `research/<slug>/` 与 report.md 同级；按内容锚点自动插入对应小节（幂等，防重复插入）。
- 凭证 `AGNES_API_KEY` 环境变量传入，不入库。
- 数据图表用 PIL（Pillow），无需 matplotlib/venv；中文字体自动探测。
- **AI 概念图合规/主题/构图规则见 `docs/CONVENTIONS.md` §8**（纯抽象禁元素、紧扣主题、无留白；`call_agnes` 自动追加 `_AI_IMAGE_NEGATIVE_GUARD` 禁词句，生成后必须肉眼复检，违规删图重生成，`process_notes.md` 记录复检）。
## 降级方案

`research_subagent` 配置的模型不可用（"Model not found"），**主代理直执是当前默认方式**（非降级）：web_search / web_fetch 均由主代理调用，公众号检索走上述包装工具。已实测可行（两份研究均以此完成）。若子代理配置修复，可升级回并行分派。

## flomo 单条完整版上传（tools/flomo_upload_full.py，已弃用）

常规上传走 `note_upload.py`（模块化笔记逐条质检上传，报告/索引禁止上传）；本工具仅当用户明确要求回传某篇历史报告时使用：`python tools/flomo_upload_full.py --slug <slug>`（凭证环境变量 `FLOMO_TOKEN`，绕过客户端对超长 content 的调度层拦截）。
