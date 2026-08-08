# -*- coding: utf-8 -*-
"""
研究报告结构校验工具（zhihu-ask 项目专用）

校验 report.md 章节结构完整性，防止插入章节时覆盖/错位/重复/跳号
（实战中多次发生的 Edit 覆盖标题问题——人工发现成本高，工具化强制）：
  1. 小节编号连续：### 2.1 → 2.2 → … 无重复、无跳号（如 2.8 后直接 2.9 但缺 2.7 之间内容错位）
  2. 顶层章节完整：## 一、研究问题与框架 / ## 二、关键事实与数据 / ## 三、量化测算
     / ## 四、多维分析 / ## 五、结论 均存在（参考文献也属顶层章节）
  3. ## 参考文献 存在且含 [标题](url) 条目（可溯源硬性要求）
  4. 无模板占位符 {{...}} 残留

用法：
    python tools/check_report_structure.py --file research/<slug>/report.md

输出：全部通过退出码 0；检出问题退出码 1 并列出位置。
"""

import sys
import os
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REQUIRED_TOP = ["一、研究问题与框架", "二、关键事实与数据", "三、量化测算", "四、多维分析", "五、结论"]
REQUIRED_REF = "## 参考文献"


def main():
    argv = sys.argv[1:]
    filepath = None
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if not filepath or not os.path.exists(filepath):
        print("用法: python tools/check_report_structure.py --file <report.md>")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    issues = []

    # 1) 小节编号连续（### N.M）
    sub_nums = []
    for i, line in enumerate(lines, 1):
        m = re.match(r"^###\s+(\d+)\.(\d+)\s+", line)
        if m:
            sub_nums.append((int(m.group(1)), int(m.group(2)), i))
    for idx in range(1, len(sub_nums)):
        p_ch, p_num, p_line = sub_nums[idx - 1]
        c_ch, c_num, c_line = sub_nums[idx]
        if p_ch == c_ch:
            if c_num == p_num:
                issues.append((c_line, f"小节编号重复: {p_ch}.{p_num} 出现两次"))
            elif c_num != p_num + 1:
                issues.append((c_line, f"小节编号跳号: {p_ch}.{p_num} → {p_ch}.{c_num}（期望 {p_ch}.{p_num + 1}）"))

    # 2) 顶层章节完整
    top_found = set()
    for line in lines:
        for req in REQUIRED_TOP:
            if re.match(rf"^##\s+{re.escape(req)}", line.strip()):
                top_found.add(req)
    for req in REQUIRED_TOP:
        if req not in top_found:
            issues.append((1, f"缺少顶层章节: ## {req}"))

    # 3) 参考文献存在且含链接条目
    ref_idx = next((i for i, line in enumerate(lines) if line.strip() == REQUIRED_REF), None)
    if ref_idx is None:
        issues.append((1, f"缺少参考文献章节: {REQUIRED_REF}"))
    else:
        ref_lines = [l for l in lines[ref_idx + 1:] if l.strip()]
        link_count = sum(1 for l in ref_lines if re.search(r"\[[^\]]+\]\([^)]+\)", l))
        if link_count == 0:
            issues.append((ref_idx + 1, "参考文献章节为空或条目非 [标题](url) 链接格式"))

    # 4) 模板占位符残留
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\{\{[^{}]*\}\}", line):
            issues.append((i, f"模板占位符残留: {m.group(0)}"))

    print("=" * 60)
    print(f"报告结构检查: {filepath}")
    print("=" * 60)

    if not issues:
        print("全部通过：小节编号连续、顶层章节完整、参考文献合规、无占位符残留。")
        sys.exit(0)

    seen = {}
    for line_no, msg in issues:
        seen.setdefault(msg, []).append(line_no)
    for msg, lns in seen.items():
        print(f"  行{lns[0]}{'/' + str(lns[-1]) if len(lns) > 1 else ''}: {msg}")
    print("\n提示：存在结构问题（可能由插入章节时覆盖标题导致），请先修复再交付。")
    sys.exit(1)


if __name__ == "__main__":
    main()
