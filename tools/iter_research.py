# -*- coding: utf-8 -*-
"""
多轮迭代研究工具（zhihu-ask 项目专用）

把"单轮研究"升级为"多轮迭代"：每完成一轮，带着上一轮未尽问题进入下一轮，逐轮提升报告质量。
本工具负责两件事：
  1. 进入下一轮前，读取上一轮报告，从【局限/未尽问题/可深化点】生成下一轮的问题清单（写 round_notes.md）。
  2. 更新 .progress.json 的 round 记录（round + 1）。

用法：
    python tools/iter_research.py --slug <slug>              # 读取上一轮报告，生成下一轮问题清单
    python tools/iter_research.py --slug <slug> --round 2     # 指定目标轮次（默认当前轮+1）

流程建议（与 SOP 附录 A 配套）：
  第 1 轮：research_start.py 启动 -> 阶段 2/3/4 产出 report v1
  第 2 轮：本工具生成问题清单 -> 带着问题补检索/深化 -> 产出 report v2
  第 3 轮：同上，产出 report v3。一般 3 轮达到质量收敛。

说明：
- 报告路径：research/<slug>/report.md（每轮迭代直接在原 report.md 上更新，不创建 vN 版本文件）。
- 本工具只生成"问题清单"与更新轮次，不替代主代理的分析与写作。
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
PROGRESS_FILE = ".progress.json"
ROUND_NOTES = "round_notes.md"

# 从报告中提取"未尽问题"的章节标题（下一轮要深化的来源）
# 注意：不含"问题"，否则会误匹配"研究问题"标题，把框架描述当未尽问题。
LIMIT_SECTIONS = ["局限", "待深化", "未尽", "后续核实", "口径", "存疑"]

# 提取"可深化点"的提示词（出现在报告正文中）
DEEPEN_MARKERS = ["待核实", "未取得", "无法核实", "未见", "推断", "推算", "需进一步", "可补充", "建议后续"]


def parse_args(argv):
    args = {"slug": None, "round": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--round" and i + 1 < len(argv):
            args["round"] = int(argv[i + 1])
            i += 2
        else:
            i += 1
    return args


def read_report(slug):
    """读取当前报告：research/<slug>/report.md。"""
    rdir = os.path.join(ROOT, "research", slug)
    path = os.path.join(rdir, "report.md")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return path, f.read()


def extract_questions(report_text):
    """从报告提取下一轮问题：局限章节 + 可深化标记句。
    排除"研究问题/分析框架/数据来源分级"等框架描述小节（这些不是未尽问题）。"""
    questions = []
    seen = set()
    # 不应视为"未尽问题"的框架小节标题
    EXCLUDE_SECTIONS = ["研究问题", "分析框架", "数据来源分级", "关键事实", "主要发现"]
    # 框架描述行：以这些词开头（含"推断/推算"但非未尽问题）
    FRAME_LEAD = ["研究问题", "分析框架", "数据来源分级", "执行摘要", "结论", "参考文献", "局限与后续", "对策建议"]
    # 非问题性质的段落引导词（如"数据局限：""该拆解仅说明"）
    NON_QUESTION_LEAD = ["数据局限", "推断部分", "该拆解仅", "本报告仅", "结论是", "需要注意的是"]

    lines = report_text.splitlines()
    in_limit = False
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            # 是否进入"局限类"章节（真未尽问题来源）
            in_limit = any(marker in s for marker in LIMIT_SECTIONS)
            continue
        if in_limit and s and not s.startswith("|"):
            body = s.lstrip("-*•0123456789.、 ")
            # 排除框架描述行
            if any(body.startswith("**" + lead) or body.startswith(lead + "**")
                   or body.startswith(lead + "：") for lead in FRAME_LEAD):
                continue
            # 排除非问题性质的段落引导（如"数据局限：xxx"，应拆成其中的①②）
            if any(body.startswith(lead) for lead in NON_QUESTION_LEAD):
                continue
            # 跳过"已在正文处理"的说明性内容（非待解决问题）
            if "已在正文处理" in body or body.startswith("口径说明"):
                continue
            clean = body.replace("**", "").strip()
            _add_split_questions(clean, questions, seen)
    return questions


def _add_split_questions(text, questions, seen):
    """把长段文本按 ①/②/；/。/？ 拆成单条问题，避免整段大块。
    仅保留有"未尽"语义的片段；用子串包含去重避免同一问题的不同表述重复出现。"""
    parts = re.split(r"[；;。]+|①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩", text)
    for p in parts:
        p = p.strip().replace("**", "")
        if not p or len(p) < 6:
            continue
        if not any(kw in p for kw in ["核实", "待确认", "未取得", "无法", "口径", "推断", "推算",
                                      "数据", "确认", "待核实", "需进一步", "可补充", "回溯", "验证"]):
            continue
        # 子串去重：若新片段被已收录问题的关键短语包含（或反之），视为同一问题，跳过
        if _is_duplicate(p, seen):
            continue
        questions.append(p)
        seen.add(p)


def _is_duplicate(candidate, seen):
    """判断候选片段是否与已收录问题高度重复。
    规则：候选与某已收录问题共享超过一个"主题关键词"时视为重复。
    主题关键词：常住/户籍/口径/富有/收入/宅基地/租金/财产/开店/外来/东西部/差距 等。
    避免"常住人口口径"在不同段落被反复提取为多个问题。"""
    if candidate in seen:
        return True
    TOPIC_KW = ["常住", "户籍", "口径", "富有", "收入", "宅基地", "租金", "财产",
                "开店", "外来", "东西部", "差距", "城乡", "人均", "财产净"]
    c_kw = {kw for kw in TOPIC_KW if kw in candidate}
    for s in seen:
        s_kw = {kw for kw in TOPIC_KW if kw in s}
        # 共享 ≥2 个主题关键词即视为同一话题的重复
        overlap = c_kw & s_kw
        if len(overlap) >= 2:
            return True
    return False


def get_current_round(slug):
    prog_path = os.path.join(ROOT, "research", slug, PROGRESS_FILE)
    if os.path.exists(prog_path):
        with open(prog_path, "r", encoding="utf-8") as f:
            prog = json.load(f)
        return int(prog.get("data", {}).get("round", 1))
    return 1


def update_round(slug, new_round):
    prog_path = os.path.join(ROOT, "research", slug, PROGRESS_FILE)
    prog = {}
    if os.path.exists(prog_path):
        with open(prog_path, "r", encoding="utf-8") as f:
            prog = json.load(f)
    data = prog.setdefault("data", {})
    data["round"] = new_round
    data["round_updated"] = date.today().isoformat()
    with open(prog_path, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


def main():
    args = parse_args(sys.argv[1:])
    slug = args["slug"]
    if not slug:
        print("用法: python tools/iter_research.py --slug <slug> [--round <N>]")
        sys.exit(1)

    cur_round = get_current_round(slug)
    target_round = args["round"] if args["round"] else cur_round + 1

    result = read_report(slug)
    if not result:
        print(f"[错误] {slug}: 未找到报告（research/{slug}/report.md）。请先完成第1轮产出报告。")
        sys.exit(1)

    path, text = result
    questions = extract_questions(text)

    print("=" * 60)
    print(f"多轮迭代研究 | slug: {slug}")
    print(f"当前轮次: {cur_round} -> 目标轮次: {target_round}")
    print(f"报告来源: {os.path.relpath(path, ROOT)}")
    print("=" * 60)

    if not questions:
        print("\n[提示] 未从报告中提取到明确的未尽问题。")
        print("  建议：人工审视报告，补充下一轮要深化的方向后，用 --round 手动指定。")
        questions = ["（人工补充：本轮未自动提取到未尽问题，请审视报告局限性后手动填写）"]

    # 写 round_notes.md
    rdir = os.path.join(ROOT, "research", slug)
    notes_path = os.path.join(rdir, ROUND_NOTES)
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(f"# 第 {target_round} 轮研究问题清单\n\n")
        f.write(f"> 由 iter_research.py 基于第 {cur_round} 轮报告自动提取，日期 {date.today().isoformat()}。\n\n")
        f.write("## 第 N 轮未解决/可深化的问题\n\n")
        for i, q in enumerate(questions, 1):
            f.write(f"{i}. {q}\n")
        f.write("\n## 下一轮执行指引\n\n")
        f.write("1. 针对上述问题逐条补充检索（web_search / 公众号）。\n")
        f.write("2. 优先补一手来源；无法补足的标注\"仍无法核实\"。\n")
        f.write("3. 直接在 report.md 上更新（不创建 vN 版本文件），保留深化过程记录于 process_notes.md。\n")

    print(f"\n已生成下一轮问题清单: {os.path.relpath(notes_path, ROOT)}")
    print(f"共 {len(questions)} 个待深化问题：")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")

    update_round(slug, target_round)
    print(f"\n已更新轮次: .progress.json round = {target_round}")

    print("\n下一轮执行建议：")
    print("  1. 打开 round_notes.md，逐条处理问题")
    print("  2. 补检索 -> 深化分析 -> 直接在 report.md 上更新（不创建 vN 版本文件）")
    print("  3. 全部完成后可再跑本工具进入第 {0} 轮，一般 3 轮收敛".format(target_round + 1))


if __name__ == "__main__":
    main()
