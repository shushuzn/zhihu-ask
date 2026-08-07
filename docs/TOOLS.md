# 项目内工具说明

解决开发环境中命令行中文参数乱码、外部脚本路径耦合等问题。所有工具放在 `tools/`。

## init_research.py — 研究目录初始化

**作用**：一键创建新研究，避免手动复制模板。自动完成：创建 `research/<slug>/` 目录 → 从模板生成 plan/report/zhihu_answer/process_notes 四个文件 → 填入问题标题/日期/领域 → 在 `plan.md` 问题索引表登记一行。

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

# 或指定时间范围（推荐，与 SOP 一致）
python tools/wechat_search.py --keywords tools/keywords.json --time-range 2025-08-01 2026-08-01
```

**输出**：每个关键词的结果清单（标题/公众号/时间/摘要/链接），UTF-8 编码。

**注意**：
- 关键词文件必须 UTF-8 编码（用 write_to_file 创建即可保证）。
- 冷门关键词搜狗可能补充旧文章，需按返回的 time 字段自行过滤。
- 触发验证码时返回 "触发验证码，请稍后重试"，稍后再试即可。
- 每轮研究结束，将 `tools/keywords.json` 中的有效组合回填至 `docs/KEYWORDS.md`，并删除该临时文件。

## git_protect.py — 提交前检查

**作用**：提交前检查暂存区，阻止 `plan.md`、`research/`、`.codebuddy/`、`docs/PLAN_v1_ARCHIVE.md`、临时 config 等内部文件被误提交。

**用法**：

```bash
python tools/git_protect.py    # 检查暂存区；发现内部文件则退出码 1 并列出
```

**注意**：内部文件清单见脚本内 `INTERNAL_PATTERNS`，按需增改。可与 `git commit` 串联使用，作为提交前的例行校验。

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

## 降级方案

若 `research_subagent` 因配置问题不可用（如 "Model not found"），由主代理直接执行检索：web_search / web_fetch 均可由主代理调用，公众号检索走上述包装工具。信息密度会降低，但流程可跑通（首个研究已验证可行）。
