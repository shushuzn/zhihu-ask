# -*- coding: utf-8 -*-
"""
阶段进度校验工具（zhihu-ask 项目专用）

读取 research/<slug>/.progress.json，校验前置阶段是否完成，供阶段 2-4 进入前确认。
对应 SOP 附录 A 的「输出未达校验即阻塞」规则：进入后续阶段前必须先确认前置阶段产出有效。

用法：
    python tools/check_progress.py --slug deepseek-price-motivation
    python tools/check_progress.py --slug deepseek-price-motivation --require phase1_done
    python tools/check_progress.py --slug deepseek-price-motivation --require_round 10
    python tools/check_progress.py --slug deepseek-price-motivation --require_round auto

说明：
- 不传 --require 时，展示当前进度并给出建议下一步。
- 传 --require 时，校验指定阶段是否已完成；未完成则退出码 1（阻塞提示）。
- 传 --require_round N 时，校验迭代轮次是否 ≥N（对应 SOP A.8 领域最低轮次：
  财政/宏观/金融 ≥10 轮，其他 ≥3 轮）；未达标则退出码 1（阻塞提示）。
- --require_round auto 按 .progress.json 的 domain 字段自动判定最低轮次
  （财政/宏观/金融投资 → 10，其他 → 3；domain 缺失时回退 3）。
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

# SOP A.8 最低迭代轮次（2026-08-09 起所有领域统一 ≥10，与 docs/SOP.md 轮次表保持一致）
MIN_ROUNDS = 10


def domain_min_round(domain):
    """返回最低迭代轮次：所有领域统一 ≥10（用户要求"都改成 10 轮以上"）。"""
    return MIN_ROUNDS


def parse_args(argv):
    args = {"slug": None, "require": None, "require_round": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--require" and i + 1 < len(argv):
            args["require"] = argv[i + 1]
            i += 2
        elif argv[i] == "--require_round" and i + 1 < len(argv):
            args["require_round"] = argv[i + 1]  # 数字或 "auto"
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

    if args["require_round"] is not None:
        # 校验迭代轮次是否达标（SOP A.8 领域最低轮次）
        try:
            cur_round = int(data.get("round", 0) or 0)
        except (TypeError, ValueError):
            cur_round = 0
        req_val = args["require_round"]
        if str(req_val).strip().lower() == "auto":
            domain = data.get("domain", "")
            req_round = domain_min_round(domain)
            src = f"按领域「{domain or '未记录'}」自动判定"
        else:
            try:
                req_round = int(req_val)
            except (TypeError, ValueError):
                print(f"[错误] --require_round 须为数字或 auto（收到: {req_val}）")
                sys.exit(1)
            src = "显式指定"
        if cur_round >= req_round:
            print(f"[通过] {slug}: 迭代轮次 {cur_round} ≥ 要求 {req_round}（{src}），达标。")
            sys.exit(0)
        print(f"[阻塞] {slug}: 迭代轮次 {cur_round} < 要求 {req_round}（{src}，SOP A.8 领域最低轮次），请继续迭代。")
        sys.exit(1)

    if args["require"]:
        # 校验指定前置阶段是否完成
        expected = {"phase1_done"}
        if args["require"] in expected:
            done = stage == args["require"]
            if not done and args["require"] == "phase1_done":
                # 兼容旧进度文件：无 stage 键但已迭代（round>=1）说明阶段 1 已完成
                try:
                    cur_round = int(data.get("round", 0) or 0)
                except (TypeError, ValueError):
                    cur_round = 0
                done = cur_round >= 1
            if done:
                print(f"[通过] {slug}: 前置阶段 {args['require']} 已完成，可进入下一阶段。")
                sys.exit(0)
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
