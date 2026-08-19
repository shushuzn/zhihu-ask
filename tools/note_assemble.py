# -*- coding: utf-8 -*-
"""模块化笔记组装工具（zhihu-ask 项目专用）

从 notes/ 目录读取模块化笔记和索引笔记, 组装成报告骨架。
配合 flomo MCP 使用时, 可从 flomo 检索拉取笔记内容。

用法:
  python tools/note_assemble.py --slug <slug>
  python tools/note_assemble.py --slug <slug> --dry-run  # 只预览, 不写文件
  python tools/note_assemble.py --slug <slug> --output report_draft.md

流程:
  1. 读取 notes/00_index.md 索引笔记, 确定报告结构
  2. 按索引顺序读取 notes/ 下的模块化笔记
  3. 组装成报告骨架 (标记需要补过渡段的位置)
  4. 输出 report_draft.md 或打印到 stdout

配合 flomo MCP:
  从 flomo 检索模块化笔记, 与本地 notes/ 合并, 去重后组装。
  flomo 检索结果优先 (最新版本), 本地文件做备份。
"""

import sys
import os
import re
import json
import argparse
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_note_file(filepath):
    """解析笔记文件, 返回 {type, tags, content, sources, meta}。"""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # 解析标签行: 第一行全是 # 开头的标签, 如 "#AI伦理 #案例 #主题/xxx"
    tags = []
    first_line = text.split("\n")[0].strip() if text.strip() else ""
    if first_line.startswith("#"):
        tags = re.findall(r"#\S+", first_line)

    # 从标签/文件名推断笔记类型：00_index.md 或 #索引 为索引笔记，其余为普通模块化笔记
    note_type = "note"
    if "#索引" in tags or os.path.basename(filepath).startswith("00_"):
        note_type = "index"

    # 提取参考文献 (GB/T 7714-2015 格式, [1] [2] 编号条目；文献段以「参考文献:」或「## 参考文献」开头)
    sources = []
    source_match = re.search(r"(?:^参考文献[:：]?|^#{1,6}\s*参考文献)\s*\n(.*?)\Z", text, re.M | re.S)
    if source_match:
        raw = source_match.group(1).strip()
        # 提取 [1] xxx [2] xxx 格式
        sources = re.findall(r"\[\d+\]\s*(.+)", raw)
        # 兜底: 如果没有 [1] 格式, 按行提取
        if not sources:
            sources = [s.strip() for s in raw.split("\n")
                       if s.strip() and not re.match(r"^参考文献[:：]?\s*$", s.strip())]

    # 提取正文 (去掉第一行标签和参考文献信息)
    content = text
    # 去掉第一行 (标签行)
    content = re.sub(r"^#[^\n]+\n", "", content, count=1, flags=re.M)
    content = re.sub(r"^参考文献[:：]?\s*\n.*\Z", "", content, flags=re.M | re.S)
    # 剥离非规定字段行（来源/概念——来源统一在文末参考文献区著录）
    content = re.sub(r"^[ \t]*\*{0,2}(?:来源|概念)\*{0,2}[ \t]*[:：][^\n]*\n?", "", content, flags=re.M)
    content = content.strip()

    return {
        "type": note_type,
        "tags": tags,
        "content": content,
        "sources": sources,
        "source_type": "",
        "meta": {},
        "filepath": filepath,
    }


def load_notes(slug):
    """加载一个主题下的所有笔记 (扁平目录)。"""
    notes_dir = os.path.join(ROOT, "research", slug, "notes")
    if not os.path.isdir(notes_dir):
        print(f"ERROR: 笔记目录不存在: {notes_dir}")
        print("请先运行: python tools/init_research.py --config tools/init.json 或 python tools/research_start.py --config tools/start.json")
        return {}

    notes = {}
    for fname in sorted(os.listdir(notes_dir)):
        if fname.startswith("_") or not fname.endswith(".md"):
            continue
        fpath = os.path.join(notes_dir, fname)
        note = parse_note_file(fpath)
        note_id = fname.replace(".md", "")
        notes[note_id] = note

    return notes


def build_report_from_index(index_note, all_notes):
    """根据索引笔记构建报告结构。"""
    content = index_note["content"]
    sections = []
    current_section = None

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            if current_section:
                sections.append(current_section)
            current_section = {"title": line[3:], "notes": []}
        elif line.startswith("→") or "→" in line:
            # 组装顺序行（"02 → 03 → 04" 或 "→ #01"），提取全部编号引用笔记
            for m in re.finditer(r"(\d+)", line):
                note_num = m.group(1)
                for nid, note in all_notes.items():
                    if note_num in nid:
                        current_section["notes"].append(note)
                        break
        elif line.startswith("- 缺:") or line.startswith("- 待验证:"):
            if current_section:
                current_section["notes"].append({"content": line, "type": "gap"})

    if current_section:
        sections.append(current_section)

    return sections


def assemble_report(sections, slug):
    """将报告结构组装成 Markdown 文本。"""
    today = date.today().isoformat()
    lines = []

    lines.append(f"# {{知乎问题标题}}")
    lines.append("")
    lines.append(f"<!-- 组装于 {today}, slug: {slug} -->")
    lines.append("")
    lines.append("{{结论一两句话 ≤300 字}}")
    lines.append("")

    for i, section in enumerate(sections):
        lines.append(f"### {section['title']}")
        lines.append("")

        for note in section["notes"]:
            if note.get("type") == "gap":
                lines.append(f"> {note['content']}")
                lines.append("")
            else:
                # 模块化笔记内容直接使用，来源统一在文末「## 参考文献」区著录
                lines.append(note.get("content", ""))
                lines.append("")

        # 标记需要补过渡段的位置
        if i < len(sections) - 1:
            lines.append("<!-- [TODO: 补过渡段落] -->")
            lines.append("")

    # 参考文献区 (GB/T 7714-2015)
    lines.append("## 参考文献")
    lines.append("")
    ref_num = 1
    seen_sources = set()
    for section in sections:
        for note in section["notes"]:
            if note.get("type") == "gap":
                continue
            for src in note.get("sources", []):
                src_key = src[:50]  # 简单去重
                if src_key not in seen_sources:
                    seen_sources.add(src_key)
                    lines.append(f"[{ref_num}] {src}")
                    lines.append("")
                    ref_num += 1

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="模块化笔记组装工具")
    parser.add_argument("--slug", required=True, help="研究主题 slug")
    parser.add_argument("--dry-run", action="store_true", help="只预览, 不写文件")
    parser.add_argument("--output", default=None, help="输出文件路径 (默认 research/<slug>/report_draft.md)")
    args = parser.parse_args()

    slug = args.slug
    notes = load_notes(slug)
    if not notes:
        print("未找到笔记, 请先创建笔记。")
        sys.exit(1)

    print(f"已加载 {len(notes)} 条笔记:")
    for nid, note in notes.items():
        print(f"  {nid}: [{note['type']}] {note['content'][:50]}...")

    # 找索引笔记
    index_notes = [n for n in notes.values() if n["type"] == "index"]
    if not index_notes:
        print("\n未找到索引笔记, 无法组装报告。")
        print("请先创建 notes/00_index.md 索引笔记。")
        sys.exit(1)

    print(f"\n找到 {len(index_notes)} 条索引笔记, 使用第一条。")
    index_note = index_notes[0]

    sections = build_report_from_index(index_note, notes)
    report = assemble_report(sections, slug)

    if args.dry_run:
        print("\n" + "=" * 60)
        print("预览 (dry-run):")
        print("=" * 60)
        print(report)
    else:
        output_path = args.output or os.path.join(ROOT, "research", slug, "report_draft.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n已生成报告骨架: {os.path.relpath(output_path, ROOT)}")
        print("下一步: 补充过渡段落, 跑质检八件套。")


if __name__ == "__main__":
    main()
