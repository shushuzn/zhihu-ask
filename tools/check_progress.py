
"""
阶段进度校验工具（zhihu-ask 项目专用）

读取 research/<slug>/.progress.json，校验前置阶段是否完成，供阶段 2-4 进入前确认。
对应 SOP 附录 A 的「输出未达校验即阻塞」规则：进入后续阶段前必须先确认前置阶段产出有效。

用法：
    python tools/check_progress.py --slug deepseek-price-motivation
    python tools/check_progress.py --slug deepseek-price-motivation --require phase1_done
    python tools/check_progress.py --slug deepseek-price-motivation --require report_channels
    python tools/check_progress.py --slug deepseek-price-motivation --require_round 5
    python tools/check_progress.py --slug deepseek-price-motivation --require_round auto

说明：
- 不传 --require 时，展示当前进度并给出建议下一步。
- 传 --require 时，校验指定阶段是否已完成；未完成则退出码 1（阻塞提示）。
- 传 --require_round N 时，校验迭代轮次是否 ≥N（对应 SOP A.8 领域最低轮次：
  默认统一 ≥1 轮）；未达标则退出码 1（阻塞提示）。
- --require_round auto 按 .progress.json 的 domain 字段自动判定最低轮次
  （默认统一 → 1；domain 缺失时同样为 1）。
- --require report_channels 校验「落报告纪律」：结构化的双向交叉校验。
  若 research/<slug>/.progress.json 的 data.channels_done 已登记六通道执行态（done/empty/skip），
  则双向核对「声明态 ⊕ 证据」：正向（声明→须有对应 gathered 文件/note）、
  反向（存在的 gathered 文件→须被登记）、完整性（六通道均须声明）、report.md 承接。
  若未登记 channels_done，则回退旧版文件启发式（向后兼容，不破坏既有成品）。
  检出项需人工确认内容级落地。用 mark_channel.py 登记通道完成态。
- 当前已知阶段键：phase1_done（阶段0初始化+阶段1通道A完成）、report_channels（落报告纪律）。
"""

import sys
import os
import json
import glob
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import channel_state as cs

# 通道清单统一由 channel_state 维护（避免双份维护漂移）
CHANNEL_ORDER = cs.CHANNEL_ORDER
CHANNEL_NAMES = cs.CHANNEL_NAMES

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MIN_ROUNDS = 1

def domain_min_round(domain):
    """返回最低迭代轮次：默认统一 ≥1 轮（默认一轮，除非有内容无法一轮解决才追加）。"""
    return MIN_ROUNDS

# 落报告纪律：已执行通道（有 gathered_*.md 素材）的硬数据须落进 report.md 正文。
# F 通道（flomo 查重）无 gathered 文件，单独处理，不在此校验。
# 证据文件→通道映射统一由 channel_state.file_to_channel() 推导，
# 含 P 通道多文件展开：gathered_arxiv.md 与 gathered_preprints.md 均属通道 P
CHANNEL_FILE_MAP = cs.file_to_channel()
MIN_MATERIAL_BYTES = 200   # 素材文件低于此视为无效/空
MIN_REPORT_BYTES = 600     # report.md 低于此视为未生成/明显缺内容

# 结构化通道登记（落报告纪律条目级细化）：
# .progress.json 的 data.channels_done 以 {字母: {status, note}} 形式声明六通道执行态，
# 本工具据此做「声明态 ⊕ 证据」双向交叉校验，替代旧版仅靠文件启发式的单向前向检查。
# CHANNEL_ORDER/NAMES/FILE 由 channel_state 统一维护。
# 内容通道 → 对应 gathered 文件（F 无文件，仅 note 记录）
CHANNEL_FILE = cs.CHANNEL_FILE
VALID_STATUS = ("done", "empty", "skip")  # 已执行有素材 / 已执行零命中 / 不适用或跳过


def discover_executed_channels(slug_dir):
    """返回已执行且有有效素材的通道列表：[(letter, name, path, size)]。"""
    results = []
    for fname, (letter, name) in CHANNEL_FILE_MAP.items():
        fpath = os.path.join(slug_dir, fname)
        if os.path.exists(fpath):
            size = os.path.getsize(fpath)
            if size >= MIN_MATERIAL_BYTES:
                results.append((letter, name, fpath, size))
    return results


def load_channels_done(slug_dir):
    """从 .progress.json 读取结构化的 channels_done。非 dict 或缺失返回 {}。"""
    prog_path = os.path.join(slug_dir, ".progress.json")
    if not os.path.exists(prog_path):
        return {}
    try:
        with open(prog_path, "r", encoding="utf-8") as f:
            prog = json.load(f)
    except (OSError, ValueError):
        return {}
    cd = (prog.get("data") or {}).get("channels_done") or {}
    if not isinstance(cd, dict):
        return {}  # 兼容旧版扁平字符串列表 channels=[...]，忽略并走文件启发式
    return cd


def _check_file_heuristic(slug_dir, slug):
    """旧版文件启发式：已执行通道有素材但 report.md 缺失/过小则阻塞。
    仅在 .progress.json 无结构化 channels_done 时作为向后兼容回退。"""
    report_path = os.path.join(slug_dir, "report.md")
    report_exists = os.path.exists(report_path)
    report_size = os.path.getsize(report_path) if report_exists else 0
    channels = discover_executed_channels(slug_dir)
    if not channels:
        print(f"[提醒] {slug}: 未检测到任何通道素材文件（gathered_*.md），且未登记 channels_done；"
              f"无法校验「落报告纪律」，请确认通道是否执行或补登 mark_channel。")
        return 0
    blocked = []
    for letter, name, fpath, size in channels:
        if not report_exists or report_size < MIN_REPORT_BYTES:
            blocked.append((letter, name))
            print(f"[阻塞] 通道 {letter}（{name}）已执行且有素材（{os.path.basename(fpath)}，{size} 字节），"
                  f"但 report.md 缺失或过小（{report_size} 字节），硬数据未落正文。")
        else:
            print(f"[通过] 通道 {letter}（{name}）素材已落盘，report.md 已生成（{report_size} 字节）；内容级核对需人工确认。")
    if blocked:
        print(f"[阻塞] {slug}: 以上 {len(blocked)} 个通道存在「执行但未落报告」风险，"
              f"请核对 report.md 正文是否已写入各通道硬数据（C 通道最易遗漏）。")
        return 1
    print(f"[通过] {slug}: 已执行通道的素材均有 report.md 承接；内容级核对为启发式，需人工确认。")
    return 0


def check_report_channels(slug_dir, slug):
    """落报告纪律校验（条目级结构化）。

    若 .progress.json 含 data.channels_done（结构化声明），则做「声明态 ⊕ 证据」
    双向交叉校验：
      正向：声明的每个通道 → 须有对应证据（done 须有 gathered 文件≥200字节；
            empty 须有文件或 note 含"无有效素材"；skip 须有 note；F done 须有 note）。
      反向：存在的 gathered 文件 → 须被 channels_done 登记为 done/empty。
      完整性：结构化模式下六通道（F/E/A/B/C/P）均须声明。
    若无结构化声明，则回退到旧版文件启发式（向后兼容，不破坏既有成品）。
    """
    cd = load_channels_done(slug_dir)
    if not cd:
        return _check_file_heuristic(slug_dir, slug)

    report_path = os.path.join(slug_dir, "report.md")
    report_size = os.path.getsize(report_path) if os.path.exists(report_path) else 0
    blocked = []

    # 1) 完整性：六通道均须声明（缺声明即视为未完成登记）。
    #    环境级未配置连接器的通道（ima E / 领域连接器 C）由初始化自动登记 skip，
    #    跨研究共享、无需逐篇手动检查；即便缺失也视为已满足（连接器未接入不阻塞）。
    env_unconf = set(cs.env_unconfigured_channels())
    for ch in CHANNEL_ORDER:
        if ch not in cd:
            if ch in env_unconf:
                continue
            blocked.append((ch, f"channels_done 未声明通道 {ch}（请用 mark_channel 登记其执行状态）"))

    # 1b) P0 通道须实际执行（领域矩阵工具化后校验）：
    #     按领域矩阵，P0 通道若登记 skip 且 note 说明"不适用/未连接"之外的原因 → 阻塞。
    #     （P0=该领域必做且最先，缺失须补足或记录原因；P2 通道 skip 正常）
    try:
        import channel_state as _cs
        domain = ""
        pf = os.path.join(slug_dir, ".progress.json")
        if os.path.exists(pf):
            try:
                with open(pf, encoding="utf-8") as _f:
                    domain = ((json.load(_f).get("data") or {}).get("domain") or "")
            except (OSError, ValueError):
                pass
        dtype = _cs.classify_domain(domain)
        p0_channels = [ch for ch, p, _ in _cs.channel_plan(dtype) if p == "P0"]
        for ch in p0_channels:
            entry = cd.get(ch)
            if not isinstance(entry, dict):
                continue
            status = (entry.get("status") or "").strip().lower()
            note = (entry.get("note") or "").strip()
            if status == "skip":
                ok_reason = any(k in note for k in ("未连接", "不适用", "无生态", "未配置",
                                                     "无主题", "无本主题", "跳过"))
                if not ok_reason:
                    blocked.append((ch, f"领域「{dtype}」中 {ch} 为 P0 必做通道，但登记 skip"
                                         f"（note={note!r}）——P0 须实际执行或说明原因（未连接/不适用）"))
    except Exception:
        pass

    # 2) 正向：声明态 → 证据
    for ch, entry in cd.items():
        if ch not in CHANNEL_ORDER:
            blocked.append((ch, f"未知通道键 {ch}（仅允许 {','.join(CHANNEL_ORDER)}）"))
            continue
        if isinstance(entry, dict):
            status = (entry.get("status") or "").strip().lower()
            note = (entry.get("note") or "").strip()
        else:
            # 兼容旧式字符串值："E(skip:未连接)"
            s = str(entry)
            status = "skip" if s.lower().startswith("skip") else "done"
            note = s
        if status not in VALID_STATUS:
            blocked.append((ch, f"status 非法: {status!r}（应为 done/empty/skip）"))
            continue
        fname = CHANNEL_FILE.get(ch)
        # 多素材文件通道（P 通道含 gathered_arxiv.md 与 gathered_preprints.md，
        # 任一存在即满足证据要求）
        multi_files = cs.CHANNEL_FILE_MULTI.get(ch)
        if status == "done":
            if fname or multi_files:
                ok = False
                if fname:
                    fp = os.path.join(slug_dir, fname)
                    ok = os.path.exists(fp) and os.path.getsize(fp) >= MIN_MATERIAL_BYTES
                if not ok and multi_files:
                    ok = any(
                        os.path.exists(os.path.join(slug_dir, fn)) and
                        os.path.getsize(os.path.join(slug_dir, fn)) >= MIN_MATERIAL_BYTES
                        for fn in multi_files)
                if not ok:
                    shown = fname or "/".join(multi_files)
                    blocked.append((ch, f"声明 done 但 {shown} 均缺失/过小（<{MIN_MATERIAL_BYTES}字节）"))
            if not note and ch == "F":
                blocked.append((ch, "F 通道声明 done 但缺 note（请说明查重结论）"))
            if ch == "F" and note and not re.search(r"memo_search|flomo_search", note):
                blocked.append((ch, "F 通道声明 done 但 note 未记录实际 flomo 查重工具调用"
                                     "（须含 memo_search/flomo_search 证据）"))
        elif status == "empty":
            if fname or multi_files:
                fp_exists = False
                if fname:
                    fp = os.path.join(slug_dir, fname)
                    fp_exists = os.path.exists(fp)
                if not fp_exists and multi_files:
                    fp_exists = any(os.path.exists(os.path.join(slug_dir, fn)) for fn in multi_files)
                recorded = fp_exists or any(
                    k in note for k in ("无有效素材", "无命中", "无结果", "无对应"))
                if not recorded:
                    shown = fname or "/".join(multi_files)
                    blocked.append((ch, f"声明 empty 但既无 {shown} 也无 note 说明（须记录无命中）"))
            elif not note:
                blocked.append((ch, "声明 empty 但缺 note 说明（须记录无命中）"))
        elif status == "skip":
            if not note:
                blocked.append((ch, "声明 skip 但缺 note（须说明跳过原因）"))

    # 3) 反向：证据 → 声明（有素材文件但 channels_done 未登记）
    for fname, (letter, name) in CHANNEL_FILE_MAP.items():
        fp = os.path.join(slug_dir, fname)
        if os.path.exists(fp) and os.path.getsize(fp) >= MIN_MATERIAL_BYTES:
            if letter not in cd:
                blocked.append((letter, f"存在 {fname}（{os.path.getsize(fp)}字节）但 channels_done 未登记"))

    # 4) report.md 承接（落报告硬门禁，与已执行通道证据一致）
    if report_size < MIN_REPORT_BYTES:
        blocked.append(("report", f"report.md 缺失或过小（{report_size}字节），硬数据未落正文"))

    if blocked:
        for ch, msg in blocked:
            print(f"[阻塞] 通道 {ch}：{msg}")
        print(f"[阻塞] {slug}: 以上 {len(blocked)} 项违反「落报告纪律/通道完成登记」，请修正 channels_done 与素材。")
        return 1
    print(f"[通过] {slug}: channels_done 六通道声明完整且与证据一致，落报告纪律达标。")
    return 0

def parse_args(argv):
    args = {"slug": None, "require": None, "require_round": None}
    i = 0
    while i < len(argv):
        if argv[i] == "--slug" and i + 1 < len(argv):
            args["slug"] = argv[i + 1]
            i += 2
        elif argv[i] == "--file" and i + 1 < len(argv):
            # 与 quality_check / check_report_structure 参数口径统一：
            # 允许传 research/<slug>/report.md，反推目录名为 slug。
            args["slug"] = os.path.basename(os.path.dirname(os.path.abspath(argv[i + 1])))
            i += 2
        elif argv[i] == "--require" and i + 1 < len(argv):
            args["require"] = argv[i + 1]
            i += 2
        elif argv[i] == "--require_round" and i + 1 < len(argv):
            args["require_round"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return args

def main():
    args = parse_args(sys.argv[1:])
    slug = args["slug"]
    if not slug:
        print("用法: python tools/check_progress.py (--slug <slug> | --file <report.md>) [--require <stage>]")
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

        if args["require"] == "report_channels":
            # 落报告纪律：已执行通道的素材是否落进了 report.md 正文（启发式校验）。
            rc = check_report_channels(os.path.join(ROOT, "research", slug), slug)
            sys.exit(rc)

        expected = {"phase1_done"}
        if args["require"] in expected:
            done = stage == args["require"]
            if not done and args["require"] == "phase1_done":

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

    print(f"[状态] {slug}: 当前阶段 = {stage}")
    if data:
        print(f"  问题: {data.get('question', '?')}")
        print(f"  公众号素材库: {'有' if data.get('has_wechat_material') else '无'}")
        print(f"  公众号关键词数: {data.get('keyword_count', 0)}")
        print(f"  当前迭代轮次: {data.get('round', 1)}")
    if stage == "phase1_done":
        print("  建议下一步: 进入阶段2（多视角收集）→ 阶段3（交叉验证量化）→ 阶段4（产出+沉淀）")
    sys.exit(0)

if __name__ == "__main__":
    main()
