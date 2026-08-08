# -*- coding: utf-8 -*-
"""
RAG 知识库构建工具（zhihu-ask 项目专用）

把公开文档（docs/、templates/）按 Markdown 章节分片，构建本地检索索引，
供 rag_search.py 做 BM25 检索。知识库内容来自公开文件，索引为派生缓存
（存 .codebuddy/knowledge/，仅本地）。

用法：
    python tools/rag_build.py                 # 默认扫描 docs/ + templates/
    python tools/rag_build.py --dir docs      # 只扫描指定目录（可多次）

输出：
    .codebuddy/knowledge/index.json           # 分片索引（UTF-8）
    .codebuddy/knowledge/meta.json            # 构建信息（文件数/片数/时间）

说明：
- 分片按 Markdown 二级/三级标题（## / ###）切分，无标题内容归入首个分片。
- 分片上限 2000 字符，超出截断（防大表格/长列表撑爆索引）。
- 仅收录 UTF-8 文本文件；.md 以外的文件忽略。
"""

import sys
import os
import json
import re
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, ".codebuddy", "knowledge")
INDEX_FILE = os.path.join(OUT_DIR, "index.json")
META_FILE = os.path.join(OUT_DIR, "meta.json")

DEFAULT_DIRS = ["docs", "templates"]
MAX_CHUNK = 2000

HEADING_RE = re.compile(r"^#{2,3}\s+(.*)$")


def parse_args(argv):
    dirs = []
    for i, a in enumerate(argv):
        if a == "--dir" and i + 1 < len(argv):
            dirs.append(argv[i + 1])
    return dirs or DEFAULT_DIRS


def split_chunks(text, path):
    """按 ##/### 标题切分 Markdown 文本，返回 [(section, chunk_text)]。"""
    chunks = []
    cur_heading = None
    cur_lines = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if cur_lines:
                body = "\n".join(cur_lines).strip()
                if body:
                    chunks.append((cur_heading, body))
            cur_heading = m.group(1).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    if cur_lines:
        body = "\n".join(cur_lines).strip()
        if body:
            chunks.append((cur_heading, body))
    # 过滤过短分片（纯占位/空壳）
    return [(h or path, c) for h, c in chunks if len(c) >= 30]


def build():
    dirs = parse_args(sys.argv[1:])
    docs = []
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            print(f"WARN: 目录不存在 {base}")
            continue
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith(".md"):
                    docs.append(os.path.join(root, fn))

    chunks = []
    for p in sorted(docs):
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        try:
            with open(p, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"WARN: 跳过 {rel}: {e}")
            continue
        # 模板占位符（{{...}}）保留，检索时可命中结构说明
        for section, body in split_chunks(text, rel):
            if len(body) > MAX_CHUNK:
                body = body[:MAX_CHUNK] + "…"
            chunks.append({
                "path": rel,
                "section": section,
                "text": body,
            })

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)
    meta = {
        "built": date.today().isoformat(),
        "files": len(docs),
        "chunks": len(chunks),
        "dirs": dirs,
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"构建完成: {len(docs)} 个文件 -> {len(chunks)} 个分片")
    print(f"索引: {os.path.relpath(INDEX_FILE, ROOT)}")
    for d in dirs:
        print(f"  - {d}/")
    return 0


if __name__ == "__main__":
    sys.exit(build())
