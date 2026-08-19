#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目模板与脚本的矛盾与废话检查

用户明确：检查对象是**项目自身的模板（templates/*.md）与脚本（tools/*.py）**，
不是报告正文。检测项目文件之间的自相矛盾与无信息量废话。

【硬伤】矛盾检测（项目文件间不一致，命中即阻断）：
1. **工具引用缺失**：docs/templates/skills 中引用的 `tools/xxx.py` 文件不存在
   （IMA_INTEGRATION 的"未实施"规划除外——引用处若标注"未实施/规划"则豁免）。
2. **通道清单漂移**：非 channel_state.py 的文件中残留旧通道表述（"通道 D"、
   "七通道"、"六通道（F/E/A/B/C/D）"、"F/E/A/B/C/D"）——通道清单单一真相源
   是 channel_state.py（F/E/A/B/C/P 六通道），其余文件出现旧表述即矛盾。
3. **模板占位符未实现**：templates/ 中 `{{...}}` 占位符若无 init_research.py
   的替换逻辑支持，且非"填写型占位符"（含中文说明文字）→ 矛盾（模板与生成器不符）。
4. **脚本 docstring 与 argparse 不一致**：tools/*.py 的 docstring 用法示例
   引用不存在的参数（如 docstring 写 `--xxx` 但 argparse 无该参数）。
5. **日期注解残留**：项目文件（tools/templates/docs/skills）中出现带日期的
   "修复/新增/优化/用户裁定/踩坑"等历史注释（IMA 数据快照豁免）。

【提示】废话检测（模板/脚本中的无信息量表述，默认同样阻断）：
6. **脚本注释自夸**：注释含"非常强大/高效便捷/极大提升/至关重要"等无信息量修饰。
7. **模板空话**：模板中含"请注意/务必/切记"但无具体内容的引导语。

用法：
  python tools/check_consistency.py                       # 检查全项目模板与脚本
  python tools/check_consistency.py --target tools        # 只查脚本
  python tools/check_consistency.py --target templates    # 只查模板
  python tools/check_consistency.py              # 默认严格阻断，提示级命中同样失败
"""

import argparse
import os
import re
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 通道单一真相源（与 channel_state 一致；导入避免硬编码漂移）
sys.path.insert(0, os.path.join(ROOT, "tools"))
import channel_state as cs

VALID_CHANNELS = set(cs.CHANNEL_ORDER)              # F/E/A/B/C/P
VALID_CHANNELS_STR = "/".join(cs.CHANNEL_ORDER)     # F/E/A/B/C/P

# 旧通道表述（应已全部迁移，残留即矛盾）
OBSOLETE_CHANNEL_PATTERNS = [
    (r"通道\s*D(?!\w)", "旧通道 D 表述（arxiv 已归入 P）"),
    (r"登记\s*D(?!\w)", "旧通道 D 登记（arxiv 已归入 P）"),
    (r"arxiv\s*D(?!\w)", "旧 arxiv D 表述（arxiv 已归入 P）"),
    (r"七通道", "七通道表述（现为六通道）"),
    (r"六通道（F/E/A/B/C/D）", "旧六通道清单（现为 F/E/A/B/C/P）"),
    (r"F/E/A/B/C/D(?:/P)?", "旧通道清单 F/E/A/B/C/D（现为 F/E/A/B/C/P）"),
    (r"F→E→A→B→C→D|F->E->A->B->C->D", "旧执行顺序（现为 F→E→A→B→C→P）"),
    (r"A–D|A-D", "旧 A–D 通道范围（现为 A/B/C/P）"),
    (r"A/B/C/D(?!\s*/?\s*P)", "旧通道范围 A/B/C/D（现为 A/B/C/P）"),
    (r"ABD", "旧 ABD 通道组合（现为 A/B/P）"),
    (r"通道 <F\|E\|A\|B\|C\|D", "mark_channel 旧通道参数示例"),
]

# 引用 tools/xxx.py 的模式
TOOL_REF_RE = re.compile(r"tools/([a-z_]+\.py)")

# flomo 查重对象：必须是「笔记」，不得再出现「报告」作为查重对象。
# flomo 查重对象必须是笔记；成品报告不上传 flomo。
FLOMO_NOTE_DEDUP_OLD = [
    (r"flomo 已有报告查重|flomo 已有报告", "flomo 查重对象应为笔记（成品报告不上传 flomo）"),
    (r"查重命中已有报告|复用已有报告|已有本报告完整版|已有本报告\)", "flomo 查重对象应为笔记（成品报告不上传 flomo）"),
    (r"本主题报告|同主题成品报告|查是否已有本报告", "flomo 查重对象应为笔记（成品报告不上传 flomo）"),
]

# 模板占位符
PLACEHOLDER_RE = re.compile(r"\{\{([^{}]+)\}\}")

# 脚本注释/文档废话
BANAL_RE = re.compile(
    r"(非常强大|高效便捷|极大提升|至关重要|非常有用|极其方便|易于使用|简单易懂|"
    r"功能完备|全面覆盖|性能卓越|表现优异|效果显著|功能强大)"
)


# ---------- 检查实现 ----------

def scan_files(target):
    """返回待检查文件列表（target: all/tools/templates/docs/skills）。"""
    files = []
    if target in ("all", "tools"):
        for f in sorted(os.listdir(os.path.join(ROOT, "tools"))):
            if f.endswith(".py"):
                files.append(os.path.join(ROOT, "tools", f))
    if target in ("all", "templates"):
        for f in sorted(os.listdir(os.path.join(ROOT, "templates"))):
            if f.endswith(".md"):
                files.append(os.path.join(ROOT, "templates", f))
    if target in ("all", "docs"):
        for f in sorted(os.listdir(os.path.join(ROOT, "docs"))):
            if f.endswith(".md"):
                files.append(os.path.join(ROOT, "docs", f))
    if target in ("all", "skills"):
        sk = os.path.join(ROOT, "skills", "zhihu-ask-research", "SKILL.md")
        if os.path.exists(sk):
            files.append(sk)
    return files


# 历史裁定的旧表述关键词（裁定已并入对应规则文档；涉及文档残留旧表述即矛盾）
# 格式：{"规则名": {"旧表述": ["旧表述正则/子串", ...], "涉及文件": ["文件名", ...]}}
LEGACY_PHRASE_PATTERNS = {
    "flomo 笔记可作素材但须国标来源": {
        "old": ["不作参考资料", "一律不作为参考", "仅作查重判断"],
        "files": ["SOP.md", "research_plan_TEMPLATE.md"],
    },
    "报告参考文献区禁止 LaTeX": {
        "old": [r"参考文献.*\$[^$]*\$"],
        "files": ["research_report_TEMPLATE.md"],
    },
    "arxiv 归入预印本聚合 P": {
        "old": [r"通道\s*D(?![（(]*(arxiv|已|于))"],
        "files": ["SOP.md", "TOOLS.md", "SKILL.md", "research_plan_TEMPLATE.md", "research_report_TEMPLATE.md"],
    },
}


def check_legacy_phrases(files):
    """硬伤：历史裁定的旧表述，在涉及文档中残留 → 与当前规则矛盾。

    flomo 素材规则矛盾（SOP 旧表述 vs SKILL 新裁定）暴露了
    "裁定分散、改裁漏同步"问题——本检查把旧表述同步机器化。
    """
    issues = []
    for ruling, spec in LEGACY_PHRASE_PATTERNS.items():
        for fp in files:
            base = os.path.basename(fp)
            if base not in spec["files"]:
                continue
            try:
                with open(fp, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            rel = os.path.relpath(fp, ROOT)
            for i, line in enumerate(lines, 1):
                for pat in spec["old"]:
                    if re.search(pat, line):
                        issues.append((i, "硬伤", f"改裁未同步（{ruling}）",
                                       f"{rel}: 残留旧表述「{line.strip()[:50]}」，文档只反映当前状态"))
                        break
    return issues


# 日期注解废话模式：项目文件中的"YYYY-MM-DD 修复/新增/用户裁定/踩坑"等历史注释
STALE_DATE_PATTERNS = [
    r"2026-\d{2}-\d{2}\s*用户(裁定|要求|严令|确定|改裁|进一步要求|第三轮要求|重申|二次指出|反馈)",
    r"用户(裁定|要求|严令|确定|改裁|进一步要求|第三轮要求|重申|二次指出|反馈)[（(]?\s*2026-",
    r"\(2026-\d{2}-\d{2}[^)]*用户[^)]*\)",
    r"2026-\d{2}-\d{2}\s*(?:用户硬规则|工具化|实测|加固|升级|核实|新增|固化|反复踩坑|起已弃用|起不再使用|续|修复|由串行改并行|优化|领域矩阵|严格化|改裁|重新评定|回归|扩展|改进|支持|实现|踩坑|缺陷回归)",
]
STALE_DATE_EXCLUDE = {"IMA_LIBRARIES.md", "health_check.py", "KEYWORDS.md"}


def check_stale_dates(files):
    """硬伤：项目文件中残留带日期的裁定/修复/优化/踩坑等历史注释。"""
    issues = []
    regexes = [re.compile(p) for p in STALE_DATE_PATTERNS]
    for fp in files:
        if os.path.basename(fp) in STALE_DATE_EXCLUDE:
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        try:
            rel = os.path.relpath(fp, ROOT)
        except ValueError:
            rel = os.path.basename(fp)
        for i, line in enumerate(lines, 1):
            if any(r.search(line) for r in regexes):
                issues.append((i, "硬伤", "日期注解残留", f"{rel}: {line.strip()[:60]}"))
    return issues


def check_tool_refs(files):
    """硬伤：docs/templates/skills 中引用的 tools/xxx.py 不存在。

    豁免：引用处同行含"未实施/规划/待实现/方案 B"标注（如 IMA_INTEGRATION 的规划）。
    """
    issues = []
    tools_dir = os.path.join(ROOT, "tools")
    existing = {f for f in os.listdir(tools_dir) if f.endswith(".py")}
    for fp in files:
        if fp.startswith(os.path.join(ROOT, "tools")):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for m in TOOL_REF_RE.finditer(line):
                tool = m.group(1)
                if tool in existing:
                    continue
                # 豁免：同行或前 15 行内含"未实施/规划/待实现/方案 B"标注
                ctx = "\n".join(lines[max(0, i - 16):i])
                if any(k in ctx for k in ("未实施", "规划", "待实现", "方案 B", "尚未实现")):
                    continue
                try:
                    rel = os.path.relpath(fp, ROOT)
                except ValueError:
                    rel = os.path.basename(fp)  # 跨盘（C:/D:）时退化为文件名
                issues.append((i, "硬伤", "工具引用缺失", f"{rel}: 引用 tools/{tool} 但文件不存在"))
    return issues


def check_obsolete_channels(files):
    """硬伤：非 channel_state.py 的文件残留旧通道表述。

    """
    issues = []
    for fp in files:
        # 检查器自身豁免（规则定义文本含旧通道表述字样，属说明性）
        if os.path.basename(fp) in ("check_consistency.py", "channel_state.py", "KEYWORDS.md"):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        try:
            rel = os.path.relpath(fp, ROOT)
        except ValueError:
            rel = os.path.basename(fp)  # 跨盘（C:/D:）时退化为文件名
        for i, line in enumerate(lines, 1):
            for pat, label in OBSOLETE_CHANNEL_PATTERNS:
                if re.search(pat, line):
                    issues.append((i, "硬伤", label,
                                   f"{rel}: {line.strip()[:60]}（通道单一真相源为 channel_state.py: {VALID_CHANNELS_STR}）"))
                    break
    return issues


def check_flomo_note_dedup_phrasing(files):
    """硬伤：项目文件把 flomo 查重对象写成「报告」，应为「笔记」。

    成品报告不上传 flomo；F 通道 memo_search 查的是本主题已有笔记。
    此检查防止模板/文档/技能再次出现“已有报告查重/本主题报告”等旧表述。
    """
    issues = []
    for fp in files:
        # 检查器自身豁免（规则定义文本含旧表述字样，属说明性）
        if os.path.basename(fp) in ("check_consistency.py",):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        try:
            rel = os.path.relpath(fp, ROOT)
        except ValueError:
            rel = os.path.basename(fp)  # 跨盘（C:/D:）时退化为文件名
        for i, line in enumerate(lines, 1):
            for pat, label in FLOMO_NOTE_DEDUP_OLD:
                if re.search(pat, line):
                    issues.append((i, "硬伤", label,
                                   f"{rel}: {line.strip()[:60]}（flomo 查重对象应为笔记）"))
                    break
    return issues


def check_placeholder_supported(files):
    """硬伤：templates/ 的 {{占位符}} 若非生成器支持且非填写型 → 矛盾。

    填写型占位符：模板设计上由 agent 研究时填写的字段——特征是出现在
    research_plan_TEMPLATE（问题界定/关键词等研究计划字段），或键名本身有明确
    语义（如 {{slug}}、{{URL}}、{{X}} 等单字段）。生成器支持的占位符：
    init_research.py 的全部 replace/替换键。
    """
    # 生成器支持的占位符：init_research 源码中的 {{...}} 与 replace("{{...}}", ...)
    try:
        import inspect
        import init_research as ir
        src = inspect.getsource(ir)
        supported = set(re.findall(r"\{\{[^{}]*\}\}", src))
        for m in re.finditer(r'replace\("(\{\{[^{}]*\}\})"', src):
            supported.add(m.group(1))
    except Exception:
        supported = {"{{知乎问题完整标题}}", "{{YYYY-MM-DD}}", "{{进行中 / 已完成}}",
                     "{{...}}", "{{topic-slug}}", "{{领域档位}}"}
    issues = []
    for fp in files:
        if not fp.startswith(os.path.join(ROOT, "templates")):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        rel = os.path.relpath(fp, ROOT)
        for i, line in enumerate(lines, 1):
            for m in PLACEHOLDER_RE.finditer(line):
                ph = m.group(0)
                if ph in supported:
                    continue
                inner = m.group(1)
                # 填写型：含中文说明、或已知单字段键（slug/URL/X/关键词等）
                if re.search(r"[\u4e00-\u9fff]", inner):
                    continue
                if re.fullmatch(r"(slug|URL|X|关键词|topic_slug|topic-slug|date|domain|query)", inner):
                    continue
                issues.append((i, "硬伤", "占位符未实现",
                               f"{rel}: {ph} 无 init_research 替换且非填写型占位符"))
    return issues


def check_argparse_docstring(files):
    """硬伤：脚本 docstring 用法示例引用不存在的 argparse 参数。"""
    issues = []
    for fp in files:
        if not fp.startswith(os.path.join(ROOT, "tools")):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        # argparse 参数
        args = set(re.findall(r'add_argument\("(--[a-z-]+)', content))
        if not args:
            continue
        rel = os.path.relpath(fp, ROOT)
        # docstring 区（前三引号内）中的 --xxx 用法
        m = re.match(r'"""(.*?)"""', content, re.S)
        if not m:
            continue
        doc = m.group(1)
        for used in re.findall(r"(--[a-z-]+)", doc):
            if used not in args:
                # 豁免：说明性文本中的参数（如 check_consistency 的 --offline 等）
                issues.append((i := 1, "提示", "docstring 参数未实现",
                               f"{rel}: docstring 引用 {used} 但 argparse 未定义"))
    return issues


def check_banal(files):
    """提示：脚本注释/模板中的无信息量修饰（废话）。"""
    issues = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        try:
            rel = os.path.relpath(fp, ROOT)
        except ValueError:
            rel = os.path.basename(fp)  # 跨盘（C:/D:）时退化为文件名
        for i, line in enumerate(lines, 1):
            # 词表定义行豁免：工具/文档中的检测词表（引号包裹、正则模式、BANAL_RE 定义）
            if re.search(r'"[^"]*(至关重要|非常强大|高效便捷)[^"]*"|至关重要[）\)]|'
                         r'(非常强大|高效便捷|至关重要|功能完备)\||BANAL_RE|'
                         r'极大提升\||装饰词（非常|至关重要等）', line):
                continue
            for m in BANAL_RE.finditer(line):
                issues.append((i, "提示", "无信息量修饰",
                               f"{rel}: 「{m.group(1)}」（直接陈述事实，去掉空话修饰）"))
                break
    return issues


# ---------- 入口 ----------

def check(target="all"):
    files = scan_files(target)
    hard, warn = [], []
    hard += check_legacy_phrases(files)
    hard += check_tool_refs(files)
    hard += check_obsolete_channels(files)
    hard += check_flomo_note_dedup_phrasing(files)
    hard += check_stale_dates(files)
    hard += check_placeholder_supported(files)
    warn += check_argparse_docstring(files)
    warn += check_banal(files)
    return hard, warn


def main():
    ap = argparse.ArgumentParser(description="项目模板与脚本的矛盾与废话检查")
    ap.add_argument("--target", choices=["all", "tools", "templates", "docs", "skills"], default="all",
                    help="检查范围（默认 all）")
    args = ap.parse_args()

    hard, warn = check(args.target)
    print(f"项目模板与脚本检查: {args.target}")
    print("=" * 60)
    if not hard and not warn:
        print("全部通过：未检出项目文件间的矛盾与废话。")
    else:
        if hard:
            print(f"[硬伤] {len(hard)} 处（命中即阻断）")
            for lineno, level, title, detail in hard:
                print(f"  行{lineno} {title}: {detail}")
        if warn:
            print(f"[提示] {len(warn)} 处（启发式，默认同样阻断）")
            for lineno, level, title, detail in warn:
                print(f"  行{lineno} {title}: {detail}")
    if hard or warn:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
