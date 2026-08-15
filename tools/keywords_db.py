# -*- coding: utf-8 -*-
"""关键词库 SQLite 管理工具（zhihu-ask 项目专用）

关键词库主存储从 docs/KEYWORDS.md 迁到 .codebuddy/knowledge/knowledge.db；
docs/KEYWORDS.md 保留为可读导出物，由本工具同步。

用法：
    # 初始化数据库（首次从 docs/KEYWORDS.md 导入）
    python tools/keywords_db.py --init

    # 从 Markdown 导入（覆盖关键词表）
    python tools/keywords_db.py --import docs/KEYWORDS.md

    # 导出 Markdown（同步回 docs/KEYWORDS.md）
    python tools/keywords_db.py --export docs/KEYWORDS.md

    # 新增关键词（之后用 --export 同步 Markdown）
    python tools/keywords_db.py --add --section "数学 / 概率论" --kind "已验证有效组合" \
        --content "- `Equi-dependence implying independence`（arXiv 直查）" --slug foo

    # 查询
    python tools/keywords_db.py --list
    python tools/keywords_db.py --list --section "数学"
    python tools/keywords_db.py --search "arXiv"

    # 查看数据库路径
    python tools/keywords_db.py --path
"""

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import knowledge_store as ks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_KEYWORDS_MD = os.path.join(ROOT, "docs", "KEYWORDS.md")


def cmd_init():
    conn = ks.connect()
    ks.init_db(conn)
    if os.path.exists(DEFAULT_KEYWORDS_MD):
        n = ks.import_keywords_md(conn, DEFAULT_KEYWORDS_MD)
        print(f"已初始化并导入 {n} 条关键词：{ks.DB_PATH}")
    else:
        print(f"已初始化空关键词库：{ks.DB_PATH}")
    conn.close()


def cmd_import(path):
    conn = ks.connect()
    ks.init_db(conn)
    n = ks.import_keywords_md(conn, path)
    print(f"已导入 {n} 条关键词：{path}")
    conn.close()


def cmd_export(path):
    conn = ks.connect()
    ks.init_db(conn)
    text = ks.export_keywords_md(conn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"已导出 {len(text)} 字符：{path}")
    conn.close()


def cmd_add(args):
    conn = ks.connect()
    ks.init_db(conn)
    ks.add_keyword(conn, args.section, args.kind, args.content, args.slug)
    print(f"已新增：{args.section} / {args.kind}")
    conn.close()


def cmd_list(args):
    conn = ks.connect()
    ks.init_db(conn)
    rows = ks.list_keywords(conn, args.section)
    for r in rows:
        slug = f"  [{r['source_slug']}]" if r["source_slug"] else ""
        print(f"{r['section']} | {r['kind']} | {r['content']}{slug}")
    print(f"共 {len(rows)} 条")
    conn.close()


def cmd_search(args):
    conn = ks.connect()
    ks.init_db(conn)
    rows = ks.search_keywords(conn, args.search)
    for r in rows:
        slug = f"  [{r['source_slug']}]" if r["source_slug"] else ""
        print(f"{r['section']} | {r['kind']} | {r['content']}{slug}")
    print(f"共 {len(rows)} 条")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="关键词库 SQLite 管理")
    ap.add_argument("--init", action="store_true", help="初始化数据库并从 docs/KEYWORDS.md 导入")
    ap.add_argument("--import", dest="import_path", metavar="PATH", help="从 Markdown 导入")
    ap.add_argument("--export", dest="export_path", metavar="PATH", help="导出 Markdown")
    ap.add_argument("--add", action="store_true", help="新增关键词")
    ap.add_argument("--section", help="关键词所属领域/小节")
    ap.add_argument("--kind", default="条目", help="条目类型：主题词/视角词组合示例/通用模式/已验证有效组合/条目")
    ap.add_argument("--content", help="关键词内容（原样保存，含 - 前缀等）")
    ap.add_argument("--slug", help="来源研究 slug（可选）")
    ap.add_argument("--list", action="store_true", help="列出关键词")
    ap.add_argument("--search", metavar="QUERY", help="搜索关键词")
    ap.add_argument("--path", action="store_true", help="打印数据库路径")
    args = ap.parse_args()

    if args.path:
        print(ks.DB_PATH)
        return 0
    if args.init:
        cmd_init()
        return 0
    if args.import_path:
        cmd_import(args.import_path)
        return 0
    if args.export_path:
        cmd_export(args.export_path)
        return 0
    if args.add:
        if not args.section or not args.content:
            print("ERROR: --add 需要 --section 与 --content")
            return 1
        cmd_add(args)
        return 0
    if args.list:
        cmd_list(args)
        return 0
    if args.search:
        cmd_search(args)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
