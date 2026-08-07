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

**作用**：把「启动一次知乎问题研究」压缩为一条命令，并落地 SOP 附录 A 的执行级逻辑。自动完成：配置校验（question/slug 必填、关键词下限提示）→ 初始化研究目录（阶段 0）→ 公众号检索并落盘素材库 `research/<slug>/gathered_wechat.md`（阶段 1 通道 A）→ 素材库非空校验 → 记录阶段进度 `.progress.json` → 打印后续步骤（阶段 2-4 上下文）。

**用法**：

```bash
python tools/research_start.py --config tools/start.json
```

**config 格式**（UTF-8）：
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

**作用**：把"单轮研究"升级为"多轮迭代"。每完成一轮，读取上一轮报告，从【局限/未尽问题/可深化点】自动提取下一轮问题清单（写 round_notes.md），并更新 `.progress.json` 的 round 记录。逐轮深化，一般 3 轮达到质量收敛。

**用法**：

```bash
python tools/iter_research.py --slug <slug>            # 生成下一轮问题清单（当前轮+1）
python tools/iter_research.py --slug <slug> --round 2  # 指定目标轮次
```

**强制多轮流程（至少 3 轮，不询问用户）**：
- 第 1 轮：`research_start.py` 启动 → 阶段 2/3/4 产出 report.md
- 第 2 轮：本工具生成问题清单 → 补检索/深化 → 直接在 report.md 上更新
- 第 3 轮：同上，继续深化。至少完成 3 轮该研究才算完成，禁止询问用户是否继续。

**注意**：工具只生成问题清单与更新轮次，不替代主代理的分析写作。报告路径 research/<slug>/report.md；迭代直接在原文件更新，不创建 vN 版本文件。3 轮为下限，3 轮内不得以"已收敛"为由提前停止。

## quality_check.py — 回答质量自动检查

**作用**：把回答模板/CHECKLIST 中的「去 AI 味 + 立场中立」检查落地为自动扫描。检测立场词（我认为/应该/总之等）、框架词（先说结论/总结一下等）、评价词（太猛/离谱等）、感叹号/反问句、无来源数字（启发式）。

**用法**：

```bash
python tools/quality_check.py --file research/<slug>/report.md
python tools/quality_check.py --file research/<slug>/report.md --verbose
```

**输出**：全部通过退出码 0；检出待确认项退出码 1 并列出位置与命中词。检出项为启发式规则，需人工确认是否真正违规（如"不构成投资建议"中的"建议"为合法用法）。

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

## 降级方案

`research_subagent` 配置的模型不可用（"Model not found"），**主代理直执是当前默认方式**（非降级）：web_search / web_fetch 均由主代理调用，公众号检索走上述包装工具。已实测可行（两份研究均以此完成）。若子代理配置修复，可升级回并行分派。
