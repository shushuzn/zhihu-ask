# -*- coding: utf-8 -*-
"""
多轮迭代研究工具（zhihu-ask 项目专用）

把"单轮研究"升级为"多轮迭代"：每完成一轮，带着上一轮未尽问题进入下一轮，逐轮提升报告质量。
问题清单由主代理手动编写（人工看报告中标注"仍无法核实/推算"的内容与口径缺口，整理成清晰条目），本工具只负责：
  1. 生成下一轮问题清单模板（写 round_notes.md，问题部分留空待人工填写）。
  2. 更新 .progress.json 的 round 记录（round + 1）。

用法：
    python tools/iter_research.py --slug <slug>              # 生成下一轮问题清单模板（当前轮+1）
    python tools/iter_research.py --slug <slug> --round 2     # 指定目标轮次（默认当前轮+1）

流程建议（与 SOP 附录 A 配套）：
  第 1 轮：research_start.py 启动 -> 阶段 2/3/4 产出 report
  第 2 轮：本工具生成问题清单模板 -> 人工填写未尽问题 -> 带着问题补检索/深化 -> 更新 report.md
  第 3 轮：同上，继续深化。一般 3 轮达到质量收敛。

说明：
- 报告路径：research/<slug>/report.md（每轮迭代直接在原 report.md 上更新，不创建 vN 版本文件）。
- 问题清单必须人工编写：自动提取的碎片句语义不清，人工整理才可靠。
"""

import sys
import os
import json
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS_FILE = ".progress.json"
ROUND_NOTES = "round_notes.md"


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
    return path


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
    # 迭代发生于阶段 4，说明阶段 1 已完成；旧进度文件可能缺 stage 键，此处自愈补齐
    if "stage" not in prog:
        prog["stage"] = "phase1_done"
    data["round"] = new_round
    data["round_updated"] = date.today().isoformat()
    with open(prog_path, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


def write_template(slug, cur_round, target_round):
    """生成问题清单模板：问题部分留空，由主代理手动填写。"""
    rdir = os.path.join(ROOT, "research", slug)
    notes_path = os.path.join(rdir, ROUND_NOTES)
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(f"# 第 {target_round} 轮研究问题清单\n\n")
        f.write(f"> 由主代理人工编写，基于第 {cur_round} 轮报告中标注'仍无法核实/推算'的内容整理，日期 {date.today().isoformat()}。\n\n")
        f.write("## 未解决/可深化的问题\n\n")
        f.write("（逐条填写，每条一个明确、可执行的问题。参考报告中：")
        f.write("哪些数据未取得一手来源、哪些结论依赖推断、哪些口径需澄清、哪些客观无法核实。)\n\n")
        f.write("1. \n")
        f.write("2. \n")
        f.write("3. \n\n")
        f.write("## 下一轮执行指引\n\n")
        f.write("1. 针对上述问题逐条补充检索（web_search / 公众号）。\n")
        f.write("2. 优先补一手来源；无法补足的标注\"仍无法核实\"后从问题清单移除。\n")
        f.write("3. 直接在 report.md 上更新（不创建 vN 版本文件），深化过程记录于 process_notes.md。\n")
    return notes_path


def main():
    args = parse_args(sys.argv[1:])
    slug = args["slug"]
    if not slug:
        print("用法: python tools/iter_research.py --slug <slug> [--round <N>]")
        sys.exit(1)

    cur_round = get_current_round(slug)
    target_round = args["round"] if args["round"] else cur_round + 1

    path = read_report(slug)
    if not path:
        print(f"[错误] {slug}: 未找到报告（research/{slug}/report.md）。请先完成第1轮产出报告。")
        sys.exit(1)

    print("=" * 60)
    print(f"多轮迭代研究 | slug: {slug}")
    print(f"当前轮次: {cur_round} -> 目标轮次: {target_round}")
    print(f"报告来源: {os.path.relpath(path, ROOT)}")
    print("=" * 60)

    notes_path = write_template(slug, cur_round, target_round)
    print(f"\n已生成问题清单模板: {os.path.relpath(notes_path, ROOT)}")
    print("  请人工打开并逐条填写未尽问题（参考报告中标注'仍无法核实/推算'的内容），不要自动提取。")

    update_round(slug, target_round)
    print(f"\n已更新轮次: .progress.json round = {target_round}")

    print("\n下一轮执行建议：")
    print("  1. 打开 round_notes.md，逐条填写未尽问题")
    print("  2. 补检索 -> 深化分析 -> 直接在 report.md 上更新（不创建 vN 版本文件）")
    print("  3. 全部完成后可再跑本工具进入第 {0} 轮，一般 3 轮收敛".format(target_round + 1))


if __name__ == "__main__":
    main()
