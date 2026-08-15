"""rag_build.py 回归测试：索引构建的纯函数（18 项）。

覆盖：
- is_indexable：research/ 仅收 process_notes.md（报告/素材库噪音排除）；其他目录收 *.md
- parse_args：--dir 多目录 / 缺值回退 / 默认目录
- split_chunks：##/### 标题切分、无标题内容归入首片（section 回退 path）、
  短正文（<30 字符）过滤、空正文丢弃、多节与末尾正文

行为锁定：分片规则回退会改变整个知识库的检索覆盖面（章节归属错误
会让 rag_search 命中错位或漏检），需回归守护。

运行：python tests/test_rag_build.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import rag_build as rb

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- is_indexable：research/ 只收 process_notes.md ----
expect("idx+ research process_notes", rb.is_indexable("research/foo/process_notes.md", "process_notes.md"), True)
expect("idx- research report", rb.is_indexable("research/foo/report.md", "report.md"), False)
expect("idx- research gathered", rb.is_indexable("research/foo/gathered_wechat.md", "gathered_wechat.md"), False)
expect("idx- research plan", rb.is_indexable("research/foo/plan.md", "plan.md"), False)
expect("idx- research 其他 md", rb.is_indexable("research/foo/notes.md", "notes.md"), False)

# ---- is_indexable：其他目录收 .md ----
expect("idx+ docs md", rb.is_indexable("docs/TOOLS.md", "TOOLS.md"), True)
expect("idx+ templates md", rb.is_indexable("templates/plan_TEMPLATE.md", "plan_TEMPLATE.md"), True)
expect("idx+ 根目录 md", rb.is_indexable("README.md", "README.md"), True)
expect("idx- 非 md", rb.is_indexable("docs/fig.png", "fig.png"), False)
expect("idx- research 下非 md", rb.is_indexable("research/foo/x.json", "x.json"), False)

# ---- parse_args ----
expect("args 无参默认", rb.parse_args([]), rb.DEFAULT_DIRS)
expect("args 单目录", rb.parse_args(["--dir", "docs"]), ["docs"])
expect("args 多目录", rb.parse_args(["--dir", "docs", "--dir", "templates"]), ["docs", "templates"])
expect("args 缺值回退默认", rb.parse_args(["--dir"]), rb.DEFAULT_DIRS)
expect("args 未知参数忽略", rb.parse_args(["--foo", "--dir", "docs"]), ["docs"])

# ---- split_chunks：标题切分与首片回退 ----
text = (
    "# 文档标题\n\n"
    "文档开头介绍文字，这段内容足够长，超过三十个字符的限制，因此会被收录为分片。\n\n"
    "## 第一节\n\n"
    "第一节的正文内容，这段文字同样足够长，远远超过三十个字符的限制，会被收录。\n\n"
    "### 子节\n\n"
    "子节的正文内容，这一段文字也足够长，超过三十个字符的限制，因此被收录为分片。\n"
)
chunks = rb.split_chunks(text, "docs/x.md")
expect("chunk+ 节标题顺序", [s for s, _ in chunks], ["docs/x.md", "第一节", "子节"])
expect("chunk+ 首片回退为 path", chunks[0][0], "docs/x.md")
expect("chunk+ 三片齐全", len(chunks), 3)
expect("chunk+ 正文非空", all(len(c) >= 30 for _, c in chunks), True)

# 短正文（<30）过滤
text = "## A\n\n太短。\n\n## B\n\n" + "长" * 40
chunks = rb.split_chunks(text, "docs/y.md")
expect("chunk- 短正文过滤", [s for s, _ in chunks], ["B"])

# 连续标题无正文 → 不产出分片
text = "## 空一\n\n## 空二\n\n" + "实" * 40
chunks = rb.split_chunks(text, "docs/z.md")
expect("chunk- 空节不产出", [s for s, _ in chunks], ["空二"])

# 末尾正文归属最后标题
text = "## 尾节\n\n" + "尾" * 40 + "\n\n无标题尾段，" + "补" * 40
chunks = rb.split_chunks(text, "docs/w.md")
expect("chunk+ 末尾正文并入当前节", [s for s, _ in chunks], ["尾节"])

# 一级标题不触发切分（仅 ##/###）
text = "# 一级标题\n\n" + "内" * 40 + "\n\n## 二级\n\n" + "容" * 40
chunks = rb.split_chunks(text, "docs/h.md")
expect("chunk+ 一级标题不切分", [s for s, _ in chunks], ["docs/h.md", "二级"])


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
