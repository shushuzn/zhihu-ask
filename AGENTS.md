# zhihu-ask 项目开发指南

## 常用命令

### 测试
```bash
# 全套回归测试（包含 unittest 风格 + expect 风格）
python3 tests/run_all.py

# 单个测试模块
python3 tests/test_quality.py
python3 tests/test_gbt_refs.py
python3 tests/test_citation_validity.py
# ... 其他 test_*.py

# 单元测试（unittest 风格）
python3 tests/test_jspace_integration.py
```

### 代码质量检查
```bash
# 质检单文件（报告/笔记）
python3 tools/quality_check.py --file research/<slug>/report.md
python3 tools/quality_check.py --file research/<slug>/notes/01_xxx.md

# GB/T 7714 参考文献合规检查
python3 tools/check_gbt_refs.py --file research/<slug>/notes/01_xxx.md

# 引用有效性检查
python3 tools/check_citation_validity.py --file research/<slug>/report.md

# 全库体检
python3 tools/check_all.py --slug <slug>
```

### 研究流程工具
```bash
# 初始化研究
python3 tools/research_start.py --config tools/start.json

# 标记通道完成
python3 tools/mark_channel.py --slug <slug> --channel E --status done --note "..."

# 检查进度
python3 tools/check_progress.py --slug <slug> --require report_channels

# 组装报告骨架
python3 tools/note_assemble.py --slug <slug>

# 生成 Word 文档
python3 tools/report_to_docx.py --slug <slug>

# 关键词沉淀
python3 tools/keywords_db.py --add --content "xxx" --section "大模型推理"
python3 tools/keywords_db.py --export docs/KEYWORDS.md

# 完整流水线
python3 tools/run_pipeline.py --slug <slug>
```

### Git Hooks
```bash
# 安装/更新 pre-commit hook（自动跑回归套件 + 内部文件检查）
python3 tools/install_git_hooks.py

# 移除 hook
python3 tools/install_git_hooks.py --remove
```

### 健康检查
```bash
python3 tools/health_check.py
```

## 关键环境变量
- `ZHIHU_ASK_VENV_PY`：可选，指定隔离 venv 的 Python 解释器（默认 `./venv/bin/python`）

## 规范约束（硬性拦截）
- 报告：标题 ≤30 字、结论 ≤300 字、小节用 `###`、参考文献 GB/T 7714-2015、禁"但"/长破折号/LaTeX/arXiv 预印本字样
- 笔记：tag 行 + 纯文本标题 + 正文 + `参考文献:`，**禁止"来源/概念"字段**、**正文 [n] 与文献一一对应**
- 参考文献区：条目间空行、无 LaTeX、含 URL 必带引用日期 `[YYYY-MM-DD]`
- 正文禁止分级词括注`（一手/二手/推算）`、禁"arXiv 预印本"、禁立场/框架/评价词
- 所有检查以 `quality_check.py` / `check_gbt_refs.py` / `check_citation_validity.py` 为准

## 提交流程
1. 代码修改后 `python3 tests/run_all.py` 全绿
2. `python3 tools/health_check.py` 全绿
3. `git add` 相关文件（`tools/` `tests/` `.gitignore` 等公开文件；`research/` `plan.md` `docs/KEYWORDS.md` 不入库）
4. `git commit -m "..."`（身份 shushuzn / 132275809+shushuzn@users.noreply.github.com）
5. `git push`
