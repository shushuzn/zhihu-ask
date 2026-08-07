# -*- coding: utf-8 -*-
"""
研究初始化脚本（zhihu-ask 项目专用）

一键创建新的研究目录：
1. 在 research/<slug>/ 下生成 3 个文件（plan/report/process_notes），从模板复制并填入基础占位符。
2. 更新 plan.md 的问题索引表（追加一行，状态=进行中）。

用法（Windows PowerShell 下中文必须走 --config 文件，见 docs/CONVENTIONS.md）：

    # 方式一：config 文件（推荐，规避中文乱码；示例格式见 tools/init.example.json）
    python tools/init_research.py --config tools/init.json

    # 方式二：直接传参（非 Windows 或参数无中文时）
    python tools/init_research.py --question "问题标题" --domain "示例领域" --slug example-slug

config 文件格式（UTF-8）：
    {
      "question": "问题完整标题",
      "domain": "示例领域",
      "slug": "example-slug",
      "priority": "中"
    }
"""

import sys
import os
import re
import json
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
RESEARCH = os.path.join(ROOT, "research")
PLAN = os.path.join(ROOT, "plan.md")

# 模板 -> 目标文件名
FILES = [
    ("research_plan_TEMPLATE.md", "plan.md"),
    ("research_report_TEMPLATE.md", "report.md"),
    ("process_notes_TEMPLATE.md", "process_notes.md"),
]


def parse_args(argv):
    args = {"config": None, "question": None, "domain": "其他", "slug": None, "priority": "中"}
    i = 0
    while i < len(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            args["config"] = argv[i + 1]
            i += 2
        elif argv[i] == "--question" and i + 1 < len(argv):
            args["question"] = argv[i + 1]
            i += 2
        elif argv[i] == "--domain" and i + 1 < len(argv):
            args["domain"] = argv[i + 1]
            i += 2
        elif argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--priority" and i + 1 < len(argv):
            args["priority"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args


def slug_ok(slug):
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""))


def load_config(args):
    if args["config"]:
        with open(args["config"], "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg
    if not args["question"]:
        print("ERROR: 需要 --question 或 --config")
        sys.exit(1)
    return {
        "question": args["question"],
        "domain": args["domain"],
        "slug": args["slug"],
        "priority": args["priority"],
    }


def fill_template(tpl_path, question, domain, today):
    with open(tpl_path, "r", encoding="utf-8") as f:
        content = f.read()
    replacements = {
        "{{知乎问题完整标题}}": question,
        "{{YYYY-MM-DD}}": today,
    }
    # plan 模板特有
    if os.path.basename(tpl_path) == "research_plan_TEMPLATE.md":
        replacements["{{进行中 / 已完成}}"] = "进行中"
        replacements["{{金融 / 产品 / AI / 其他}}"] = domain
    for k, v in replacements.items():
        content = content.replace(k, v)
    return content


def append_to_index(domain, slug, today):
    """在 plan.md「问题索引表」小节插入一行；找不到则提示手动添加。"""
    if not os.path.exists(PLAN):
        return False
    with open(PLAN, "r", encoding="utf-8") as f:
        content = f.read()

    # 仅定位「问题索引表」标题到下一个二级标题之间，避免误匹配其他表格
    header_m = re.search(r"^## 三、问题索引表\s*\n", content, re.MULTILINE)
    if not header_m:
        return False
    section_end = content.find("\n## ", header_m.end())
    if section_end == -1:
        section_end = len(content)
    section = content[header_m.end():section_end]

    # 找到该表格的标题行+分隔行（标题行含 topic_slug）
    m = re.search(r"^\|.*topic_slug.*\|\s*\n(\s*\|[-:\s|]+\|\s*)\n", section, re.MULTILINE)
    if not m:
        return False
    # 索引表只记录进度与 topic_slug，不含知乎问题具体内容（隐私）
    row = f"| {today} | {domain} | {slug} | 进行中 |"
    insert_offset = header_m.end() + m.end()
    content = content[:insert_offset] + row + "\n" + content[insert_offset:]

    with open(PLAN, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    args = parse_args(sys.argv[1:])
    cfg = load_config(args)

    question = cfg.get("question", "").strip()
    domain = cfg.get("domain", "其他").strip()
    slug = (cfg.get("slug") or "").strip().lower()
    priority = cfg.get("priority", "中")
    today = date.today().isoformat()

    if not question:
        print("ERROR: 缺少 question")
        sys.exit(1)
    if not slug:
        print("ERROR: 缺少 slug（英文小写短横线，如 example-slug）")
        sys.exit(1)
    if not slug_ok(slug):
        print("ERROR: slug 格式非法，须为英文小写短横线（如 example-slug）")
        sys.exit(1)

    target_dir = os.path.join(RESEARCH, slug)
    if os.path.exists(target_dir):
        print(f"ERROR: 目录已存在: {target_dir}")
        sys.exit(1)

    os.makedirs(target_dir)
    for tpl, name in FILES:
        src = os.path.join(TEMPLATES, tpl)
        dst = os.path.join(target_dir, name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(fill_template(src, question, domain, today))
        print(f"已生成: {os.path.relpath(dst, ROOT)}")

    if append_to_index(domain, slug, today):
        print(f"已登记索引: {slug}（状态=进行中，优先级={priority}）")
    else:
        print("提示: 未能自动更新 plan.md 索引表，请手动添加一行。")

    print("\n下一步：按 docs/SOP.md 阶段 0-4 执行。完成后回填索引状态为「已完成」。")
    print("完成后请删除临时 config 文件（本机中文参数必须文件传参，见 docs/CONVENTIONS.md）。")


if __name__ == "__main__":
    main()
