# 项目环境约定（跨会话必读）

> 本文件记录本项目所在环境的已知限制与统一做法，任何会话启动涉及工具操作时应先参考。内容来自实际踩坑，随项目持续更新。

## 0. 执行硬限制（跨会话最高约束）

1. **不猜测含糊指令**：「优化 / 精简 / 自动化 / 改进」等词，先给出具体改动清单、影响面与可回滚性，经用户确认后执行。
2. **不碰既定规则**：凭证读取方式（只从环境变量）、通道登记方式（F 人工判读登记 / A、B、P 落盘自动登记 / E、C 环境级 skip）、文档结构、报告红线（纯事实陈述、禁过程性标注、缺口只落 process_notes 与索引笔记）——照做，不加个人"改进"。
3. **不私自加兜底 / 自动化**：任何降级链、兜底、自动登记，先论证必要性并征得确认。
4. **改错立即回滚**：判断错误当场还原，不留尾巴。
5. **研究严格走 SOP 六通道 + 门禁**：门禁报错先人工判读——真违规修内容，工具误报改工具（先给改动清单与影响面，经确认后执行）；禁止任何"凑过"行为：为消除命中而改正文塞词、删引用、`--force` 跳过质检，均属绕过门禁。

## 1. PowerShell 中文乱码（最高优先级）

**现象**：本机 PowerShell（Windows）向任何命令行工具传中文参数都会乱码（git commit / gh repo create / python 脚本参数均中招），`chcp 65001` 无效。

**统一做法：中文参数一律通过 UTF-8 文件传入，不在命令行直接写中文。**

```powershell
# 反例（会乱码）
git commit -m "feat: 新增功能"

# 正例（先写 UTF-8 文件，再 -F 传入）
# 用 write_to_file 创建 .commit_msg.tmp（UTF-8）
git commit -F .commit_msg.tmp
del .commit_msg.tmp

# gh 描述同理：先写 UTF-8 文件，PowerShell 内读入变量
$desc = (Get-Content .desc.tmp.txt -Raw -Encoding UTF8).Trim()
gh repo edit shushuzn/zhihu-ask --description $desc
```

## 2. 命令行工具限制与降级

| 工具 | 状态 | 说明 |
|---|---|---|
| `research_subagent` | 不可用（默认） | 模型 "claude-haiku-4.5" not found；当前研究一律由主代理直执（已实测可行） |
| 知乎网页/API | 不可用 | 未登录访问返回 403，需用户粘贴问题内容 |
| `wechat-article-search` skill 脚本 | 中文参数乱码 | 使用 `tools/wechat_search.py` 包装（文件传参） |
| `research_start.py` | 可用 | 一键启动研究（初始化+公众号检索+素材库落盘）；新会话先跑 `python tools/health_check.py` 自检 |

## 2.5 命令行外网出口

本环境外网出口存在**工具差异**，任何需要联网的脚本都必须据此选择实现方式：

| 方式 | 出口状态 | 说明 |
|---|---|---|
| 命令行 `curl` / `wget` / arxiv-watcher 的 `search_arxiv.sh` | **无出口（返回 HTTP 200 但空响应，SIZE=0）** | 即使放开沙箱、即使走 `HTTPS_PROXY` 也拿不到正文；shell 版 arxiv 检索脚本**永远空返回**，不要依赖。 |
| Python `urllib` / `requests` / `pip` | **有出口（走 `HTTPS_PROXY=http://127.0.0.1:7897/`）** | `pip install` 可联网；`report_to_docx.py` 的 venv 自动装包可用。但 **ArXiv API 对代理 IP 频繁返回 429 限流**，`arxiv_search.py` 直连常失败并自动降级到 WebFetch——不要假定 arxiv 直连必成功。 |
| agent 的 WebFetch / WebSearch 工具 | **有出口（走 WorkBuddy 后端代理）** | 不依赖本机网络栈，任何环境均可联网；是 shell 无网时的兜底抓取手段。 |

**统一做法**：
- 需要外网抓取时，**优先用 Python 工具**（`tools/arxiv_search.py` 等），不要用 curl/shell 脚本。
- **反爬 403 ≠ 死链**：百度百科/知乎等站点对 urllib/curl 非浏览器 UA 常返回 403（甚至浏览器 UA 也拒），页面本身存在。引用核验（`check_citation_validity.py`）已实现 403/000 自动 WebFetch 降级复核；正文抓取优先 `tools/web_fetch.py`（Jina Reader 代理，实测可绕过百度/知乎反爬）。
- **ArXiv 检索**：本机 urllib 有出口，但 ArXiv API 对代理 IP 频繁 429 限流，直连常失败。`tools/arxiv_search.py` 直连失败会自动打印 WebFetch prompt 并退出码 2——**实践中直接走 WebFetch 降级更稳**：`tools/arxiv_search.py --query "<q>" --print-web-prompt` → 用 WebFetch 抓取并保存为 `research/<slug>/arxiv_raw.txt` → `tools/arxiv_search.py --raw research/<slug>/arxiv_raw.txt --out research/<slug>/gathered_arxiv.md`。（WebFetch 走 WorkBuddy 后端代理，不受本机限流影响。）
- 外网动作前用 `tools/net_check.py` 探测出口，缺失时打印清晰提示、避免静默失败（已实现于 `report_to_docx.py` 的图片下载分支）。
- `report_images.py --url-base` 的图床部署、`report_to_docx.py` 的远程图片下载等 urllib 动作在本机可联网；但换机若无代理会失败，须以 net_check 兜底。

## 3. 数据与文件规范

- 所有项目文档、检索文件、临时文件一律 UTF-8 编码（write_to_file 默认即可）。
- 临时文件（commit 消息、描述、keywords.json）用完即删，不提交入库。
- `.codebuddy/` 为本地数据目录，已在 `.gitignore` 排除，不要删除。

## 3.5 提交管理规范

- `git add -A` 前先 `git status` 确认无多余文件被暂存。
- 提交时 pre-commit hook 自动运行 `tools/git_protect.py` 检查暂存区（见 `docs/TOOLS.md`）；hook 未被安装时手动运行 `python tools/git_protect.py` 校验。
- 若发现内容被误推，立即处理：`git rm --cached <文件>` + 更新 `.gitignore` + 提交修正；若已在历史提交中，用 `git filter-repo` 重写历史。
- 禁止未经用户确认直接 `git push` 或 `gh repo create`；创建仓库、改可见性、强推等操作必须先获得用户明确同意。
- **改进类提交默认直接推送（不询问）**：项目改进（docs/tools/skills 等公开文件）完成后，经 `git_protect` 校验后直接 commit + push，无需等待用户指示；研究产出（`research/`）按约定仅存本地、永不入库。

## 4. git / GitHub 约定

- 仓库：`shushuzn/zhihu-ask`（public），远程名 `origin`，默认分支 `main`。
- 本地 git 未配置全局 user 身份，提交时用 `-c` 临时指定（不改全局配置）：
  ```
  git -c user.name="shushuzn" -c user.email="132275809+shushuzn@users.noreply.github.com" commit ...
  ```
- 提交信息用 UTF-8 文件 + `-F` 传入（见第 1 条）。
- **禁止任何 force 参数**：不用 `git push --force`/`-f`，也不用 PowerShell 的 `-Force`（如 `Remove-Item -Force`）；删除文件用 `del`，覆盖暂存用普通命令。
- 推送一律用干净命令 `git push origin main`。

### 4.1 git 实操踩坑

- **`git add` 显式列出被忽略文件会整体失败**（如 `docs/KEYWORDS.md`、`plan.md`）——内部文件本就不提交，`git add` 只列公开文件。
- **commit 后核验实际内容**：`git show --stat HEAD` 与 commit 输出对照，`git status --short` 复查到工作区干净才结束（曾出现提交只含部分文件）。
- **PowerShell 将 git stderr 进度当错误**：`git push` 进度（"To github.com:..."）走 stderr，PowerShell 合并 2>&1 后显示 NativeCommandError 并报 `[exit code: 1]`，但提交实际成功。判定以输出中的 `分支范围  main -> main` 行为准，勿因红色错误信息误判失败重推。

## 5. 提交规范

- 功能类：`feat: 一句话说明`；修复类：`fix: ...`；文档类：`docs: ...`；工具类：`chore/tool: ...`。
- 提交前检查：临时文件已清理、`git status` 无多余文件、`.codebuddy/` 未入库。

## 6. ima 知识库使用约定（通道 E）

- **连接状态**：ima 连接器（ima-mcp）经 WorkBuddy 侧边栏「更多 → ima知识库」OAuth 授权；连接器管理页显示 connected 即可用。未连接时通道 E 由初始化**环境级自动登记 skip**（跨研究共享，无需逐篇手动检查）；连接器接入后设 `ZHIHU_ASK_UNCONFIGURED_CHANNELS`（如 `"C"`）或置空（全部已配置）恢复手动登记。
- **检索**：主代理直执连接器工具（`search_knowledge_base` 搜库 / `search_knowledge` 库内检索），与本地 `rag_search.py`（SQLite BM25）互补；ima 无 CLI，不涉及乱码问题。
- **凭证**：连接器方案无需凭证。脚本化（OpenAPI）才需 Client ID + API Key（https://ima.qq.com/agent-interface 生成，仅显示一次），存 `~/.config/ima/` 或环境变量；**凭证不入项目文件、不入日志**，泄露后引导在 agent-interface 撤销重建。
- **flomo MCP Token**：`FLOMO_MCP_TOKEN` **只从环境变量读取**（tools/flomo_search.py 与 note_upload.py 读 `os.environ`，不读 `.env`）。曾硬编码在 flomo_search.py 并进入公开仓库——**须在 flomo 后台撤销旧 token 重建**，新 token 只放环境变量，绝不写入代码/文档/日志。
- **隐私边界（写入硬性管控）**：读取无限制；写入（import_urls / add_knowledge）仅限公开级内容——docs/、templates/、脱敏经验与词库；已定稿 report.md 须用户逐篇确认；gathered 素材、plan.md、问题原文禁止写入。ima 为云服务，与「research/ 仅存本地」红线冲突的内容一律不上云。
- **参考**：能力盘点与分级矩阵见 `docs/IMA_INTEGRATION.md`。

## 7. 领域连接器约定（通道 C：通达信 / 企查查 / 智慧芽）

- **连接状态**：通达信（tdx-connector）、企查查（qcc-company）、智慧芽（patsnap-search）经 WorkBuddy 连接器授权（连接器管理页 connected 即可用），**三者均为通道 C 必做项**（无论问题主题均须执行，含人文/经典类）；未连接或调用失败时须记录"通道 C [数据源]未执行"告警并提示用户连接、改用 Web/其余通道补位，不得静默跳过——但**本环境 C 连接器未配置属环境级常态：由初始化自动登记 skip（`tools/channel_state.py` 环境级机制），无需逐篇手动检查**；连接器接入后自动失效并恢复手动登记；finance 插件为按需通道，未连接时跳过不阻塞。
- **只读原则**：均为只读数据源，仅查询引用，不执行交易、不写回数据。
- **通达信纪律**：`tdx_quotes`/`tdx_api_data` 的 code 只接受纯数字，中文名必须先 `tdx_lookup_stock` 查码（期货传 range="QH"、期权传 range="QQ"）；code 与 setcode 必须匹配；接口返回空结果时如实报告"该数据暂无"，禁止用训练数据填充行情/财务数字。
- **企查查纪律**：先用 `get_company_by_query` 锁定实体；返回多候选时必须把候选列表完整展示给用户、等用户确认后再调下游工具，自动选第一条属错误操作；穿透类结果（实控人持股/受益股份/财务比率）为服务端精算终值，逐字引用，禁止自乘重算或臆测中间层主体（实际算错案例：79.8674%×11.5446% 曾被算成 9.2145%，正确 9.2204%）。
- **智慧芽纪律**：`patsnap_search` 的 search_strategy 与参数严格绑定——含 "semantic" 才传 semantic_query（自然语言技术问题，非关键词列表）、含 "keyword" 才传 keywords（原子术语 3-8 个，禁句子/公司名）、含 "filter" 才传 filters（结构化约束：申请人/发明人/IPC/日期/法律状态/被引，仅填用户明确字段）；专利与论文是两个独立调用（source=patent/paper）；返回文档含 标题/申请人/发明人/IPC/法律状态/日期/被引/URL，取全文用 `patsnap_fetch`（公开号或 URL，一次 ≤100 条）。**智慧芽为通道 C 对应领域必做项（科技产业/财经时政 P0、学术科研 P1），专利与论文各一次调用，无命中如实记录"通道 C 智慧芽无有效素材"。**通达信、企查查同为通道 C 对应领域必做项（通达信 code 先 `tdx_lookup_stock`、企查查先 `get_company_by_query` 锁定实体），无命中记录"通道 C [数据源]无有效素材"。
- **凭证/额度**：无需项目内凭证（连接器托管授权）；企查查查询有账号额度限制，批量尽调前控制查询次数。
- **用法**：工具表与调用示例见 `docs/TOOLS.md`「领域连接器」章节。

## 8. 执行纪律

- **初始化必传 --domain**：`init_research.py` 初始化研究时显式传 `--domain "领域 / 二级"`（如 `--domain "产业经济 / 制造业 / 国际经贸"`）；不传则 plan 索引领域为「其他」、后续须手动 sed 修正（今日 6+ 次踩坑）。未传时工具已打印警告。
- **DeferExecuteTool 调用格式**：`toolName` 为顶层参数、`params` 只放目标工具参数——禁止把 `toolName` 写进 `params` 内部（今日 4 次报 "toolName is required"）。例：`DeferExecuteTool({toolName: "mcp__flomo__memo_create", params: {content: "..."}})`。
- **编辑报告小节后立即质检**：编辑小节后立即跑 `python tools/quality_check.py --file research/<slug>/report.md`——小点须叙述化（bullet 单行会被拦截）、段落 ≤4-5 行，先查再继续，避免积压多处在收尾时集中修。
- **结论先留余量**：结论按 ≤300 字上限写时先压到 280 左右再补充事实，避免反复删减。
- **参考文献链接必须与条目一一对应**：写参考文献时禁止用论文自身链接占位代替背景文献（如把 König 的 M₂₃ 辫群轨道论文、ACT DR6 的 α-Starobinsky 论文、RLSVR 的背景文献全部写成 arXiv:2608.08538 / 2608.06071 / 2607.23802）。背景文献的真实链接须从 `gathered_arxiv.md` 的「标题→链接」映射表逐条取用（该表由 arxiv_search 落盘，标题与链接一一对应）；宁缺勿错——找不到对应链接的条目删掉，不写伪链接。
- **AI 概念图合规复检**：封面/题图必须为**纯抽象视觉**——严禁语言文字、徽章/国徽、政府/司法/宗教建筑、货币票据、真实人脸、国家/政治符号。`report_images.py` 的 `call_agnes` 自动追加 `_AI_IMAGE_NEGATIVE_GUARD` 禁词句，但**不替代人工复检**（实测偶有不合规输出，如国徽+飘字票据）；生成后肉眼逐图扫（重点：圆形徽标/飘字票据），违规即删图重生成，不保留凑数图；`process_notes.md` 记录"封面图合规复检"。
- **AI 概念图主题相关性**：封面**必须紧扣问题主题**，禁止与问题无关的纯装饰抽象图（如"金色球体+棱柱"通用科幻视觉）。写 prompt 先提炼 2-3 个核心视觉符号（如 LOF 退市→挤溢价泡沫+退市闸口+按净值赎回），围绕符号构造抽象叙事场景；不复用通用 DEFAULT_AI_PROMPTS，用 `--ai-prompts` 自定义当前主题专用 prompt。自检：不看标题能否识别主题？答否则重做；`process_notes.md` 记录"封面图主题相关性复检"与符号映射。
- **AI 概念图构图饱满**：封面**禁止大面积留白**——prompt 不得写"左下角留白适合叠加标题"等引导；构图饱满平衡、元素铺满画布、边角不留白（`_AI_IMAGE_NEGATIVE_GUARD` 已含禁留白句）。复检时同步检查四角/边缘是否大块空白。
- **写作前置：先读门禁规则再起草**（probabilistic-deterministic-systems 教训：报告第一版 13 处破折号/「但」命中、笔记 4 处「不是…而是」「其一/其二/我们」命中，全部可在起草时规避）：写报告/笔记前先读 `tools/check_ai_voice.py` 的 HARD_PATTERNS / WARN_PATTERNS / 破折号规则与 `tools/quality_check.py` 的 STANCE_WORDS / FRAMEWORK_WORDS / AI 转折句式 / 段落长度规则；草稿完成先跑单工具（`--file`/`--slug`），全绿再走收尾八件套，禁止写完直接收尾积压批量命中。
- **门禁命中处理顺序：判读 → 分流 → 留痕**：任何门禁命中先逐条人工判读（真违规 / 词面差异误报 / 反爬误报 / 结构误报），再决定动作——真违规改内容（如 AI 腔句式改直述，语义无损）；工具误报改工具（如 check_citation_validity 的 403 WebFetch 降级复核、`--ack` 人工确认机制），改动清单先给用户确认；`--ack` 放行必须逐条说明判读理由并在门禁输出中留痕。禁止未判读直接改正文、禁止为过门禁改正文塞词。
- **改算法先验证假设**：任何正则/匹配逻辑改动（如切词、窗口、阈值），先写最小复现脚本验证行为假设（findall 消费式 vs 滑窗、窗口覆盖长度等），再改工具代码；改完补单测，单测全绿再跑全量回归，最后收尾——收尾八件套只跑一次。

## 参考文献学术纪律

- **核验失败 ≠ 核验通过**：`check_citation_validity.py` 联网核验（CrossRef/arXiv）失败时默认硬伤阻断——禁止"网络不好就算了"式放行；网络恢复后重跑，或显式 `--offline` 声明放弃核验（输出注明"离线模式"）。
- **佚名必须真佚名**：GB/T 规则"无作者才写佚名"——注册库（CrossRef/arXiv）有作者却著录"佚名" = 作者误用（硬伤）。引用前先查注册库作者，有作者写真实作者。
- **引用日期须晚于/等于发布日期**：著录引用日期 < 注册库发布日期 = 硬伤。
- **引用 URL 须可溯源**：普通 URL 死链（404/5xx）= 硬伤；DOI/arxiv 链接必须能解析到注册记录。
- **作者必须真实**：著录作者与 CrossRef/arXiv 注册作者比对（前 3 位、忽略大小写与顺序）；编造作者 = 硬伤（"Li Y" 事件教训）。
- **题名必须与注册一致**：著录题名与注册题名规范化比对（连字符/破折号变体已归一化）；张冠李戴 = 硬伤。
- **正文引用须与文献内容对应**：引用处上下文与题名关键词匹配（提示级启发式，人工复核）。
- **DOI 可含括号**（Elsevier 格式如 `10.1016/0167-2789(93)90178-4`）；引用日期紧邻 URL 不误吞。
- **报告（交付物）必须联网核验**：`check_all.py` 全库体检「违规引」列联网执行；笔记上传链（note_upload）用 `--offline` 只拦离线可判项，完整核验在报告质检阶段。
