
"""
通道完成登记工具（zhihu-ask 项目专用）

将六通道（F/E/A/B/C/P）的执行状态以结构化形式写入
research/<slug>/.progress.json 的 data.channels_done，供
  python tools/check_progress.py --slug <slug> --require report_channels
做「声明态 ⊕ 证据」双向交叉校验（落报告纪律的条目级细化）。

结构化声明替代旧版扁平字符串列表 channels=[...]（该字段从未被任何门禁读取，形同虚设）；
本工具写入的 channels_done 才会被 report_channels 门禁真正校验。

用法：
  # 通道已执行且有素材
  python tools/mark_channel.py --slug <slug> --channel A --status done
  # 通道已执行但零命中（须有 gathered 文件或 note 说明）
  python tools/mark_channel.py --slug <slug> --channel P --status empty --note "通道 P 无有效素材"
  # 通道不适用/连接器未连接
  python tools/mark_channel.py --slug <slug> --channel E --status skip --note "ima 连接器未连接"
  # 领域数据源（C）一次登记三项
  python tools/mark_channel.py --slug <slug> --channel C --status done --note "企查查+通达信+智慧芽"
  # 查看当前登记
  python tools/mark_channel.py --slug <slug> --list

status 取值：
  done  —— 通道已执行且产出有效素材（须有对应 gathered_*.md ≥200 字节；F 仅需 note）
  empty —— 通道已执行但零命中（须有 gathered 文件或 note 含「无有效素材/无命中」）
  skip  —— 通道不适用/连接器未连接（须有 note 说明原因）

约束：本工具仅登记状态，不替代落盘 gathered 文件；声明 done 但对应文件缺失时会提示，
但不阻断登记（先登记、后落盘属正常顺序）。最终以 check_progress --require report_channels 为准。
"""

import sys
import os
import json
import argparse

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import channel_state as cs

CHANNEL_ORDER = cs.CHANNEL_ORDER
CHANNEL_NAMES = cs.CHANNEL_NAMES
VALID_STATUS = cs.VALID_STATUS


def do_list(slug):
    path, prog = cs.load(slug)
    if prog is None:
        print(f"[错误] 未找到 research/{slug}/.progress.json，请先运行 research_start.py")
        return 1
    cd = (prog.get("data") or {}).get("channels_done") or {}
    if not cd:
        print(f"[状态] {slug}: 尚未登记 channels_done（旧版 channels 列表不被门禁读取）。")
        print("        建议用 mark_channel 登记六通道执行态，否则 report_channels 门禁仅走文件启发式。")
        return 0
    env_unconf = set(cs.env_unconfigured_channels())
    print(f"通道登记（{slug}）：")
    for ch in CHANNEL_ORDER:
        e = cd.get(ch)
        tag = "（环境级）" if ch in env_unconf else ""
        if isinstance(e, dict):
            print(f"  {ch} [{CHANNEL_NAMES.get(ch, ch)}]{tag}: {e.get('status','?')}  note={e.get('note','')!r}")
        else:
            print(f"  {ch} [{CHANNEL_NAMES.get(ch, ch)}]: {e!r}（旧式值，建议用 mark_channel 重写为结构化）")
    return 0


def do_mark(slug, channel, status, note):
    channel = channel.upper()
    if channel not in CHANNEL_ORDER:
        print(f"[错误] 非法通道 {channel!r}（仅允许 {','.join(CHANNEL_ORDER)}）")
        return 1
    if status not in VALID_STATUS:
        print(f"[错误] 非法 status {status!r}（仅允许 {','.join(VALID_STATUS)}）")
        return 1

    path, prog = cs.load(slug)
    if prog is None:
        print(f"[错误] 未找到 research/{slug}/.progress.json，请先运行 research_start.py")
        return 1

    ok = cs.mark(slug, channel, status, note)
    if not ok:
        print("[错误] 登记失败（.progress.json 状态异常）")
        return 1

    print(f"[已登记] 通道 {channel} [{CHANNEL_NAMES.get(channel, channel)}]: status={status} note={(note or '')!r}")

    # done 但对应素材文件缺失 → 提示（不阻断；多文件通道任一存在即可）
    if status == "done":
        files = cs.files_for(channel)
        if files:
            missing = [fn for fn in files
                       if not os.path.exists(os.path.join(cs.ROOT, "research", slug, fn))
                       or os.path.getsize(os.path.join(cs.ROOT, "research", slug, fn)) < 200]
            if missing:
                print(f"  [提示] 声明 done 但 {missing} 缺失或过小；请先落盘素材后再过关 report_channels 门禁。")
    print(f"  校验：python tools/check_progress.py --slug {slug} --require report_channels")
    return 0


def do_all_skip(slug, note):
    """一键把未登记的通道登记为 skip（E 未连接/P 不适用/F 无主题等常见场景）。

    已登记的通道保留原状；批量 skip 的 note 统一为指定说明（默认"不适用/未连接"）。
    """
    path, prog = cs.load(slug)
    if prog is None:
        print(f"[错误] 未找到 research/{slug}/.progress.json，请先运行 research_start.py")
        return 1
    cd = (prog.get("data") or {}).get("channels_done") or {}
    applied = []
    for ch in CHANNEL_ORDER:
        if ch in cd:
            continue
        cs.mark(slug, ch, "skip", note=note or f"通道 {ch} 不适用/未连接（--all-skip）")
        applied.append(ch)
    if applied:
        print(f"[已登记] 未声明通道批量 skip: {', '.join(applied)}（note={note or '不适用/未连接'!r}）")
    else:
        print("[状态] 所有通道均已登记，无需批量 skip。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="通道完成登记（落报告纪律条目级）")
    ap.add_argument("--slug", required=True, help="研究报告 slug")
    ap.add_argument("--channel", help="通道字母 F/E/A/B/C/P")
    ap.add_argument("--status", help="done / empty / skip")
    ap.add_argument("--note", help="状态说明（empty/skip 必填；done 可选）")
    ap.add_argument("--list", action="store_true", help="查看当前登记")
    ap.add_argument("--all-skip", action="store_true", help="批量把未登记通道登记为 skip（配合 --note 说明原因）")
    args = ap.parse_args()

    if args.list:
        sys.exit(do_list(args.slug))
    if args.all_skip:
        sys.exit(do_all_skip(args.slug, args.note))
    if not args.channel or not args.status:
        print("ERROR: 需 --channel 与 --status，或 --list，或 --all-skip")
        sys.exit(1)
    sys.exit(do_mark(args.slug, args.channel, args.status, args.note))


if __name__ == "__main__":
    main()
