# -*- coding: utf-8 -*-
"""
研究报告 → flomo 完整上传工具（zhihu-ask 项目专用）

参考 mynews 项目的 flomo 集成模式（见 D:/OpenClaw/mynews/scripts/process_inbox.py）：
把研究报告【完整内容】转换为 flomo 兼容格式后上传，一字不改、只转格式。
flomo 仅支持加粗/高亮/下划线/有序/无序列表，不支持标题/引用/代码块/链接/表格，
故做以下机械转换（不增删任何文字）：
  - 标题（#/##/###）→ 加粗 **标题**
  - 引用（>）→ 正文（去掉 >）
  - 表格行（| a | b |）→ 列表 - a / b；表头分隔行（|---|）跳过
  - 链接 [标题](url) → 标题（url）
  - 反引号（`）→ 去掉
其余内容原样保留。

用法：
    python tools/report_to_flomo.py --slug <slug>                    # 打印完整转换结果
    python tools/report_to_flomo.py --slug <slug> --out flomo_full.md # 写文件（research/<slug>/）

查重流程（上传前必做，对应 mynews relevance 判断）：
    1. 主代理用 flomo MCP memo_search 搜报告标题/主题词，取最相似笔记 relevance：
       - relevance < 0.5：主题无重叠 → memo_create 新建
       - 0.5 ≤ relevance < 0.9：主题相近 → 人工判断（已有本报告则跳过；有新增量则 update）
       - relevance ≥ 0.9：高相似 → 已存在则跳过（skip）；有新增内容则 memo_update
    2. 上传内容为本工具输出的完整报告（首行标签 #知识基座 #一级 #二级 为 flomo 分类元信息，
       非报告内容；上传时保留）。

隐私说明：上传报告全文至用户自己的 flomo 笔记；素材库（gathered_*）、plan.md 仍仅存本地。
"""

import sys
import os
import re
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# domain → (一级领域标签, 二级领域标签) 映射（按顺序优先匹配，具体领域排前）
DOMAIN_TAGS = {
    "能源": ("能源", "油气煤炭"),
    "ai": ("AI", "科技社会"),
    "财政": ("财政", "宏观经济"),
    "宏观": ("财政", "宏观经济"),
    "金融": ("金融", "投资理财"),
    "贵金属": ("金融", "贵金属"),
    "数码": ("数码", "消费电子"),
    "产品": ("产品", "职业成长"),
    "法律": ("法律", "合规"),
    "教育": ("教育", "学业规划"),
}


def get_meta(slug):
    """从 report.md 头部读取领域与标题（仅元信息，不读正文）。"""
    path = os.path.join(ROOT, "research", slug, "report.md")
    domain, title = "", ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f.readlines()[:8]:
                m = re.match(r"#\s*研究报告[：:]\s*(.+)", line.strip())
                if m and not title:
                    title = m.group(1).strip()
                m = re.match(r">\s*日期[：:]\s*([\d-]+).*?领域[：:]\s*([^|]+)", line.strip())
                if m:
                    domain = m.group(2).strip()
    except OSError as e:
        print(f"[错误] 无法读取报告头部: {e}")
    return title, domain


def pick_tags(domain):
    """领域 → (一级, 二级) 标签。"""
    d = (domain or "").strip()
    for key, tags in DOMAIN_TAGS.items():
        if key.lower() in d.lower():
            return tags
    first = re.split(r"[/、,，\s]+", d)[0] if d else "研究"
    return (first[:8] or "研究", "综合")


def convert_full_report(slug):
    """读取 report.md 全文，转换为 flomo 兼容格式（只转格式，不改内容）。"""
    path = os.path.join(ROOT, "research", slug, "report.md")
    if not os.path.isfile(path):
        print(f"[错误] 未找到报告: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    out = []
    for line in raw.splitlines():
        s = line.rstrip()
        # 表头分隔行（|---|）跳过
        if re.match(r"^\s*\|[\s:\-|]+\|\s*$", s):
            continue
        # 表格行 → 列表
        m = re.match(r"^\s*\|(.+)\|\s*$", s)
        if m:
            cells = [c.strip() for c in m.group(1).split("|")]
            out.append("- " + " / ".join(cells))
            continue
        # 标题 → 加粗
        m = re.match(r"^(#{1,6})\s+(.+)$", s)
        if m:
            out.append(f"**{m.group(2).strip()}**")
            continue
        # 引用 → 正文
        if s.startswith(">"):
            out.append(s.lstrip("> ").strip())
            continue
        # 链接 → 文本（flomo 不支持链接语法）
        s2 = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", s)
        # 反引号 → 去掉
        s2 = s2.replace("`", "")
        out.append(s2)
    return "\n".join(out).strip()


def main():
    args = {"slug": None, "out": None}
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            args["out"] = argv[i + 1]
            i += 2
        else:
            i += 1
    slug = args["slug"]
    if not slug:
        print("用法: python tools/report_to_flomo.py --slug <slug> [--out <文件>]")
        sys.exit(1)

    title, domain = get_meta(slug)
    tag1, tag2 = pick_tags(domain)
    body = convert_full_report(slug)
    content = f"#知识基座 #{tag1} #{tag2}\n\n{body}"

    print("=" * 60)
    print(f"flomo 完整转换 | slug: {slug}")
    print(f"标题: {title}")
    print(f"领域: {domain or '未记录'} | 标签: #{tag1} #{tag2}")
    print(f"内容长度: {len(body)} 字符（完整报告，未截断）")
    print("=" * 60)
    print()
    print(content)

    if args["out"]:
        out_path = args["out"]
        if not os.path.isabs(out_path):
            out_path = os.path.join(ROOT, "research", slug, out_path)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        print(f"\n[已写] {out_path}")

    print("\n查重决策规则（参考 mynews relevance 判断）：")
    print("  relevance < 0.5  -> 直接新建 memo_create")
    print("  0.5 <= r < 0.9   -> 主题相近，人工判断（已有本报告则跳过，有增量则合并 update）")
    print("  relevance >= 0.9  -> 高相似，已存在则跳过，有新内容则 memo_update")


if __name__ == "__main__":
    main()
