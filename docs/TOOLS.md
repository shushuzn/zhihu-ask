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

`tests/` 下为工具回归测试套件，由 `tests/run_all.py` 统一运行（逐模块子进程执行、聚合 PASS/FAIL、任一失败退出码 1）：

```bash
python tests/run_all.py                 # 全量回归（质量/门禁/登记/自动登记）
python tools/check_all.py              # 全库体检（体检前自动先跑 tests/run_all.py）
```

| 测试模块 | 覆盖 |
|---|---|
| `tests/test_quality.py` | `quality_check.py` 全部规则的「必命中 / 必不命中」断言（125 项） |
| `tests/test_check_progress.py` | `report_channels` 双向交叉门禁：文件启发式回退 + 结构化正向/反向/完整性/report 承接（13 项） |
| `tests/test_channel_state.py` | `channel_state.py` 登记的纯函数：slug 反推 / load-save / mark 校验与 note 语义（37 项） |
| `tests/test_wechat_norm.py` | `wechat_search.py` 消费端防御 + 解析漂移检测 + 落盘自动登记通道 A + `_normalize_skill_path`（Git Bash `/c/` 路径归一化，实测踩坑：`/c/` 风格 Windows Python 不识别导致 sogou 找不到）（31 项） |
| `tests/test_arxiv_automark.py` | `arxiv_search.py` 落盘自动登记通道 P（5 项；arxiv 归入 P） |
| `tests/test_arxiv_query.py` | `arxiv_search.py` 的 `query_semantics_hint`：多词裸查询（空格+无引号+无 AND）触发 OR 语义提示，引号短语/显式 AND（含大小写变体）/单词/空查询不触发；curl 兜底四态（成功/无curl/空响应/异常）（23 项） |
| `tests/test_report_structure.py` | `check_report_structure.py` 五类结构规则的正向/负向断言：编号连续、参考文献合法条目（链接/编号/无序/纯文本标题）、占位符、测算融入（21 项） |
| `tests/test_report_to_flomo.py` | `report_to_flomo.py` 的 `convert_text`（标题/引用/表格/链接/图片/反引号机械转换 + 内容完整性）与 `pick_tags`（最长键优先匹配、兜底、大小写不敏感）（26 项） |
| `tests/test_git_protect.py` | `git_protect.py` 的 `_touches_tested` 分流与 `maybe_run_test_suite` 拦截逻辑（纯决策，不触发真实 git）（15 项） |
| `tests/test_internal_files.py` | `internal_files.is_internal` 隐私红线单一真相源：直配内部模式（plan.md/research//docs 归档/.codebuddy//.workbuddy//.tmp）、临时 config 双重限定（前缀+`.json` 后缀）、PUBLIC_EXCEPTIONS 豁免、核心脚本不得被前缀误伤、Windows 反斜杠归一化（31 项） |
| `tests/test_init_research.py` | `init_research.py` 的 `slug_ok`（短横线校验）、`parse_args`（CLI 解析/缺值/默认值）、`apply_replacements`+`fill_template`（占位符替换，plan 专属占位符仅 plan 模板替换）、`insert_index_row`（索引表插入：命中/缺 topic_slug 表头/缺分隔行/不污染后续小节）、`write_initial_progress`（落盘 stage/round/domain）（44 项） |
| `tests/test_check_all.py` | `check_all.py` 的 `classify_quality_hits`（软命中豁免：无来源数字/立场词不算硬失败）、`extract_conclusion`（结论段截至首个标题行/文末，含 `###` 平铺结构、空结论/无标题边界）、`conclusion_ok`（≤300 字/非 bullet）、`find_reports`（临时目录扫描）（25 项） |
| `tests/test_rag_build.py` | `rag_build.py` 的 `is_indexable`（research/ 仅收 process_notes.md 排除报告/素材噪音）、`parse_args`（--dir 多目录/缺值回退/默认）、`split_chunks`（##/### 切分、无标题内容归首片回退 path、短正文 <30 过滤、空节不产出、一级标题不切分）（23 项） |
| `tests/test_rag_search.py` | `rag_search.py` 的 `tokenize`（中文 bigram/单字/英文≥2 小写/数字/下划线连词/停用词过滤/英文数字在前中文在后的输出序）、`bm25`（tf 词频排序、df/idf 稀有词加分、file_filter 限定、空分片/无命中/空查询词）、`highlight`（命中标记+括号开销、上下文窗口、省略号前缀、无命中截断）（29 项） |
| `tests/test_knowledge_store.py` | `knowledge_store.py` 的 `parse_keywords_md`（前导/分节/kind 识别）、`import_keywords_md`/`export_keywords_md` roundtrip、`add_keyword`/`list_keywords`/`search_keywords`、`replace_chunks`/`load_chunks`（17 项） |
| `tests/test_health_check.py` | `health_check.py` 的 `find_missing`/`git_synced` 纯函数 + REQUIRED_FILES 一致性守护不变量：无重复、全量真实存在、全覆盖 tools/*.py 与 docs/*.md 与 templates/*.md（新增/改名工具漏登记即漂移）、含 tests/run_all.py、清单内无内部文件（否则 git_protect 永久阻止提交关键文件本身）、git_protect.KEY_FILES 为超集且技能文件存在（27 项） |
| `tests/test_report_to_docx.py` | `report_to_docx.py` 的 `split_rich`（**加粗** 标记解析：单段/混合/多段/单星号与裸双星不误判）、`parse_table_rows`（分隔行过滤、对齐分隔行、不等宽保留）、`normalize_img_ext`（查询串/白名单/未知与无扩展回退/大写归一）+ `convert_md_to_docx` 端到端（python-docx：标题层级、加粗 run、bullet/有序/引用、表格单元格、无 md 语法残留的一字不改契约）（41 项） |
| `tests/test_iter_research.py` | `iter_research.py` 的 `parse_args`、`round_status`（已达/还需 N 轮文案）、`get_current_round`（缺失/无 round/损坏 JSON 兜底 1）、`update_round`（新建默认 stage、保留 domain/channels_done 既有字段、覆写 round+round_updated）、`write_template`（生成问题清单模板、cur≥2 推进时归档 round_notes_r<N>.md、cur=1 不归档）（27 项） |
| `tests/test_net_check.py` | `net_check.py` 的 `has_egress`（mock urllib：非空响应/空响应/urlopen 异常/read 异常）与 `require_egress`（有出口无提示、无出口提示含 purpose 与 WebFetch 建议）（9 项） |
| `tests/test_research_start.py` | `research_start.py` 的 `validate_config`（question/slug 必填、slug 短横线格式、大写自动降级、keywords 缺失/不足下限警告非阻塞）、`write_progress`（合并保 round——覆盖丢 round 的历史 bug、新字段合并、损坏文件回退、setdefault 1）、`get_ima_library_hints`（词元双向包含匹配、≤2 组上限、空 domain/无文件/无匹配）（25 项） |
| `tests/test_install_git_hooks.py` | `install_git_hooks.py` 的 HOOK_TEMPLATE 内容（调用 git_protect.py/exit 0/勿手动编辑标记——模板回归会静默禁用提交保护）与装/卸行为（HOOK_PATH 打补丁：安装内容一致、移除、未装移除不报错、hooks 目录缺失退出码 1）（10 项） |
| `tests/test_run_pipeline.py` | `run_pipeline.py` 的 `agent_checklist`（slug/query 替换、六通道步骤齐全、无占位符残留）、`finish` 收尾门禁执行顺序（结构→质量→轮次→落报告→docx→flomo，Mock 替换子进程）、`bootstrap`（WECHAT 环境变量预警 + research_start 调用）、`main` 无参数退出码 1（15 项） |
| `tests/test_syllogism_check.py` | `syllogism_check.py` 的纯逻辑（不依赖 lean 二进制）：`find_candidates`（大前提/结论/因果链三类候选提取+去重）、`completeness`（三件套齐备性四分支+非三段论）、`diagnose`（中项共享/中项缺失四名词谬误风险/大前提非全称/小前提含 ∀）、`gen_skeleton_lean`（骨架注释与占位证明）；**移除死代码 `verify_triple`**（无任何调用、首段 code 赋值被覆盖、含 `sorry` 占位证明——误用会产出误导性"形式有效"判定）（22 项） |
| `tests/test_report_images.py` | `report_images.py` 的 `hex_to_rgb`（色值解析）、`insert_block_into_content`（本轮抽取的锚点插入纯函数：命中插到首段后不紧跟标题/加粗标题命中/未命中回退首个 ### 前/AI 概念图未命中跳过/无小节可回退）、图表冒烟（PIL 可用时 bar_group 1440×840 / bar_single / scatter 1440×960 生成 PNG）（19 项） |
| `tests/test_ai_voice.py` | `check_ai_voice.py` 两级检出：硬伤（空转过渡/需要强调/立靶子句式/标题禁词）与提示（装饰词/长插入语/引号日常词）+ 负例（正常语句/术语引号不误报）（12 项） |
| `tests/test_latex_unicode.py` | `latex_unicode.py` LaTeX→Unicode 转换：分数/根号/上下标/希腊字母/运算符/箭头/文本命令/组合/纯文本；**测试抓出并修复 \in 吞噬 \infty 的真实 bug**（按 key 长度降序替换）；嵌套分数/美元符为已知限制（13 项） |
| `tests/test_note_upload.py` | `note_upload.py` 上传质检链与拦截规则（索引/报告禁传、--update 原地更新）（21 项） |
| `tests/test_web_search.py` | `web_search.py` 解析纯函数（域名提取/结果过滤/region 自适应/查询变体/openalex/crossref/hn 解析）+ curl 兜底（urllib 失败接管、双通道失败抛异常）（43 项，含 curl 兜底） |
| `tests/test_check_flomo_note_refs.py` | `check_flomo_note_refs.py` 笔记参考文献合规判定：has_reference（来源:/参考文献/类型标识/URL/编号）、extract_title（tag 行/转义下划线/加粗清理）、URL 缺引用日期判不合规等（29 项） |
| `tests/test_citation_validity.py` | `check_citation_validity.py` 违规引用核验：URL/DOI 提取（括号 DOI、引用日期不吞）、作者匹配（真/假/空）、题名归一化（破折号/LaTeX）、离线四类硬伤、CrossRef mock 联网核验（作者/题名/佚名误用/引用日期早于发布）、网络失败硬伤阻断、显式 offline 放行、死链拦截、正文题名上下文提示、arxiv html/abs/pdf 识别与注册库核验（34 项） |

**纪律**：修改任一被测工具后，先跑 `python tests/run_all.py` 确认无回归再提交——规则静默回退会连累每一篇报告或污染通道 ledger。

**运行器注意**：`tests/run_all.py` 取子进程输出中**最后一个** `TOTAL: PASS=.. FAIL=..` 作为模块权威结果（避免被模块内部嵌套调用的子进程回显干扰而误报 / 掩盖失败）。


## init_research.py — 研究目录初始化

**作用**：一键创建新研究，避免手动复制模板。自动完成：创建 `research/<slug>/` 目录 → 从模板生成 plan/report/process_notes 三个文件 → 填入问题标题/日期/领域/slug（元信息行的领域与 slug 会实填，`report_to_flomo.py` 依赖该行解析 flomo 标签）→ 落盘 `.progress.json`（`stage=phase1_done`、`round=1`、`domain`，供 `check_progress.py` 校验）→ 在 `plan.md` 问题索引表登记一行。

**用法**（本机 PowerShell 下中文必须走 `--config` 文件）：

```bash
# 1. 准备 config 文件（UTF-8，参考 tools/init.example.json）
{
  "question": "示例问题标题",
  "domain": "示例领域",
  "slug": "example-slug",
  "priority": "高"
}

# 2. 执行
python tools/init_research.py --config tools/init.json
```

**参数**：`--config <json>` 或直接 `--question "标题" --domain "领域" --slug <slug> --priority <级别>`。

**注意**：
- slug 必须为英文小写短横线（如 `example-slug`）；目录已存在时会报错退出。
- config 文件用完即删；已通过 `.gitignore` 忽略 `tools/init.*.json` 模式。
- 生成文件保留未填占位符（主概念/关键词等），按 SOP 阶段 0–1 在 `plan.md` 中补齐；但元信息行（第 3 行）的领域与 slug 已实填，不要改回占位符，否则 flomo 标签会兜底为 `#{{...}} #综合`。
- 单独用本工具起研究时 `.progress.json` 已自动落盘，无需手工补造；走 `research_start.py` 时该文件会被合并更新（保留 `round`）。
- **模块化笔记目录**：初始化后自动创建 `notes/` 目录及统一模板，笔记扁平存放，靠标签区分类型。

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

**作用**：通过 flomo MCP 搜索笔记，支持关键词搜索和标签筛选。用于阶段0查重、阶段1补充已有笔记、阶段4写索引前盘点。

**用法**：

```bash
python tools/flomo_search.py --keywords "AI 编程"        # 关键词搜索
python tools/flomo_search.py --tag "AI编程"              # 按标签搜
python tools/flomo_search.py --tag "AI编程" --keywords "定价"  # 组合搜
python tools/flomo_search.py --keywords "定价" --limit 5  # 限制条数
python tools/flomo_search.py --keywords "定价" --full     # 输出完整笔记正文（memo_batch_get 拉全文）
python tools/flomo_search.py --keywords "主题词" --slug <slug>  # 查重后自动登记通道 F（done，note 含 memo_search 证据）
```

**凭证**：MCP Token **只从环境变量** `FLOMO_MCP_TOKEN` 读取（不读 `.env`，见 docs/CONVENTIONS.md）；此前硬编码在代码并进入公开仓库，**请先在 flomo 后台撤销旧 token 重建**，再设环境变量。未配置时查重调用报错并提示配置方式。

**F 通道自动登记**：带 `--slug` 执行即把通道 F 登记为 done（note 含 memo_search 证据，供 report_channels 门禁）；命中≥0.9 复用/更新、0.5~0.9 参考等结论由主代理阅读结果后用 `mark_channel.py` 补充/覆盖 note。

**工作流位置**：
- 阶段0：搜已有相关笔记，避免重复研究
- 阶段1：每收到新链接，先搜 flomo 看有没有相关笔记
- 阶段4：写索引前，盘点所有相关笔记

**上传规则**：
- 索引笔记(00_index.md)和报告禁止上传 flomo
- 笔记上传前必须跑质检: `python tools/quality_check.py --file notes/xx.md`

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

**说明**：`--config` 触发 `research_start.py`（会预警 `WECHAT_ARTICLE_SEARCH_SCRIPTS` 未设置）；`--slug` 触发 **clean_workspace → 质检八件套 → report_to_docx → report_to_flomo**（仅格式化，未上传）→ 打印 agent 待办（笔记上传 / AI 封面 / 发布前 `check_all.py`）。`--offline` 让违规引用门禁以 `check_citation_validity.py --offline` 运行，适合当前无外网环境；联网核验仍建议在外网环境补跑。收尾前的 Web/ima/C/arxiv 检索与 report.md 写作由 agent 完成。

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

## wechat_search.py — 微信公众号检索包装

**问题背景**：`wechat-article-search` skill 的 `sogou_search.py` 通过命令行接收中文关键词，但在本机 PowerShell 环境下中文参数会乱码（`chcp 65001` 也无法解决），导致通道 A 无法使用。

**解决方案**：包装脚本从 UTF-8 关键词文件读取检索词，直接在 Python 进程内调用 `sogou_search.py` 的函数，完全绕开命令行传参。

**降级模式**：`sogou_search.py` 缺失时（如本机未装 wechat-article-search 技能）**自动降级**为 ddgs 检索 `site:mp.weixin.qq.com <关键词>`（走 web_search.py 的后端容错链，无需安装），命中后用 urllib 抓取文章页补真实标题与公众号名（微信 PC 页 `h1#activity-name` / `a#js_name`）；原词无命中自动去虚词重试。输出格式与搜狗模式一致（标题/公众号/链接），降级模式下时间字段为空、相关性依赖搜索引擎索引。

**降级模式加速**：
- 多关键词并行检索：默认 4 个关键词同时跑（`--parallel N` 调整，仅降级模式生效），结果仍按关键词原顺序输出、落盘格式不变。
- 命中文章元数据抓取并行化（每关键词内部 6 线程），单页超时 15s → 8s。
- 实测：7 关键词串行约 10+ 分钟 → 4 关键词并行约 27-40 秒（瓶颈为 ddgs 反爬空转，单后端失败约 11s）。
- 顶层自动设置 `SSL_CERT_FILE`（certifi CA bundle），消除 Windows ssl 证书存储加载失败的 C 层 stderr 噪音（该噪音不走 warnings 系统，filterwarnings 无效）。

**用法**：

```bash
# 1. 准备关键词文件 tools/keywords.json（UTF-8，参考 keywords.example.json）
{
  "queries": ["<主题词> 突破", "<主题词> 产业化"],
  "count": 10
}

# 2. 检索最近 N 天
python tools/wechat_search.py --keywords tools/keywords.json --days 30

# 3. 落盘为素材库（推荐）
python tools/wechat_search.py --keywords tools/keywords.json --days 30 --output research/<slug>/gathered_wechat.md
```

**自动登记通道 A**：当 `--output` 写到标准路径 `research/<slug>/gathered_wechat.md` 时，脚本在写盘后自动把通道 A 登记进 `.progress.json`（`done`/`empty` 按命中条数判定），无需再手动 `mark_channel --channel A`。可用 `--slug` 显式指定 slug（否则从输出路径反推）。

**输出**：每个关键词的结果清单（标题/公众号/时间/摘要/链接），UTF-8 编码。

**注意**：
- 关键词文件必须 UTF-8 编码（用 write_to_file 创建即可保证）。
- **必须设置环境变量 `WECHAT_ARTICLE_SEARCH_SCRIPTS`** 指向 `wechat-article-search` 技能的 `scripts` 目录，否则脚本报「未找到 sogou_search.py」退出（`run_pipeline.py` 启动时会预警）。**路径归一化**：Git Bash 的 `/c/...` 风格路径会被自动转为 `c:/...`（实测 `/c/` 风格 Windows Python 不识别导致误报未找到）；Windows 原生路径原样使用。
- 冷门关键词搜狗可能补充旧文章，需按返回的 time 字段自行过滤。
- 触发验证码时返回 "触发验证码，请稍后重试"，稍后再试即可。
- 检索词的有效组合可写入 SQLite 关键词库（`python tools/keywords_db.py --add ...`，再 `--export docs/KEYWORDS.md` 同步），临时关键词文件用完即删。

**消费端防御**：上游 `sogou_search.py` 用正则 / HTML 结构提取，搜狗站内改版极易失效。本脚本在消费端加 `_normalize_results` 防御层：① 非字典记录直接丢弃并记录原因；② 标题 / 公众号 / 摘要字段剥离 HTML 标签与实体；③ 标题与公众号均空的记录视为噪声丢弃；④ 关键改进——**原始有内容但归一化后 0 条有效记录时，判定为「解析结构漂移」并合成 error**（而非静默当作「真无结果」），避免坏解析污染通道 ledger。13 场景单元测试覆盖正常 / 畸形 / 漂移 / 空结果等路径。

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

**作用**：接入腾讯 ima 知识库（ima.qq.com），在阶段 1 检索历史经验沉淀（跨问题语义召回），与本地 `rag_search.py`（SQLite BM25，词面匹配）互补。ima 为 RAG 语义检索，可召回措辞不同但语义相关的内容。

**使用方式**：非脚本，由主代理直执连接器工具（已授权连接，侧边栏「更多 → ima知识库」）：

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `search_knowledge_base` | 按关键词搜索知识库（名称/描述） | query, limit |
| `search_knowledge` | 在指定库内语义检索内容 | knowledge_base_id, query |
| `get_knowledge_base_list` | 列出个人/共享/订阅知识库 | params[{type, limit}]（type 必填，如 KBT_MINE_KB） |
| `get_knowledge_list` | 列出库内文件 | knowledge_base_id, limit |
| `fetch_media_content` | 读取文件正文 | media_id |
| `import_urls` | 批量导入网页链接（≤10 个/次） | knowledge_base_id, urls |
| `create_media` + `add_knowledge` | 上传本地文件入库（先建 media 取 COS 凭证再上传再入库） | knowledge_base_id, file_* |

**检索流程**（对应 SOP 阶段 1 通道 E；**通道 E 为阶段 1 执行顺序第一的检索**，先于 A/B/C/P 通道，为关键词与检索起点定基调），两级执行：

1. **E1 经验检索**（检索项目历史沉淀）：`search_knowledge_base "主概念"` 定位相关库 → 对个人库/项目沉淀库 `search_knowledge "主概念 关键实体"` → 命中片段纳入检索起点；无命中记录"E1 无有效素材"。
2. **E2 内容素材检索**（核心，把订阅库变成素材通道）：按问题领域从 `docs/IMA_LIBRARIES.md` 选取候选订阅库（金融/电子行业研究/科技公司财报/法律/AI/学术等分组，已列库名+ID+内容量）→ **对该领域全部候选库逐个**执行 `search_knowledge (knowledge_base_id, query)` → 命中内容落盘素材库。**执行纪律**：候选库取全（如数码/消费电子 → 电子行业研究库+明星科技公司财报库，不只查"最全研报库"）；每库 ≥2 个关键词重试（主概念+视角词）；全部库+全部词无命中才记录"通道 E 无有效素材"。

**gathered_ima.md 落盘格式**（每条命中的一个条目）：

```markdown
- **[标题]**（库名 · 类型 · 时间）
  摘要/简介首段（截断至 ~200 字）
  命中片段：`<highlight_content>`
  media_id: <media_id> ｜ knowledge_base_id: <id>
```

**正文读取**：阶段 3 交叉验证需要原文时，`fetch_media_content(media_id)` 获取全文（PDF/MD/网页均支持，can_fetch_content=true 条目可读）。

**注意**：
- E2 候选库按领域取 2–5 个即可；命中过多（单库返回超限）时收窄库范围或换更精确关键词（见 SOP 异常表）。
- 订阅库为只读（can_add_knowledge=false），仅检索引用；写入（import_urls / add_knowledge）仅限自己的库。
- 无「新建知识库」接口；建库需在 ima 网页/客户端操作。
- **写入仅限公开级内容**：docs/、templates/、脱敏经验与词库；report.md 须用户逐篇确认；gathered 素材、plan.md、问题原文禁止写入（见 `docs/IMA_INTEGRATION.md` 隐私分级矩阵）。
- 脚本化（OpenAPI，`tools/ima_*.py`）为可选增强：需在 https://ima.qq.com/agent-interface 生成 Client ID + API Key（存 `~/.config/ima/`，凭证不入项目），当前未实施。

## 领域连接器 — 通道 C 数据源（通达信 / 企查查 / 智慧芽）

**作用**：金融/企业/技术类研究的一手数据源，主代理直执连接器工具（已授权连接）。覆盖：行情/K线/F10 财务（通达信）、企业工商/股东/实控人穿透/财务/上市信息（企查查）、专利/学术论文检索与全文（智慧芽）；**通达信、企查查、智慧芽为通道 C 对应领域必做项（按领域优先级：科技产业/财经时政 P0、学术科研 P1；通达信查行情·财务、企查查锁定企业实体、智慧芽专利+论文各一次调用），finance 插件按需**。

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
- 智慧芽 `patsnap_search` 的 search_strategy 与参数**严格绑定**：含 "semantic" 才传 semantic_query（自然语言技术问题，不是关键词列表）、含 "keyword" 才传 keywords（原子术语 3-8 个，禁句子/公司名）、含 "filter" 才传 filters（申请人/发明人/IPC/日期/法律状态/被引，仅填用户明确字段）；**专利与论文是两个独立调用**（source=patent/paper）；取全文用 `patsnap_fetch`（公开号或 URL，一次 ≤100 条）。**智慧芽为通道 C 对应领域必做项（科技产业/财经时政 P0、学术科研 P1），专利+论文各一次调用，无命中记录"通道 C 智慧芽无有效素材"。**通达信、企查查同为通道 C 对应领域必做项（通达信 code 先 `tdx_lookup_stock`、企查查先 `get_company_by_query` 锁定实体），无命中记录"通道 C [数据源]无有效素材"。
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

## arxiv-watcher + tools/arxiv_search.py — arxiv 平台（归入学术预印本聚合通道 P）

**作用**：arxiv 预印本检索工具（属学术预印本聚合通道 P）——经 ArXiv API 检索最新论文与预印本（未正式发表的 preprint），学术主题与智慧芽（已发表期刊论文）互补；日常推荐用统一入口 `tools/preprint_search.py --platform all`（arxiv + bioRxiv + 浪淘沙 + PSSXiv 一次完成），本工具用于单独检索 arxiv 或 WebFetch 降级路径。

**工具说明：`tools/arxiv_search.py`**（替代 arxiv-watcher 的 shell 脚本）。`arxiv-watcher` 的 `scripts/search_arxiv.sh`（`curl` 实现）在本环境命令行无外网出口下**永远空返回**，不要依赖它；`tools/arxiv_search.py` 用 `urllib` 经 `HTTPS_PROXY` 可联网，但 ArXiv API 对代理 IP 频繁限流（HTTP 429），`--query` 直连不稳定，无命中时优先走 WebFetch 降级（WebFetch 走 WorkBuddy 后端代理，稳定可用）。**curl 自动兜底**：urllib 直连/代理均失败（报"无外网出口"）时，工具自动依次尝试「系统 curl 直连 → curl 经代理」后才降级 WebFetch——curl 独立 SSL 栈在本机实测可用，多数情况无需 agent 手动 WebFetch；降级链完整验证：urllib→代理→curl 直连→curl 代理→WebFetch 提示。**查询语义**：`build_url` 现按相关性排序（`sortBy=relevance`）并把多词查询自动转 AND（`all:w1 AND all:w2`，修复 ArXiv API 空格=OR 导致返回最新无关论文的陷阱）；精确短语用引号。改用 `tools/arxiv_search.py`：

```bash
# 有外网出口的环境：直连
python tools/arxiv_search.py --query "constrained decoding JSON" --count 5 \
    --out research/<slug>/gathered_arxiv.md

# 本环境（无外网出口）：WebFetch 降级路径
python tools/arxiv_search.py --query "constrained decoding JSON" --print-web-prompt
# → 用 agent 的 WebFetch 工具抓取打印出的 URL，把响应保存为 arxiv_raw.txt
python tools/arxiv_search.py --raw arxiv_raw.txt --out research/<slug>/gathered_arxiv.md
```

`--raw` 同时支持 ArXiv 原生 Atom XML 与 WebFetch 用约定 prompt 产出的分隔符文本，解析后落盘 `gathered_arxiv.md`（标题/作者/日期/摘要/链接/PDF）。

**自动登记通道 P**：当 `--out` 写到标准路径 `research/<slug>/gathered_arxiv.md` 时，脚本在写盘后自动把通道 P 登记进 `.progress.json`（`done`/`empty` 按命中条数判定），无需再手动 `mark_channel`。可用 `--slug` 显式指定 slug（否则从输出路径反推）。

**用法**：
- `arxiv-watcher` 技能：`scripts/search_arxiv.sh "<query>"` → 返回 XML（`<entry>/<title>/<summary>/<link title="pdf">`），解析后按 标题/作者/日期/摘要/arxiv 链接/PDF 落盘 `research/<slug>/gathered_arxiv.md`。
- **查询语法（实测）**：ArXiv API 中空格与 `+` 均为 OR 语义（`all:a OR all:b`），精确短语用引号（`search_query=all:%22exact+phrase%22`），多词 AND 用 `all:x+AND+all:y`；脚本传参可直接写引号短语（如 `"formal proof"`）或按上述语法手工构造 URL 用 curl 调用（脚本失败时）。**脚本内建 OR 语义提示**：`--query` 含空格、无引号、无 AND 的多词裸查询会在直连/`--print-web-prompt` 前打印提示（实测 `Riemann zeta zeros critical line proportion` 裸查询返回自动驾驶等无关结果），建议用引号短语或显式 AND。
- 检索词用英文（ArXiv 元数据为英文），2-3 组主题词；零结果换词重试 1 次，仍无记录"通道 P 无有效素材（arxiv）"。
- 需全文时 `web_fetch` PDF 链接提取；`arxiv.org/abs/<id>` 为摘要页、`arxiv.org/pdf/<id>` 为 PDF。

**纪律**：
- 按领域优先级执行（学术科研 P0 / 科技产业 P1 / 财经时政 P2，属通道 P）：学术主题与智慧芽互补；无命中记"通道 P 无有效素材（arxiv）"。
- 与通道 C 智慧芽互补：arxiv 拿最新预印本，智慧芽拿已发表论文+被引；两者交叉验证。
- 讨论/总结过的论文须追加到 `memory/RESEARCH_LOG.md`（arxiv-watcher 技能自带规范，项目内改记 process_notes/gathered 素材即可）。

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

## report_images.py — 报告配图（图文并茂，新增）

**作用**：生成 AI 概念图封面——**正文禁止图表**，量化数据一律用 Markdown 表格承载；AI 概念图**仅作封面 `ai_cover.png` 独立存放、不插入正文**，供发布时作文章封面：

1. **AI 概念图**（Agnes Image 2.1 Flash API，文生图，当前 $0/张）：**仅作封面主视觉**（`ai_cover.png`，不插入正文小节）。端点 `POST https://apihub.agnes-ai.com/v1/images/generations`，模型 `agnes-image-2.1-flash`，size 用 `2K` + ratio（`16:9` 等），`extra_body.response_format: "url"` 返回 `data[0].url`。**注意**：`response_format` 不能放顶层；图生图需 `extra_body.image`。
2. **数据图表**（PIL/Pillow，`--chart-defs` 锚点插入）：**已弃用**——量化数据一律以表格代替，工具保留但不得向新报告插入 chart_*.png。

**用法**：
```bash
AGNES_API_KEY=<key> python tools/report_images.py --slug <slug>          # 全量（AI图+图表）
python tools/report_images.py --slug <slug> --skip-ai                    # 仅数据图表
python tools/report_images.py --slug <slug> --skip-charts                # 仅 AI 概念图
python tools/report_images.py --slug <slug> --chart-defs charts.json     # 自定义图表
python tools/report_images.py --slug <slug> --embed-base64               # 生成图片内嵌单文件 report_embedded.md
python tools/report_images.py --slug <slug> --url-base https://...       # 生成图片 URL 引用版 report_url.md
```

**三种引用模式（按发布场景选择）**：
| 模式 | 生成文件 | 适用场景 | 说明 |
|---|---|---|---|
| 相对路径（默认） | report.md | 本地 Typora/Obsidian | 图片与 md 同目录，仅本地可显示 |
| base64 内嵌 | report_embedded.md | 支持 data URI 的渲染器 | 单文件自包含，代价体积 +33%（图片大时文件可达 10+MB） |
| 公网 URL | report_url.md | **知乎/公众号/在线笔记** | 图片先部署公网静态托管（如 CloudStudio `workbuddy_cloudstudio_deploy`），引用为 https URL；文件仅几十 KB、加载快——**在线应用发布首选** |

**输出与纪律**：
- 图片落盘 `research/<slug>/` **与 report.md 同级**（用户要求图片不放子文件夹，`ai_*.png` + `chart_*.png` 与报告同目录）；report.md 按内容锚点自动插入（不再集中「配图」节，而是插到对应小节标题后、内容前——如斩杀线概念图→2.1 节、单价对比图→测算 1），图片定义带 `anchor` 字段（匹配小节标题关键词）；空行自动规范化；锚点插入幂等（已存在图片跳过，防重复运行重复插入，）。
- **凭证**：API key 用环境变量 `AGNES_API_KEY` 传入，**不写入脚本/项目文件/日志**（同 ima 凭证纪律）。
- **前置**：数据图表用 PIL（Pillow），Python 标准库环境即可，**无需 matplotlib/venv**（用户要求弃用 matplotlib，减少环境依赖）；中文字体自动探测微软雅黑/SimHei/Noto CJK。
- **flomo 上传**为文本版（当前 MCP 无图片参数；flomo 平台本身支持图片——官方 URL Scheme `image_urls` 最多 9 张、需 PRO，未来可走 webhook 带图），图片 URL 以 alt（url）形式保留在文本中供可追溯。
- 中文字体：自动选 Noto Sans CJK / 微软雅黑 / SimHei，图表无乱码。

**AI 概念图硬性禁元素**：封面/题图必须为纯抽象视觉，严禁出现以下任何具象元素——
1. 任何语言文字（汉字/英文/数字/字符/符号/logo/水印）
2. 任何徽章与国徽（国徽/国旗/警徽/军徽/校徽/企业徽/盾牌纹章/奖章/勋章/带图案的圆形或盾形徽标）
3. 任何政府/司法/宗教建筑（人民大会堂/政府大楼/法院/议会/教堂/寺庙/可识别地标建筑）
4. 任何货币与票据（钞票/硬币/债券/纸币/票据/发票/彩票/价格标签/收据）
5. 任何真实人脸与肖像
6. 任何特定国家/政治符号（国旗/政党标志/政治标语）

**实测踩坑**：原封面出现中国国徽（门楣）+飘字票据（"325"/"50"等数字+纸张），用户严令禁止。修复方式——
- **`call_agnes` 末尾自动追加 `_AI_IMAGE_NEGATIVE_GUARD` 通用禁词句**（含 "no text, no characters, no letters, no numbers, no logo, no national emblem, no banknote..." 全套英文 negative），确保所有 `--ai-prompts` 默认遵守。具体 prompt 不必重复写 negative，工具会自动附加。
- **生成后必须肉眼复检**（重点扫门楣/中央/边缘的圆形徽标与飘字票据）。工具层面的 prompt 防御不替代人工复检——实测 Agnes 仍偶有不合规输出，发现违规立刻 `rm <path>` 删除原图、用更强 negative prompt 重生成，**不要为了凑数保留违规图**。
- `process_notes.md` 同步记录"封面图合规复检"结果。完整检查清单见 `docs/CHECKLIST.md` AI 概念图合规复检项。

**AI 概念图主题相关性**：封面/题图除合规外，**必须紧扣问题主题**——视觉应能映射问题的核心概念。**禁止使用与问题无关的纯装饰抽象图**（如"金色球体+棱柱"的通用科幻视觉，看似合规但读者看不出主题）。
- **写 prompt 流程**：①提炼 2-3 个核心视觉符号（如 LOF 退市→"溢价泡沫=发光气泡群/退市闸口=几何门框/按净值赎回=规整立方体阵列"）；②围绕这些符号构造抽象叙事场景（左→中→右的视觉过渡即可直观映射问题逻辑）；③用 `--ai-prompts` 自定义 JSON 文件传入。
- **DEFAULT_AI_PROMPTS 旧模板弃用**：默认模板（"斩杀线"/"双档定价"等）是历史 slug 留下的固化提示，对新主题往往无关——新研究一律用 `--ai-prompts` 自定义 prompt 覆盖，不要复用默认模板。
- **自检**：不看标题，读者能否从图中识别本报告主题？答否则必须重做；`process_notes.md` 同步记录"封面图主题相关性复检"与核心视觉符号的映射说明。

**AI 概念图构图饱满**：封面/题图**禁止大面积空白/留白**——prompt 不得写"左下角留白适合叠加标题"等留白引导（标题由知乎发布时叠加，图内不留白）；画面构图必须饱满、平衡，视觉元素均匀铺满整个画布，边角不留白。`_AI_IMAGE_NEGATIVE_GUARD` 已含 "no large empty areas, no blank corners, no white space reserved for text overlay"；自定义 prompt 也不再写留白引导。复检时同步检查四角/边缘是否有大块均匀空白（可用 PIL 网格扫描：16×9 块，avg>200 且 stdev<6 即留白嫌疑）。

## 降级方案

`research_subagent` 配置的模型不可用（"Model not found"），**主代理直执是当前默认方式**（非降级）：web_search / web_fetch 均由主代理调用，公众号检索走上述包装工具。已实测可行（两份研究均以此完成）。若子代理配置修复，可升级回并行分派。

## flomo 单条完整版上传（tools/flomo_upload_full.py，已弃用）

- 用途：历史流程中把 `research/<slug>/flomo_full.md` 全文作为**单条 memo** 上传 flomo。
- **报告与索引禁止上传 flomo**——本工具对常规研究已弃用（上传走 `note_upload.py` 模块化笔记逐条质检上传）；仅当用户明确要求回传某篇历史报告时才使用。
- 背景：客户端工具调度层（DeferExecuteTool）对超长 content（>~2KB）间歇性假报 `toolName is required`（请求未到达代理层，elapsed 0ms 本地拦截）；flomo MCP 服务端本身支持长文（历史 4000-6500 字正常）。本脚本按 MCP streamable-http 协议直连 flomo 端点，绕过该拦截。
- 用法：`python tools/flomo_upload_full.py --slug <slug>`；成功后自动把 `<!-- flomo id: ... -->` 注释写入 flomo_full.md 首行。
- 注意：凭证优先从环境变量 `FLOMO_TOKEN` 读取（Windows 用户环境变量已持久化，`setx FLOMO_TOKEN <token>` 可更新；token 格式 `fmcp_...`），未设置时兜底读 `~/.workbuddy/mcp.json`；不落盘、不打日志。flomo MCP 参数速查：`memo_search` 用 `keywords`（非 query），`memo_batch_get` 用 `ids`。
