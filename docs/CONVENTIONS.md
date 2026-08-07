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

## 3. 数据与文件规范

- 所有项目文档、检索文件、临时文件一律 UTF-8 编码（write_to_file 默认即可）。
- 临时文件（commit 消息、描述、keywords.json）用完即删，不提交入库。
- `.codebuddy/` 为本地数据目录，已在 `.gitignore` 排除，不要删除。

## 3.5 提交管理规范

- `git add -A` 前先 `git status` 确认无多余文件被暂存。
- 提交时 pre-commit hook 自动运行 `tools/git_protect.py` 检查暂存区（见 `docs/TOOLS.md`）；hook 未被安装时手动运行 `python tools/git_protect.py` 校验。
- 若发现内容被误推，立即处理：`git rm --cached <文件>` + 更新 `.gitignore` + 提交修正；若已在历史提交中，用 `git filter-repo` 重写历史。
- 禁止未经用户确认直接 `git push` 或 `gh repo create`；创建仓库、改可见性、强推等操作必须先获得用户明确同意。

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
