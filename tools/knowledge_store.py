# -*- coding: utf-8 -*-
"""SQLite 知识存储（zhihu-ask 项目专用）

统一管理两类本地知识：
1. RAG 分片：rag_build.py 构建的 Markdown 分片索引；
2. 关键词库：原 docs/KEYWORDS.md 的结构化数据。

数据库文件放在 .codebuddy/knowledge/knowledge.db（仅本地，不入库）。
docs/KEYWORDS.md 仍保留为可读导出物，但主存储为 SQLite。
"""

import os
import re
import sqlite3
import sys

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from tools.run_util import ROOT
except ModuleNotFoundError:
    from run_util import ROOT  # 被测导入时 tools 不在包路径
DB_PATH = os.path.join(ROOT, ".codebuddy", "knowledge", "knowledge.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    built_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rag_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS keyword_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS keyword_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL REFERENCES keyword_sections(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT '条目',
    content TEXT NOT NULL,
    source_slug TEXT,
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keyword_entries_section ON keyword_entries(section_id);
"""


def connect(db_path=None):
    """打开 SQLite 连接，启用外键与 Row 访问。"""
    path = db_path or DB_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """建表（幂等）。"""
    conn.executescript(SCHEMA)
    conn.commit()


# ---------- RAG 分片 ----------

def replace_chunks(conn, chunks, built_at):
    """清空并写入全量 RAG 分片。"""
    conn.execute("DELETE FROM rag_chunks")
    conn.executemany(
        "INSERT INTO rag_chunks (path, section, text, built_at) VALUES (?, ?, ?, ?)",
        [(c["path"], c["section"], c["text"], built_at) for c in chunks],
    )
    conn.execute(
        "INSERT OR REPLACE INTO rag_meta (key, value) VALUES ('built_at', ?)",
        (built_at,),
    )
    conn.execute(
        "INSERT OR REPLACE INTO rag_meta (key, value) VALUES ('chunk_count', ?)",
        (str(len(chunks)),),
    )
    conn.commit()


def load_chunks(conn):
    """读取全部 RAG 分片，返回 [{path, section, text}]。"""
    rows = conn.execute(
        "SELECT path, section, text FROM rag_chunks ORDER BY id"
    ).fetchall()
    return [{"path": r["path"], "section": r["section"], "text": r["text"]} for r in rows]


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM rag_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO rag_meta (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()


# ---------- 关键词库 ----------

def parse_keywords_md(text):
    """解析 KEYWORDS.md 文本，返回 [(section, kind, content)]。

    - `## ` 开头开启新 section；
    - `主题词：` / `视角词组合示例：` / `通用模式：` 等行作为带 kind 的条目；
    - `- ` 列表行继承最近的 kind（无则用「条目」）；
    - 其余非空行按「条目」保存。
    """
    entries = []
    section = None
    current_kind = "条目"
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped.strip():
            continue
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            current_kind = "条目"
            continue
        if section is None:
            section = "未分类"
        lower = stripped.lstrip()
        if lower.startswith("主题词："):
            current_kind = "主题词"
        elif lower.startswith("视角词组合示例："):
            current_kind = "视角词组合示例"
        elif lower.startswith("通用模式："):
            current_kind = "通用模式"
        elif lower.startswith("已验证有效组合："):
            current_kind = "已验证有效组合"
        elif not stripped.startswith("-") and not stripped.startswith("  "):
            current_kind = "条目"
        entries.append((section, current_kind, stripped))
    return entries


def import_keywords_md(conn, path):
    """把 KEYWORDS.md 导入 SQLite（先清空关键词表）。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    entries = parse_keywords_md(text)
    conn.execute("DELETE FROM keyword_entries")
    conn.execute("DELETE FROM keyword_sections")
    sections = {}
    order = 0
    for section, kind, content in entries:
        if section not in sections:
            cur = conn.execute(
                "INSERT INTO keyword_sections (title, sort_order) VALUES (?, ?)",
                (section, len(sections) + 1),
            )
            sections[section] = cur.lastrowid
        sid = sections[section]
        order += 1
        conn.execute(
            "INSERT INTO keyword_entries "
            "(section_id, kind, content, source_slug, sort_order, created_at) "
            "VALUES (?, ?, ?, NULL, ?, datetime('now'))",
            (sid, kind, content, order),
        )
    conn.commit()
    return len(entries)


def export_keywords_md(conn):
    """从 SQLite 导出 KEYWORDS.md 文本。"""
    lines = []
    sections = conn.execute(
        "SELECT id, title FROM keyword_sections ORDER BY sort_order"
    ).fetchall()
    for sec in sections:
        if sec["title"] != "未分类":
            lines.append("## " + sec["title"])
            lines.append("")
        rows = conn.execute(
            "SELECT content FROM keyword_entries WHERE section_id = ? "
            "ORDER BY sort_order",
            (sec["id"],),
        ).fetchall()
        for r in rows:
            lines.append(r["content"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def add_keyword(conn, section, kind, content, source_slug=None):
    """新增/追加一条关键词；section 不存在则创建。"""
    row = conn.execute(
        "SELECT id FROM keyword_sections WHERE title = ?", (section,)
    ).fetchone()
    if row:
        sid = row["id"]
    else:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM keyword_sections"
        ).fetchone()[0]
        sid = max_order + 1
        conn.execute(
            "INSERT INTO keyword_sections (title, sort_order) VALUES (?, ?)",
            (section, sid),
        )
    max_entry = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM keyword_entries WHERE section_id = ?",
        (sid,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO keyword_entries "
        "(section_id, kind, content, source_slug, sort_order, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (sid, kind, content, source_slug, max_entry + 1),
    )
    conn.commit()


def list_keywords(conn, section=None):
    """列出关键词；可按 section 过滤。"""
    if section:
        rows = conn.execute(
            "SELECT s.title AS section, e.kind, e.content, e.source_slug "
            "FROM keyword_entries e JOIN keyword_sections s ON e.section_id = s.id "
            "WHERE s.title LIKE ? ORDER BY s.sort_order, e.sort_order",
            (f"%{section}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT s.title AS section, e.kind, e.content, e.source_slug "
            "FROM keyword_entries e JOIN keyword_sections s ON e.section_id = s.id "
            "ORDER BY s.sort_order, e.sort_order"
        ).fetchall()
    return [dict(r) for r in rows]


def search_keywords(conn, query):
    """对关键词内容做简单 LIKE 检索。"""
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT s.title AS section, e.kind, e.content, e.source_slug "
        "FROM keyword_entries e JOIN keyword_sections s ON e.section_id = s.id "
        "WHERE e.content LIKE ? OR s.title LIKE ? "
        "ORDER BY s.sort_order, e.sort_order",
        (like, like),
    ).fetchall()
    return [dict(r) for r in rows]
