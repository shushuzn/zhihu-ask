# 项目内工具说明

解决开发环境中命令行中文参数乱码、外部脚本路径耦合等问题。所有工具放在 `tools/`。

## init_research.py — 研究目录初始化

**作用**：一键创建新研究，避免手动复制模板。自动完成：创建 `research/<slug>/` 目录 → 从模板生成 plan/report/process_notes 三个文件 → 填入问题标题/日期/领域 → 在 `plan.md` 问题索引表登记一行。

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
- 生成文件保留未填占位符（主概念/关键词等），按 SOP 阶段 0–1 在 `plan.md` 中补齐。

## research_start.py — 一键研究启动器

**作用**：把「启动一次知乎问题研究」压缩为一条命令，并落地 SOP 附录 A 的执行级逻辑。自动完成：配置校验（question/slug 必填、关键词下限提示）→ 初始化研究目录（阶段 0）→ 公众号检索并落盘素材库 `research/<slug>/gathered_wechat.md`（阶段 1 通道 A）→ 知乎官方检索并落盘素材库 `research/<slug>/gathered_zhihu.md`（阶段 1 通道 Z，可选）→ 素材库非空校验 → 记录阶段进度 `.progress.json` → 打印后续步骤（阶段 2-4 上下文）。

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
  "zhihu_keywords": ["主题词 高赞", "主题词 争议"],
  "zhihu_mode": "zhihu",
  "days": 30,
  "min_keywords": 6
}
```

**注意**：keywords 为公众号检索关键词组，zhihu_keywords 为知乎官方检索关键词组（可选，通道 Z；需 zhihu-cli 已安装且 Access Secret 已配置，未配置时自动跳过不阻塞），zhihu_mode 为通道 Z 检索方式（zhihu 站内 / global 全网 / both 两者，both 时分别落盘 `gathered_zhihu.md` 与 `gathered_zhihu_global.md`），days 为时间范围（天，默认 365），min_keywords 为关键词下限（默认 6，不足时提示但不阻塞）。脚本做「阶段 0 初始化 + 阶段 1 通道 A/Z」，产出素材库后按 SOP 附录 A 进入阶段 2。

## iter_research.py — 多轮迭代研究

**作用**：把"单轮研究"升级为"多轮迭代"。每完成一轮，生成下一轮问题清单模板（写 round_notes.md，历史轮次自动归档为 `round_notes_r<N>.md` 保留迭代轨迹）并更新 `.progress.json` 的 round 记录。问题清单由主代理人工编写——阅读报告中标注"仍无法核实/推算"的内容与数据口径缺口，逐条整理成明确、可执行的问题；不用自动提取（机械拆句语义不清）。逐轮深化，领域最低轮次见 SOP A.8（财政/宏观/金融 ≥10 轮，其他 ≥3 轮）。

**用法**：

```bash
python tools/iter_research.py --slug <slug>            # 生成下一轮问题清单（当前轮+1）
python tools/iter_research.py --slug <slug> --round 2  # 指定目标轮次
```

**强制多轮流程（至少 3 轮，不询问用户）**：
- 第 1 轮：`research_start.py` 启动 → 阶段 2/3/4 产出 report.md
- 第 2 轮：本工具生成问题清单模板 → 人工填写未尽问题 → 补检索/深化 → 直接在 report.md 上更新
- 第 3 轮：同上，继续深化。至少完成 3 轮该研究才算完成，禁止询问用户是否继续。

**注意**：工具只生成问题清单与更新轮次，不替代主代理的分析写作。报告路径 research/<slug>/report.md；迭代直接在原文件更新，不创建 vN 版本文件。3 轮为下限：3 轮内不得以"已收敛"为由提前停止；3 轮后若问题清单仍有未处理内容必须继续，直到问题清单处理完。报告必须是成品，正文禁止出现"第 N 轮/迭代"等过程性字样。

## quality_check.py — 正文质量自动检查

**作用**：把报告模板/CHECKLIST 中的「去 AI 味 + 立场中立」检查落地为自动扫描。检测立场词（我认为/应该/总之等）、框架词（先说结论/总结一下等）、评价词（太猛/离谱等）、感叹号/反问句、无来源数字（启发式）、参考文献标注（参考文献区链接行不得带"一手/二手/推断"等分级标注，分级只在正文）。

**用法**：

```bash
python tools/quality_check.py --file research/<slug>/report.md
python tools/quality_check.py --file research/<slug>/report.md --verbose
```

**输出**：全部通过退出码 0；检出待确认项退出码 1 并列出位置与命中词。检出项为启发式规则，需人工确认是否真正违规（如"不构成投资建议"中的"建议"为合法用法）。来源特征词含数据分级标注（一手/二手/计算/估算/预算等），带来源括注的列表行与表格行不误报。

**注意**：扫描范围为正文（自动跳过"数据与来源备查"及之后的来源区）；表格行数字不判为无来源。数字溯源与逻辑终审仍需人工复核。

## check_progress.py — 阶段进度校验

**作用**：读取 `research/<slug>/.progress.json`，校验前置阶段是否完成，供阶段 2-4 进入前确认（对应 SOP 附录 A「输出未达校验即阻塞」）。

**用法**：

```bash
python tools/check_progress.py --slug <slug>                      # 展示当前进度
python tools/check_progress.py --slug <slug> --require phase1_done # 校验前置阶段（通过退出码0，阻塞退出码1）
```

**说明**：当前已知阶段键为 `phase1_done`（阶段 0 初始化 + 阶段 1 通道 A 完成）。进入阶段 2 前先跑本工具确认前置就绪。

## wechat_search.py — 微信公众号检索包装

**问题背景**：`wechat-article-search` skill 的 `sogou_search.py` 通过命令行接收中文关键词，但在本机 PowerShell 环境下中文参数会乱码（`chcp 65001` 也无法解决），导致通道 A 无法使用。

**解决方案**：包装脚本从 UTF-8 关键词文件读取检索词，直接在 Python 进程内调用 `sogou_search.py` 的函数，完全绕开命令行传参。

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

**输出**：每个关键词的结果清单（标题/公众号/时间/摘要/链接），UTF-8 编码。

**注意**：
- 关键词文件必须 UTF-8 编码（用 write_to_file 创建即可保证）。
- 冷门关键词搜狗可能补充旧文章，需按返回的 time 字段自行过滤。
- 触发验证码时返回 "触发验证码，请稍后重试"，稍后再试即可。
- 检索词的有效组合可补充至 `docs/KEYWORDS.md`（通用词库），临时关键词文件用完即删。

## zhihu_search.py — 知乎开放平台检索包装（通道 Z）

**问题背景**：zhihu skill（`zhihu-cli`）是本机已安装的知乎官方开放平台 CLI，提供知乎站内搜索（`search zhihu`）、全网搜索（`search global`）、热榜（`hot`）与直答（`answer`）。但 CLI 是 exe，PowerShell 下向 exe 传中文参数同样会乱码。

**解决方案**：包装脚本用 Python `subprocess` 直接以 Unicode 参数调用 `zhihu-cli`，绕开 PowerShell 命令行层。

**前置条件**：
1. zhihu skill 已 setup（CLI 已安装，本机路径 `C:\Users\35234\AppData\Local\ZhihuCLI\current\zhihu-cli.exe`）。
2. Access Secret 已配置：`zhihu-cli auth set --secret-stdin`（通过标准输入传入，不进进程参数）。
3. 未认证时本工具报 `AUTH_REQUIRED` 并提示配置方法，不落盘。

**用法**：

```bash
# 1. 准备配置 tools/zhihu_search.json（UTF-8）
{
  "mode": "zhihu",                    // zhihu | global | hot
  "queries": ["<主题词> 高赞", "<主题词> 争议"],  // zhihu/global 必填
  "count": 10,                        // zhihu:1-10, global:1-20
  "search_db": "all",                 // global 可选: all|realtime|static
  "filter": "host==\"gov.cn\"",       // global 可选: 高级筛选表达式（用于限定权威站点/时间）
  "limit": 20,                        // hot 模式: 1-30
  "output": "research/<slug>/gathered_zhihu.md"
}

# 2. 执行（落盘素材库）
python tools/zhihu_search.py --config tools/zhihu_search.json
```

**输出**：每个关键词的知乎结果清单（标题/作者/赞同/类型/权威等级/链接/摘要），UTF-8 编码，落盘 `gathered_zhihu.md`。

**数据边界（zhihu skill 官方口径）**：热榜只用于发现议题；深度研究必须用 search，不用直答（answer）替代；搜索返回的是摘要与链接，需要原文时用 `web_fetch` 打开 `Url`。

**注意**：配置文件用完即删；检索词有效组合补充至 `docs/KEYWORDS.md`；Access Secret 不写入项目任何文件。

## git_protect.py — 提交前检查

**作用**：提交前检查暂存区，阻止 `plan.md`、`research/`、`.codebuddy/`、`docs/PLAN_v1_ARCHIVE.md`、临时 config 等内部文件被误提交。

**用法**：

```bash
python tools/git_protect.py    # 检查暂存区；发现内部文件则退出码 1 并列出
```

**注意**：内部文件清单见脚本内 `INTERNAL_PATTERNS`，按需增改。已通过 `install_git_hooks.py` 接入 pre-commit hook，提交时自动执行；如需手动校验也可单独运行本脚本。

## install_git_hooks.py — pre-commit hook 安装

**作用**：把 `git_protect.py` 接入 git，使每次 `git commit` 自动执行检查，暂存区含内部文件时阻止提交。

**用法**：

```bash
python tools/install_git_hooks.py          # 安装/更新 hook
python tools/install_git_hooks.py --remove # 移除 hook
```

**注意**：hook 写入 `.git/hooks/`（本地，不入库），重新 clone 后需重跑本脚本。安装后可验证：`git add -f <内部文件>` 后 `git commit` 会被阻止，再 `git reset HEAD <file>` 恢复。

## health_check.py — 项目健康自检

**作用**：一键验证项目就绪状态，适合新会话启动或排障时运行。检查 Python 环境、git 分支/远程/同步状态、pre-commit hook、内部文件是否被跟踪、关键文件完整性。

**用法**：

```bash
python tools/health_check.py
```

**输出**：逐项 `[OK]/[FAIL]`，全部通过退出码 0，有失败项退出码 1。新会话开始时先跑一遍，可快速确认环境是否就绪。

## rag_build.py / rag_search.py — RAG 知识库（检索项目内经验）

**作用**：把公开文档（docs/ + templates/）变成可检索知识库，研究启动前先查项目内已有经验——流程规则、关键词词库、模板结构、写作规范、踩坑沉淀，避免每次研究从零开始。

**用法**：

```bash
python tools/rag_build.py                # 构建索引（改动 docs/ 后需重跑）
python tools/rag_search.py "笔记本 8000 学生"     # BM25 检索，默认前 5 条
python tools/rag_search.py "关键词 回填" -k 10    # 指定条数
python tools/rag_search.py "立场 纯事实" --file docs/STYLE_GUIDE.md  # 限定文件
```

**说明**：零第三方依赖（中文按字符 bigram + 英文按词切分，BM25 打分）；索引为派生缓存，存 `.codebuddy/knowledge/` 仅本地，不进入 git。建议研究流程中在阶段 0/1 前执行一次，把命中片段作为检索起点。

## ima 连接器 — 通道 E（ima 知识内容检索）

**作用**：接入腾讯 ima 知识库（ima.qq.com），在阶段 1 检索历史经验沉淀（跨问题语义召回），与本地 `rag_search.py`（词面匹配）互补。ima 为 RAG 语义检索，可召回措辞不同但语义相关的内容。

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

**检索流程**（对应 SOP 阶段 1 通道 E；**通道 E 为阶段 1 执行顺序第一的检索**，先于 A–D 通道，为关键词与检索起点定基调），两级执行：

1. **E1 经验检索**（检索项目历史沉淀）：`search_knowledge_base "主概念"` 定位相关库 → 对个人库/项目沉淀库 `search_knowledge "主概念 关键实体"` → 命中片段纳入检索起点；无命中记录"E1 无有效素材"。
2. **E2 内容素材检索**（核心，把订阅库变成素材通道）：按问题领域从 `docs/IMA_LIBRARIES.md` 选取候选订阅库（金融/法律/AI/学术/工程等分组，已列库名+ID+内容量）→ 对每个候选库执行 `search_knowledge (knowledge_base_id, query)` → 命中内容落盘素材库。

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

## 领域连接器 — 通道 C 数据源（通达信 / 企查查）

**作用**：金融与企业类研究的一手数据源，主代理直执连接器工具（已授权连接）。覆盖：行情/K线/F10 财务（通达信）、企业工商/股东/实控人穿透/财务/上市信息（企查查）。

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
- 两者均为只读数据源：只做查询引用，不执行交易、不写回任何数据。
- 连接器未连接/返回空时跳过该数据源，改用 Web 或其他插件补位，不阻塞流程（见 SOP 异常表）。

## 降级方案

`research_subagent` 配置的模型不可用（"Model not found"），**主代理直执是当前默认方式**（非降级）：web_search / web_fetch 均由主代理调用，公众号检索走上述包装工具。已实测可行（两份研究均以此完成）。若子代理配置修复，可升级回并行分派。
