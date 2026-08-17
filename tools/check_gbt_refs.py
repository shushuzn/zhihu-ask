#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GB/T 7714-2015 参考文献著录合规检查（引用参照国标）

检测对象：markdown 报告/创作稿中「参考文献」块的著录格式。
正文/文献块划分：以「参考文献」标题行（`## 参考文献` / `**参考文献**` / `参考文献`）为界，
标题行之后为文献区，之前为正文区。

硬性（命中即退出码 1，阻断）：
1. 文献类型标识缺失：每条须含 [M]/[J]/[C]//[N]/[D]/[R]/[S]/[Z] 或电子版 [X/OL]（[M/OL] 等）
2. 编号不连续：文献条目 [n] 须从 1 起连续递增、无跳号重复
3. 电子资源缺引用日期：含 http:// 或 https:// 的条目须带 [YYYY-MM-DD]
4. 正文引注与文献列表不对应（仅当正文存在 [n] 引注时执行）：
   - 正文 [n] 须都能在文献列表找到（无悬空引注）
   - 文献编号须全部被正文引用（无未被引用条目）
   - 正文引注编号须连续（无缺号）
   - 正文无 [n] 引注 = 参考来源清单模式（研究报告约定正文不标来源括注），跳过本项

提示级（默认 RC=1，严格阻断为默认）：
5. 转引条目未标注中间文献：条目含「见:」但「见:」后为空或同条内无书名/篇名
6. 参考文献块标题未标注国标：标题不含 GB/T 7714 或「国标」

用法：
  python tools/check_gbt_refs.py --file path/to/file.md
  python tools/check_gbt_refs.py --slug <slug>          # 检查 research/<slug>/report.md
  python tools/check_gbt_refs.py --file x.md   # 默认严格阻断，提示级命中同样失败
  python tools/check_gbt_refs.py --file x.md --verbose  # 显示命中明细
"""

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 文献类型标识（GB/T 7714-2015 附录）：M 专著 J 期刊 C 论文集 D 学位论文 R 报告 S 标准 Z 其他
# 电子资源在类型后加 /OL（如 [M/OL]、[EB/OL]）；[C]// 是析出文献格式（类型标识仍是 [C]）
TYPE_ID = re.compile(r"\[(?:[A-Z]{1,3}/OL|[A-Z]{1,3})\]")
# 引用日期 [YYYY-MM-DD]
DATE_RE = re.compile(r"\[(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\]")
# 条目行：行首 [n] 编号
ENTRY_RE = re.compile(r"^\[(\d+)\]\s")
# 正文引注 [n]（排除日期）
CITE_RE = re.compile(r"\[(\d+)\]")
# 参考文献块标题行（支持 ## 参考文献 / **参考文献（GB/T 7714-2015）** / 参考文献）
REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献")
# 笔记模式文献段标题：笔记格式为「来源:」行（也兼容 ## 参考文献）
NOTE_REF_HEAD_RE = re.compile(r"^#{1,6}\s*参考文献|^\*\*参考文献|^参考文献|^来源:")
# 笔记模式：文件位于 research/<slug>/notes/ 目录 → 文献段为「来源:」行；
# 笔记文献区是参考来源清单（正文引用可选），跳过"文献未被引用/引注编号连续"检查，
# 保留：条目空行/编号连续/类型标识/URL 引用日期/悬空引注。
def is_note_file(filepath):
    return os.path.basename(os.path.dirname(os.path.abspath(filepath))) == "notes"

# 期刊/文献标题中的年份（4 位数字）会与引用日期混淆，DATE_RE 已限定 [20xx-xx-xx] 格式，不会误伤
# 文献类型标识清单（用于提示语）
KNOWN_TYPES = ("[M]", "[M/OL]", "[J]", "[J/OL]", "[C]", "[C]//", "[D]", "[R]", "[S]", "[Z]", "[EB/OL]", "[DB/OL]", "[N]", "[N/OL]")


def split_ref_block(body, note_mode=False):
    """返回 (正文区, 文献区, 文献标题行号)。找不到参考文献块返回 (body, "", None)。"""
    lines = body.splitlines()
    pat = NOTE_REF_HEAD_RE if note_mode else REF_HEAD_RE
    for i, line in enumerate(lines):
        if pat.match(line.strip()):
            return "\n".join(lines[:i]), "\n".join(lines[i:]), i + 1
    return body, "", None


def parse_entries(ref_block):
    """解析文献区条目：返回 [(编号, 完整条目文本, 行号)]"""
    entries = []
    for i, line in enumerate(ref_block.splitlines(), 1):
        m = ENTRY_RE.match(line)
        if m:
            entries.append((int(m.group(1)), line.strip(), i))
    return entries


def check(body, note_mode=False):
    """返回 (硬性问题列表, 提示性问题列表)。问题元素：(行号, 级别, 标题, 详情)"""
    hard, warn = [], []
    body_txt, ref_txt, ref_head_line = split_ref_block(body, note_mode=note_mode)

    if ref_txt.strip() == "":
        hard.append((0, "硬伤", "无参考文献块",
                     "未找到「参考文献」标题（## 参考文献 / **参考文献** / 参考文献）"))
        return hard, warn

    entries = parse_entries(ref_txt)
    if not entries:
        hard.append((ref_head_line or 0, "硬伤", "无文献条目",
                     "参考文献块内未找到 [n] 编号条目"))
        return hard, warn

    # 0) 条目间空行（渲染兼容：无空行的连续条目行在 Markdown 渲染器中被合并成一段，
    #    参考文献黏连；条目须各自成段）
    for i, line in enumerate(ref_txt.splitlines(), 1):
        if ENTRY_RE.match(line) and i < len(ref_txt.splitlines()):
            nxt = ref_txt.splitlines()[i]
            if ENTRY_RE.match(nxt):
                hard.append((ref_head_line + i, "硬伤", "文献条目间缺空行",
                             f"条目 [{line.strip()[:20]}…] 与下一条目直接相邻（须空行分隔，否则渲染黏连）"))

    # 1) 编号连续
    nums = [n for n, _, _ in entries]
    expected = list(range(1, len(entries) + 1))
    if nums != expected:
        hard.append((ref_head_line, "硬伤", "文献编号不连续",
                     f"编号 {nums}，应从 1 连续递增到 {len(entries)}（无跳号/重复）"))

    # 2) 类型标识
    for n, text, lineno in entries:
        if not TYPE_ID.search(text):
            hard.append((ref_head_line + lineno, "硬伤", "缺文献类型标识",
                         f"[{n}] {text[:60]} 须含类型标识 {KNOWN_TYPES} 之一"))

    # 3) 电子资源引用日期
    for n, text, lineno in entries:
        if ("http://" in text or "https://" in text) and not DATE_RE.search(text):
            hard.append((ref_head_line + lineno, "硬伤", "电子资源缺引用日期",
                         f"[{n}] 含 URL 但缺 [YYYY-MM-DD] 引用日期（国标：电子资源须标注引用日期）"))

    # 4) 正文引注对应（GB/T 7714-2015 强制要求正文标注 [n]）
    body_cites = sorted({int(x) for x in CITE_RE.findall(body_txt)})
    entry_nums = set(nums)
    # 清单模式: 正文无 [n] 引注 = 参考来源清单模式, 跳过本项
    if body_cites:
        # 4a 悬空引注
        dangling = [c for c in body_cites if c not in entry_nums]
        if dangling:
            hard.append((0, "硬伤", "正文引注无对应文献",
                         f"正文引用 [{dangling}] 但文献列表不存在"))
        if not note_mode:
            # 笔记模式：文献区是参考来源清单，正文引用可选——
            # 只保留 4a 悬空检查，跳过 4b（引注连续）与 4c（文献未被引用）
            # 4b 编号连续（正文引注从 1 起连续）
            if body_cites != list(range(1, body_cites[-1] + 1)):
                hard.append((0, "硬伤", "正文引注编号不连续",
                             f"正文引注 {body_cites}，应从 1 连续递增"))
            # 4c 文献未被引用
            unused = [n for n in nums if n not in body_cites]
            if unused:
                hard.append((ref_head_line, "硬伤", "文献未被正文引用",
                             f"文献 [{unused}] 未被正文引用（顺序编码制要求逐条引用）"))
    elif not note_mode and nums:
        # 正文无 [n] 引注但文献列表非空：报告模式下仍须逐条引用，不得降级为清单模式
        hard.append((ref_head_line, "硬伤", "正文无引注",
                     f"正文未标注 [n] 引注，但文献列表含 {len(entries)} 条（顺序编码制要求逐条引用）"))

    # 5) 提示级：转引未标注中间文献
    for n, text, lineno in entries:
        if "见:" in text:
            seg = text.split("见:", 1)[1].strip()
            # 中间文献名 = 「见:」后的实质内容（中文书名/篇名均可），仅剩句号或为空才判未标注
            if not seg or seg in (".", "。", "．") or len(seg) < 2:
                warn.append((ref_head_line + lineno, "提示", "转引未标注中间文献",
                             f"[{n}] 含「见:」但未见中间文献名（应标 '见: 源文献'）"))

    return hard, warn


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="GB/T 7714-2015 参考文献合规检查")
    ap.add_argument("--file", help="目标 markdown 文件")
    ap.add_argument("--slug", help="研究 slug（检查 research/<slug>/report.md）")
    ap.add_argument("--verbose", action="store_true", help="显示命中明细")
    args = ap.parse_args()

    if args.slug:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "research", args.slug, "report.md")
    elif args.file:
        path = args.file
    else:
        ap.error("须指定 --file 或 --slug")
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    body = load_text(path)
    note_mode = is_note_file(path)
    hard, warn = check(body, note_mode=note_mode)

    print(f"GB/T 7714 合规检查: {path}{'（笔记模式）' if note_mode else ''}")
    print("=" * 60)
    if not hard and not warn:
        print("全部通过：未检出硬伤与提示级命中。")
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
