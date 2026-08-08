# -*- coding: utf-8 -*-
"""
阶段进度校验工具（zhihu-ask 项目专用）

读取 research/<slug>/.progress.json，校验前置阶段是否完成，供阶段 2-4 进入前确认。
对应 SOP 附录 A 的「输出未达校验即阻塞」规则：进入后续阶段前必须先确认前置阶段产出有效。

用法：
    python tools/check_progress.py --slug deepseek-price-motivation
    python tools/check_progress.py --slug deepseek-price-motivation --require phase1_done

说明：
- 不传 --require 时，展示当前进度并给出建议下一步。
- 传 --require 时，校验指定阶段是否已完成；未完成则退出码 1（阻塞提示）。
- 当前已知阶段键：phase1_done（阶段0初始化+阶段1通道A/通道Z完成）。
"""

import sys
import os
import json

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args(argv):
    args = {"slug": None, "require": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--require" and i + 1 < len(argv):
            args["require"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args


def main():
    args = parse_args(sys.argv[1:])
    slug = args["slug"]
    if not slug:
        print("用法: python tools/check_progress.py --slug <slug> [--require <stage>]")
        sys.exit(1)

    prog_path = os.path.join(ROOT, "research", slug, ".progress.json")
    if not os.path.exists(prog_path):
        print(f"[状态] {slug}: 未找到进度文件。说明该研究尚未完成阶段0/1，请先运行 research_start.py。")
        sys.exit(1)

    with open(prog_path, "r", encoding="utf-8") as f:
        prog = json.load(f)

    stage = prog.get("stage", "unknown")
    data = prog.get("data", {})

    if args["require"]:
        # 校验指定前置阶段是否完成
        expected = {"phase1_done"}
        if args["require"] in expected and stage == args["require"]:
            print(f"[通过] {slug}: 前置阶段 {args['require']} 已完成，可进入下一阶段。")
            sys.exit(0)
        else:
            print(f"[阻塞] {slug}: 前置阶段 {args['require']} 未完成（当前 {stage}），请先完成再继续。")
            sys.exit(1)

    # 展示模式
    print(f"[状态] {slug}: 当前阶段 = {stage}")
    if data:
        print(f"  问题: {data.get('question', '?')}")
        print(f"  公众号素材库: {'有' if data.get('has_wechat_material') else '无'}")
        print(f"  知乎素材库: {'有' if data.get('has_zhihu_material') else '无'}")
        print(f"  公众号关键词数: {data.get('keyword_count', 0)}")
        print(f"  知乎关键词数: {data.get('zhihu_keyword_count', 0)}")
        print(f"  当前迭代轮次: {data.get('round', 1)}")
    if stage == "phase1_done":
        print("  建议下一步: 进入阶段2（多视角收集）→ 阶段3（交叉验证量化）→ 阶段4（产出+沉淀）")
    sys.exit(0)


if __name__ == "__main__":
    main()
