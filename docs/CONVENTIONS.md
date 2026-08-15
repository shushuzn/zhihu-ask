# 项目环境约定（跨会话必读）

> 本文件记录本项目所在环境的已知限制与统一做法，任何会话启动涉及工具操作时应先参考。内容来自实际踩坑，随项目持续更新。

## 1. PowerShell 中文乱码（最高优先级）

**现象**：本机 PowerShell（Windows）向任何命令行工具传递中文参数都会乱码，包括：

- `git commit -m "中文消息"` → 报错或乱码
- `gh repo create --description "中文"` → 仓库描述乱码
- `python scripts/sogou_search.py "中文关键词"` → 乱码
- `chcp 65001` 无法解决此问题

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

- **`git add` 混合被忽略路径会整体失败**：一次 `git add` 中只要显式列出被 `.gitignore` 忽略的内部文件（如 `docs/KEYWORDS.md`、`plan.md`），整条命令报错退出、**任何文件都不会暂存**（随后 commit 报 "nothing to commit, working tree clean"，极易误判）。正确做法：内部文件回填后本就不提交（KEYWORDS.md 是 SQLite 关键词库的导出物、plan.md 仅本地），`git add` 只列公开文件。
- **commit 后必须核验实际提交内容**：commit 输出行数与 `git show --stat HEAD` 对照，剩余改动以 `git status --short` 复查，直到工作区干净才可结束；曾出现提交只含部分文件（docstring 1 行）而其余改动滞留工作区的情况。
- **PowerShell 将 git stderr 进度当错误**：`git push` 进度（"To github.com:..."）走 stderr，PowerShell 合并 2>&1 后显示 NativeCommandError 并报 `[exit code: 1]`，但提交实际成功。判定以输出中的 `分支范围  main -> main` 行为准，勿因红色错误信息误判失败重推。

## 5. 提交规范

- 功能类：`feat: 一句话说明`；修复类：`fix: ...`；文档类：`docs: ...`；工具类：`chore/tool: ...`。
- 提交前检查：临时文件已清理、`git status` 无多余文件、`.codebuddy/` 未入库。

## 6. ima 知识库使用约定（通道 E）

- **连接状态**：ima 连接器（ima-mcp）经 WorkBuddy 侧边栏「更多 → ima知识库」OAuth 授权；连接器管理页显示 connected 即可用。未连接时通道 E 由初始化**环境级自动登记 skip**（跨研究共享，无需逐篇手动检查）；连接器接入后设 `ZHIHU_ASK_UNCONFIGURED_CHANNELS`（如 `"C"`）或置空（全部已配置）恢复手动登记。
- **检索**：主代理直执连接器工具（`search_knowledge_base` 搜库 / `search_knowledge` 库内检索），与本地 `rag_search.py`（SQLite BM25）互补；ima 无 CLI，不涉及乱码问题。
- **凭证**：连接器方案无需凭证。脚本化（OpenAPI）才需 Client ID + API Key（https://ima.qq.com/agent-interface 生成，仅显示一次），存 `~/.config/ima/` 或环境变量；**凭证不入项目文件、不入日志**，泄露后引导在 agent-interface 撤销重建。
- **flomo MCP Token**：`FLOMO_MCP_TOKEN` 从**环境变量**读取（优先真实环境变量，其次项目根 `.env` 兜底——沙箱下 `setx` 被拒的既有做法，见 `tools/env_loader.py`；tools/flomo_search.py 与 note_upload.py 启动时加载）。曾硬编码在 flomo_search.py 并进入公开仓库——**须在 flomo 后台撤销旧 token 重建**，新 token 只放环境变量/`.env`，绝不写入代码/文档/日志。
- **隐私边界（写入硬性管控）**：读取无限制；写入（import_urls / add_knowledge）仅限公开级内容——docs/、templates/、脱敏经验与词库；已定稿 report.md 须用户逐篇确认；gathered 素材、plan.md、问题原文禁止写入。ima 为云服务，与「research/ 仅存本地」红线冲突的内容一律不上云。
- **参考**：能力盘点与分级矩阵见 `docs/IMA_INTEGRATION.md`。

## 7. 领域连接器约定（通道 C：通达信 / 企查查 / 智慧芽）

- **连接状态**：通达信（tdx-connector）、企查查（qcc-company）、智慧芽（patsnap-search）经 WorkBuddy 连接器授权（连接器管理页 connected 即可用），**三者均为通道 C 必做项**（无论问题主题均须执行，含人文/经典类）；未连接或调用失败时须记录"通道 C [数据源]未执行"告警并提示用户连接、改用 Web/其余通道补位，不得静默跳过——但**本环境 C 连接器未配置属环境级常态：由初始化自动登记 skip（`tools/channel_state.py` 环境级机制），无需逐篇手动检查**；连接器接入后自动失效并恢复手动登记；finance 插件为按需通道，未连接时跳过不阻塞。
- **只读原则**：均为只读数据源，仅查询引用，不执行交易、不写回数据。
- **通达信纪律**：`tdx_quotes`/`tdx_api_data` 的 code 只接受纯数字，中文名必须先 `tdx_lookup_stock` 查码（期货传 range="QH"、期权传 range="QQ"）；code 与 setcode 必须匹配；接口返回空结果时如实报告"该数据暂无"，禁止用训练数据填充行情/财务数字。
- **企查查纪律**：先用 `get_company_by_query` 锁定实体；返回多候选时必须把候选列表完整展示给用户、等用户确认后再调下游工具，自动选第一条属错误操作；穿透类结果（实控人持股/受益股份/财务比率）为服务端精算终值，逐字引用，禁止自乘重算或臆测中间层主体（实测算错案例：79.8674%×11.5446% 曾被算成 9.2145%，正确 9.2204%）。
- **智慧芽纪律**：`patsnap_search` 的 search_strategy 与参数严格绑定——含 "semantic" 才传 semantic_query（自然语言技术问题，非关键词列表）、含 "keyword" 才传 keywords（原子术语 3-8 个，禁句子/公司名）、含 "filter" 才传 filters（结构化约束：申请人/发明人/IPC/日期/法律状态/被引，仅填用户明确字段）；专利与论文是两个独立调用（source=patent/paper）；返回文档含 标题/申请人/发明人/IPC/法律状态/日期/被引/URL，取全文用 `patsnap_fetch`（公开号或 URL，一次 ≤100 条）。**智慧芽为通道 C 对应领域必做项（科技产业/财经时政 P0、学术科研 P1），专利与论文各一次调用，无命中如实记录"通道 C 智慧芽无有效素材"。**通达信、企查查同为通道 C 对应领域必做项（通达信 code 先 `tdx_lookup_stock`、企查查先 `get_company_by_query` 锁定实体），无命中记录"通道 C [数据源]无有效素材"。
- **凭证/额度**：无需项目内凭证（连接器托管授权）；企查查查询有账号额度限制，批量尽调前控制查询次数。
- **用法**：工具表与调用示例见 `docs/TOOLS.md`「领域连接器」章节。

## 8. 执行纪律

- **初始化必传 --domain**：`init_research.py` 初始化研究时显式传 `--domain "领域 / 二级"`（如 `--domain "产业经济 / 制造业 / 国际经贸"`）；不传则 plan 索引领域为「其他」、后续须手动 sed 修正（今日 6+ 次踩坑）。未传时工具已打印警告。
- **DeferExecuteTool 调用格式**：`toolName` 为顶层参数、`params` 只放目标工具参数——禁止把 `toolName` 写进 `params` 内部（今日 4 次报 "toolName is required"）。例：`DeferExecuteTool({toolName: "mcp__flomo__memo_create", params: {content: "..."}})`。
- **编辑报告小节后立即质检**：编辑小节后立即跑 `python tools/quality_check.py --file research/<slug>/report.md`——小点须叙述化（bullet 单行会被拦截）、段落 ≤4-5 行，先查再继续，避免积压多处在收尾时集中修。
- **结论先留余量**：结论按 ≤300 字上限写时先压到 280 左右再补充事实，避免反复删减。
- **参考文献链接必须与条目一一对应**：写参考文献时禁止用论文自身链接占位代替背景文献（如把 König 的 M₂₃ 辫群轨道论文、ACT DR6 的 α-Starobinsky 论文、RLSVR 的背景文献全部写成 arXiv:2608.08538 / 2608.06071 / 2607.23802）。背景文献的真实链接须从 `gathered_arxiv.md` 的「标题→链接」映射表逐条取用（该表由 arxiv_search 落盘，标题与链接一一对应）；宁缺勿错——找不到对应链接的条目删掉，不写伪链接。
- **AI 概念图合规复检**：每张 `ai_*.png` 封面/题图必须为**纯抽象视觉**——严禁任何语言文字、徽章与国徽、政府/司法/宗教建筑、货币与票据、真实人脸与肖像、国家/政治符号。`tools/report_images.py` 的 `call_agnes` 末尾自动追加 `_AI_IMAGE_NEGATIVE_GUARD` 通用禁词句（no text / no emblem / no banknote / no government building 等全套英文 negative）确保所有 `--ai-prompts` 默认遵守；**但工具层面的 prompt 防御不替代人工复检**——实测 Agnes 仍偶有不合规输出（如 lof-exit-mechanism 封面出现中国国徽+飘字票据），生成后必须肉眼逐图扫一遍（重点扫门楣/中央/边缘的圆形徽标与飘字票据）。发现违规立刻 `rm <path>` 删除原图、用更强 negative prompt 重生成，**不要为了凑数保留违规图**；`process_notes.md` 同步记录"封面图合规复检"结果。
- **AI 概念图主题相关性**：封面/题图除合规外，**必须紧扣问题主题**——视觉应能映射问题的核心概念（如 LOF 退市→挤溢价泡沫+场内转场外；学术vs工业→书与机房的对话；半导体→晶圆/光刻意象）。**禁止使用与问题无关的纯装饰抽象图**（如"金色球体+棱柱"的通用科幻视觉，看似合规但读者看不出主题）。写 prompt 时必须先提炼 2-3 个核心视觉符号（如"溢价泡沫→发光气泡群/退市闸口→几何门框/按净值赎回→规整立方体阵列"），再围绕这些符号构造抽象叙事场景（左→中→右的视觉过渡即可直观映射问题逻辑）；如当前 slug 复用 DEFAULT_AI_PROMPTS（"斩杀线"等旧模板），必须替换为当前主题专用 prompt（`--ai-prompts` 自定义 JSON）。自检：①不看标题，读者能否从图中识别本报告主题？答否则必须重做；②`process_notes.md` 同步记录"封面图主题相关性复检"与 2-3 个核心视觉符号的映射说明。
- **AI 概念图构图饱满**：封面/题图**禁止大面积空白/留白**——prompt 不得写"左下角留白适合叠加标题"等留白引导（标题由知乎发布时叠加，图内不留白）；画面构图必须饱满、平衡，视觉元素均匀铺满整个画布，边角不留白。`_AI_IMAGE_NEGATIVE_GUARD` 已含 "no large empty areas, no blank corners, no white space reserved for text overlay"；自定义 prompt 也不再写留白引导。复检时同步检查四角/边缘是否有大块均匀空白（可用 PIL 网格扫描辅助）。

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
