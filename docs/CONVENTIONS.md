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
| zhihu skill / `zhihu-cli` | 可用（已 setup） | 知乎开放平台官方 CLI；认证未配置时返回 AUTH_REQUIRED |

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

## 5. 提交规范

- 功能类：`feat: 一句话说明`；修复类：`fix: ...`；文档类：`docs: ...`；工具类：`chore/tool: ...`。
- 提交前检查：临时文件已清理、`git status` 无多余文件、`.codebuddy/` 未入库。

## 6. zhihu skill / zhihu-cli 使用约定

- **安装位置**：skill 在 `C:\Users\35234\.codebuddy\skills\zhihu\`，CLI 在 `C:\Users\35234\AppData\Local\ZhihuCLI\current\zhihu-cli.exe`。
- **状态检查**：`powershell -ExecutionPolicy Bypass -File <skill-dir>/scripts/run.ps1 status`。
- **认证配置**：`zhihu-cli auth set --secret-stdin`（凭证经标准输入传入，不进进程参数、不回显明文、不写入项目文件，存于系统密钥链）。未配置时业务命令返回 `AUTH_REQUIRED`，引导用户打开 https://developer.zhihu.com/profile 申请 Access Secret 后配置。
- **中文参数**：向 CLI 传中文一律经 `tools/zhihu_search.py`（Python subprocess 传 Unicode）调用，不在 PowerShell 直接写中文参数。
- **数据边界**：热榜只做议题发现；深度研究用 search 不用直答；搜索返回摘要，原文需 `web_fetch` 打开链接。
- **额度**：同一账号所有 Access Secret 共享当日池（全网/知乎搜索 5000 次、热榜 100 次、直答 100 次，邀测免费）；`Code:30001` 频率限制、`Code:30002` 配额耗尽时停止重试。
- **凭证安全**：不得在回复、日志、Shell 历史或项目文件中重复完整 Access Secret；泄露后引导用户在开放平台删除并重新申请。
- **前置检查**：研究流程在阶段 1 前用 `run.ps1 status` 确认 `auth.configured=true`，未配置则引导用户配置后重试，不阻塞其他通道。

## 7. ima 知识库使用约定（通道 E）

- **连接状态**：ima 连接器（ima-mcp）经 WorkBuddy 侧边栏「更多 → ima知识库」OAuth 授权；连接器管理页显示 connected 即可用。未连接时通道 E 跳过，不阻塞其余通道。
- **检索**：主代理直执连接器工具（`search_knowledge_base` 搜库 / `search_knowledge` 库内检索），与本地 `rag_search.py` 互补；ima 无 CLI，不涉及乱码问题。
- **凭证**：连接器方案无需凭证。脚本化（OpenAPI）才需 Client ID + API Key（https://ima.qq.com/agent-interface 生成，仅显示一次），存 `~/.config/ima/` 或环境变量；**凭证不入项目文件、不入日志**，泄露后引导在 agent-interface 撤销重建（沿用第 6 节凭证安全原则）。
- **隐私边界（写入硬性管控）**：读取无限制；写入（import_urls / add_knowledge）仅限公开级内容——docs/、templates/、脱敏经验与词库；已定稿 report.md 须用户逐篇确认；gathered 素材、plan.md、问题原文禁止写入。ima 为云服务，与「research/ 仅存本地」红线冲突的内容一律不上云。
- **参考**：能力盘点与分级矩阵见 `docs/IMA_INTEGRATION.md`。

## 8. 领域连接器约定（通道 C：通达信 / 企查查）

- **连接状态**：通达信（tdx-connector）、企查查（qcc-company）经 WorkBuddy 连接器授权（连接器管理页 connected 即可用）；未连接或调用失败时跳过该数据源，改用 Web/其他插件补位，不阻塞流程。
- **只读原则**：两者均为只读数据源，仅查询引用，不执行交易、不写回数据。
- **通达信纪律**：`tdx_quotes`/`tdx_api_data` 的 code 只接受纯数字，中文名必须先 `tdx_lookup_stock` 查码（期货传 range="QH"、期权传 range="QQ"）；code 与 setcode 必须匹配；接口返回空结果时如实报告"该数据暂无"，禁止用训练数据填充行情/财务数字。
- **企查查纪律**：先用 `get_company_by_query` 锁定实体；返回多候选时必须把候选列表完整展示给用户、等用户确认后再调下游工具，自动选第一条属错误操作；穿透类结果（实控人持股/受益股份/财务比率）为服务端精算终值，逐字引用，禁止自乘重算或臆测中间层主体（实测算错案例：79.8674%×11.5446% 曾被算成 9.2145%，正确 9.2204%）。
- **凭证/额度**：无需项目内凭证（连接器托管授权）；企查查查询有账号额度限制，批量尽调前控制查询次数。
- **用法**：工具表与调用示例见 `docs/TOOLS.md`「领域连接器」章节。
