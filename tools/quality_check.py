"""正文质量自动检查工具（zhihu-ask 项目专用）。

原单文件超 800 行，已按检查主题拆分为 tools/qc_*.py 子模块；
本文件作为 facade 聚合所有 check_* 并保留 CLI 入口（resolve_target / main）。
检查逻辑本身见各 qc_* 子模块。
"""
import sys
import os
import re
try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.qc_common import *
from tools.qc_stance import *
from tools.qc_title import *
from tools.qc_ref import *
from tools.qc_conclusion import *
from tools.qc_structure import *
from tools.qc_math import *
from tools.qc_image import *
from tools.check_latex_syntax import check_latex_syntax

try:
    from tools.report_target import resolve_report_target as resolve_target
except ModuleNotFoundError:
    from report_target import resolve_report_target as resolve_target  # 被测导入时 tools 不在包路径

def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    filepath = resolve_target(argv, "quality_check.py", " [--verbose]")
    note_mode = is_note_file(filepath)

    body, full = scan_body(filepath, note_mode=note_mode)
    if not body.strip():
        print(f"[跳过] {filepath}: 未找到正文（可能为空或全为来源区）")
        sys.exit(0)

    all_issues = []
    all_issues += check_words(body, STANCE_WORDS, "立场词")
    all_issues += check_words(body, FRAMEWORK_WORDS, "框架词")
    all_issues += check_words(body, EVALUATIVE_WORDS, "评价词")
    if note_mode:
        # 笔记模式（笔记用 Unicode、报告用 LaTeX）：
        # 笔记是内部研究记录（flomo 私人知识库），非发布成品，跳过面向报告成品的
        # 规范检查——标题/结论/小节/图片/LaTeX 公式规则不适用笔记；过程性字样
        # （笔记记录检索过程）、元话语自称（笔记引论文的"本文/前作"）、感叹号
        # （Unicode 公式中 k! 阶乘无 $ 保护易误报）均为笔记常态，一并跳过。
        # 标题禁止用 * 与 # 标记（flomo 上传质检要求，独立于报告标题检查规则）。
        # 笔记仅首行 tag 行允许 #，大小标题一律纯文本，禁止 #/##/### 与 * 标记。
        all_issues += check_title_asterisk(body)
        all_issues += check_title_hash(body)
        # 非规定字段（来源/概念等）一律禁止——来源只能以 GB/T 条目进「参考文献:」区
        all_issues += check_note_forbidden_fields(body)
        # 参考文献条目与正文 [n] 引注须一一对应（不能少、不能多）
        all_issues += check_citation_correspondence(full, note_mode=True)
    else:
        all_issues += check_exclamation(body)
        all_issues += check_process_words(body)
        all_issues += check_impl_residue(body)
        all_issues += check_meta_discourse(body)
        all_issues += check_title_paren(body)
        all_issues += check_title_len(body)
        all_issues += check_empty_section_title(body)
        all_issues += check_math_formula(body)
        all_issues += check_latex_syntax(body)
        all_issues += check_conclusion_len(full)
        all_issues += check_conclusion_style(full)
        all_issues += check_cross_ref(body)
        all_issues += check_caption_sequence(body)
        all_issues += check_cover_ban(body)
        all_issues += check_image_continuity(body)
        all_issues += check_fact_section_budget(body)
        # 段落长度限制（每段 ≤4-5 行 / 单段 ≤300 字符建议分点）是报告发布规则
        # （知乎扫读友好），笔记为内部研究素材、文末有整篇来源区，不适用——仅在报告模式检查。
        all_issues += check_paragraph_len(body)
        all_issues += check_para_points_eligible(body)
    all_issues += check_unsourced_numbers(body, full)
    all_issues += check_placeholders(body)
    all_issues += check_turn_pattern(body)
    all_issues += check_ai_phrases(body)
    all_issues += check_judgment_hints(body)
    all_issues += check_internal_refs(body)
    # Also check full content for flomo URLs in reference section
    all_issues += check_internal_refs(full)
    all_issues += check_grade_paren(body)
    all_issues += check_evidence_grade(body)
    all_issues += check_stock_info(body)
    all_issues += check_translation_voice(body)
    all_issues += check_subjectless_openers(body)
    all_issues += check_source_attribution(body)
    all_issues += check_references(full, note_mode=note_mode)
    # 参考文献区禁止 LaTeX（报告与笔记均适用——GB/T 著录为纯文本格式）
    all_issues += check_ref_latex_ban(full, note_mode=note_mode)
    all_issues += check_structure(body, full, note_mode=note_mode)

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
