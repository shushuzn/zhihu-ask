# -*- coding: utf-8 -*-
"""
正文质量自动检查工具（zhihu-ask 项目专用）

把报告模板/CHECKLIST 中的"去 AI 味 + 立场中立"检查落地为自动扫描：
  1. 立场词检测：我认为/我的判断/结论很硬/显然/可见/证明/应该/不该/建议/最好/总之
  2. 框架词检测：先说结论/总结一下/综上所述/不难发现/总而言之
  3. 评价词检测：太猛/很差/厉害/离谱/糟糕/完美/惊人（评价性形容词）
  4. 形式检测：感叹号、反问句（？+语气）、无来源数字（粗略启发式）

用法：
    python tools/quality_check.py --file research/<slug>/report.md
    python tools/quality_check.py --file research/<slug>/report.md --verbose

说明：
- 扫描范围为正文（跳过"数据与来源备查"及之后的来源区）。
- 检测到违规词时退出码 1，全部通过退出码 0。
- 检查项为启发式规则，命中后需人工确认是否真正违规（如"建议"在"不构成投资建议"中是合法用法）。
"""

import sys
import os
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 立场词（出现即标记，需人工确认）
STANCE_WORDS = [
    "我认为", "我的判断", "我的看法", "结论很硬", "显然", "可见", "证明",
    "应该", "不该", "最好", "总之", "所以结论是", "说白了", "实话实说",
    "我们", "我建议", "我认",
]

# 框架词（AI 味标志）
FRAMEWORK_WORDS = [
    "先说结论", "总结一下", "综上所述", "总而言之", "不难发现",
    "值得注意的是", "总的来说", "一方面", "另一方面", "其一", "其二",
]

# 评价词（评价性形容词/副词）
EVALUATIVE_WORDS = [
    "太猛", "很差", "非常差", "厉害", "离谱", "糟糕", "完美", "惊人",
    "令人震惊", "极其", "极其重要", "重大突破", "巨大", "显著提升",
    "狠狠", "暴跌", "暴涨",
]

# 来源区起点（跳过其后的内容）
SOURCE_MARKERS = ["## 数据与来源备查", "## 参考文献", "### 数据与来源备查", "### 参考文献", "数据与来源备查"]

# 参考文献区起点
REF_MARKERS = ["## 参考文献", "### 参考文献"]

# 参考文献行不允许出现的标注（数据分级只在正文，参考文献为纯链接列表）
REF_BAD_LABELS = ["一手", "二手", "推断"]


def scan_body(filepath):
    """读取回答，返回正文部分（来源区之前）。"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    cutoff = len(content)
    for marker in SOURCE_MARKERS:
        idx = content.find(marker)
        if idx != -1:
            cutoff = min(cutoff, idx)
    return content[:cutoff], content


def check_exclamation(body):
    """检查感叹号与反问句。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        if "！" in line or "!" in line:
            issues.append((i, "感叹号", line.strip()[:60]))
        # 反问句：含"？"且句首带"难道/难道不/怎么不/凭什么"
        if re.search(r"(难道|凭什么|怎么会|怎么不).*？", line):
            issues.append((i, "反问句", line.strip()[:60]))
    return issues


def check_words(body, word_list, label):
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        for w in word_list:
            if w in line:
                issues.append((i, label, w, line.strip()[:60]))
    return issues


def check_references(full):
    """检查参考文献区：链接条目行尾不得带"一手/二手/推断"等分级标注（数据分级只在正文）。
    仅针对参考文献区（从 ## 参考文献 起到文末）内的 [标题](url) 行。"""
    issues = []
    start = None
    for marker in REF_MARKERS:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        return issues
    section = full[start:]
    for i, line in enumerate(section.splitlines(), 1):
        stripped = line.strip()
        if not re.search(r"\[[^\]]+\]\([^)]+\)", stripped):
            continue
        # 链接闭合后是否还跟有分级标注，例如 "(url) — 一手"
        tail = re.sub(r"^.*\]\([^)]*\)", "", stripped)
        for label in REF_BAD_LABELS:
            if f"— {label}" in tail or f"：{label}" in tail:
                issues.append((i, "参考文献标注", f"链接后带 [{label}]", stripped[:60]))
                break
    return issues


def check_unsourced_numbers(body):
    """启发式：行内出现"约 X 元/万亿/亿/万"等数字表述但同行无来源字样。
    跳过表格行（| 开头）与列表项（- 开头且带来源括注），因表格/列表数字通常在行内或表前已说明来源。
    来源特征词含数据分级标注（一手/二手/计算/估算），与项目"每个数字标数据级别"约定配套。"""
    source_words = (
        r"(来源|据|数据|报道|测算|推算|口径|官方|媒体|实测|参考|定价|备查|"
        r"一手|二手|计算|估算|预算|决算|公布|披露|统计)"
    )
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            continue
        if re.search(r"[约|超过|高达]\s*[\d.]+", line):
            if not re.search(source_words, line):
                issues.append((i, "无来源数字(待确认)", stripped[:60]))
    return issues


def check_placeholders(body):
    """检测模板占位符未替换残留（{{...}}），防止模板内容漏发。"""
    issues = []
    for i, line in enumerate(body.splitlines(), 1):
        for m in re.finditer(r"\{\{[^{}]*\}\}", line):
            issues.append((i, "模板占位符", m.group(0), line.strip()[:60]))
    return issues


def check_structure(body, full):
    """结构完整性检查：
    1. 必须存在参考文献章节且含至少 1 条 [标题](url) 链接（SOP 硬性要求：纯事实报告可溯源）。
    2. 正文不得残留未决占位标记（TODO/待补充/待填写/此处填写 等；"仍无法核实"为合法口径标注，不在此列）。
    """
    issues = []
    start = None
    for marker in REF_MARKERS:
        idx = full.find(marker)
        if idx != -1:
            start = idx
            break
    if start is None:
        issues.append((1, "结构完整性", "缺少参考文献章节（## 参考文献），报告无法溯源", ""))
    else:
        section = full[start:]
        ref_lines = [ln for ln in section.splitlines() if ln.strip()]
        link_count = sum(1 for ln in ref_lines if re.search(r"\[[^\]]+\]\([^)]+\)", ln))
        if link_count == 0:
            issues.append((1, "结构完整性", "参考文献章节为空或条目非 [标题](url) 链接格式", ""))
    for i, line in enumerate(body.splitlines(), 1):
        if re.search(r"(TODO|FIXME|待补充|待填写|待填|此处填写)", line):
            issues.append((i, "未决标记", "待补充/TODO 类残留", line.strip()[:60]))
    return issues


def main():
    argv = sys.argv[1:]
    filepath = None
    verbose = False
    if "--file" in argv:
        idx = argv.index("--file")
        if idx + 1 < len(argv):
            filepath = argv[idx + 1]
    if "--verbose" in argv:
        verbose = True

    if not filepath or not os.path.exists(filepath):
        print("用法: python tools/quality_check.py --file <回答文件> [--verbose]")
        sys.exit(1)

    body, full = scan_body(filepath)
    if not body.strip():
        print(f"[跳过] {filepath}: 未找到正文（可能为空或全为来源区）")
        sys.exit(0)

    all_issues = []
    all_issues += check_words(body, STANCE_WORDS, "立场词")
    all_issues += check_words(body, FRAMEWORK_WORDS, "框架词")
    all_issues += check_words(body, EVALUATIVE_WORDS, "评价词")
    all_issues += check_exclamation(body)
    all_issues += check_unsourced_numbers(body)
    all_issues += check_placeholders(body)
    all_issues += check_references(full)
    all_issues += check_structure(body, full)

    print("=" * 60)
    print(f"正文质量自动检查: {filepath}")
    print("=" * 60)

    if not all_issues:
        print("全部通过：未检测到立场词/框架词/评价词/感叹号/参考文献标注。")
        print("说明：数字溯源与逻辑终审仍需人工复核。")
        sys.exit(0)

    by_type = {}
    for item in all_issues:
        by_type.setdefault(item[1], []).append(item)

    for label, items in by_type.items():
        print(f"\n[{label}] {len(items)} 处")
        for item in items:
            line_no = item[0]
            extra = item[2] if len(item) > 2 else ""
            ctx = item[-1]
            print(f"  行{line_no}: {ctx}")
            if verbose:
                print(f"    -> 命中: {extra}")

    print("\n提示：命中项为启发式检出，需人工确认是否真正违规（如\"不构成投资建议\"中的\"建议\"为合法用法）。")
    print("退出码 1（存在待确认项）。")
    sys.exit(1)


if __name__ == "__main__":
    main()
