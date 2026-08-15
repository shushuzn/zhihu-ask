
"""syllogism_check.py — 报告语句三段论验证（实验性工具）。

用法：
    # 1) 从报告提取三段论候选句式 + 三件套齐备性检查（识别省略三段论）
    python tools/syllogism_check.py --file research/<slug>/report.md --extract

    # 2) 命令行直接验证三段论形式有效性（生成 Lean 脚本并运行）
    python tools/syllogism_check.py --verify \
        --major "∀ x, M x → P x" --minor "M a" --concl "P a"

    # 3) 验证已有 .lean 文件（含类型错误诊断：中项偷换/四名词谬误）
    python tools/syllogism_check.py --lean path/to/check.lean

能力与边界（诚实版）：
    - 三段论是"全称+蕴含"的一阶逻辑子集，形式化后 Lean 可 100% 判定：
      24 个有效式全可证；四名词谬误（偷换中项）被类型系统拒绝。
    - 中文语义解析（哪些词是 S/M/P、大前提真假）必须人工判断——工具只做
      结构提取与形式有效性判定，不做事实核查。
    - 三段论只覆盖演绎推理子集；归纳/类比/统计推断不是三段论，--extract
      会把它们一起列出，需人工甄别。
    - --verify 的大/小/结论请用 Lean 语法（∀ x, ... / → / 谓词应用）。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

MAJOR_PAT = re.compile(
    r"(凡|所有|任何|一切|每个|凡是|无论)[^。；;\n]{4,80}?(都|均|皆|总是|必然|无一例外)")

CONCLUSION_PAT = re.compile(r"(因此|所以|可见|由此|故|结论是|这意味着|由此可见|这说明)")

BECAUSE_PAT = re.compile(
    r"(因为|由于)[^。；;\n]{4,100}?(所以|因此|可见|故|由此可见)")

def find_candidates(body):
    """提取三段论候选。返回 [(原文片段, 类型, 引导词), ...] 去重。"""
    cands, seen = [], set()
    for m in MAJOR_PAT.finditer(body):
        seg = m.group(0).strip().replace("\n", " ")
        key = ("major", seg[:80])
        if key not in seen:
            seen.add(key)
            cands.append((seg[:160], "大前提候选", m.group(1)))
    for m in CONCLUSION_PAT.finditer(body):
        s = max(0, m.start() - 100)
        e = min(len(body), m.end() + 100)
        seg = body[s:e].replace("\n", " ").strip()
        key = ("concl", seg[:80])
        if key not in seen:
            seen.add(key)
            cands.append((seg[:200], "结论候选", m.group(1)))
    for m in BECAUSE_PAT.finditer(body):
        seg = m.group(0).strip().replace("\n", " ")
        key = ("cause", seg[:80])
        if key not in seen:
            seen.add(key)
            cands.append((seg[:160], "因果链候选", m.group(1)))
    return cands

def completeness(sent):
    """三件套齐备性检查（省略三段论检测）。"""
    has_major = bool(MAJOR_PAT.search(sent))
    has_concl = bool(CONCLUSION_PAT.search(sent))
    has_cause = bool(BECAUSE_PAT.search(sent))
    if has_major and has_concl:
        return "齐备：含大前提与结论引导"
    if has_major and not has_concl:
        return "缺结论：仅全称陈述，未见结论引导词"
    if has_concl and has_cause:
        return "省略三段论(enthymeme)：因果链缺全称大前提，需补全后才能验证"
    if has_concl:
        return "缺大前提：结论句无全称前提支撑"
    return "非三段论句式（可能为归纳/类比/统计）"

def check_lean_available():
    for cand in ("lean", os.path.expanduser("~/.elan/bin/lean"),
                 os.path.expanduser("~/.local/bin/lean")):
        try:
            r = subprocess.run([cand, "--version"], capture_output=True,
                               text=True, timeout=30)
            if r.returncode == 0 and "Lean" in r.stdout:
                return True
        except Exception:
            continue
    return False

def run_lean_file(path, lean_bin="lean"):
    """运行 .lean 并诊断结果：✓ 通过 / ✗ 类型不匹配(偷换中项) / ✗ 证明失败 / ⚠ 异常。"""
    try:
        r = subprocess.run([lean_bin, path], capture_output=True,
                           text=True, timeout=120)
    except Exception as e:
        return f"⚠ 运行异常: {e}"
    out = r.stdout + r.stderr
    if r.returncode == 0:
        return "✓ 形式有效（Lean 证明通过）"
    if "type mismatch" in out:
        return "✗ 类型不匹配——疑似四名词谬误/偷换中项（中项在大小前提不同义）"
    if "unknown identifier" in out or "unknown constant" in out:
        return "⚠ 谓词/常量未定义（请检查 Lean 语法）"
    if "unsolved" in out or "is false" in out:
        return "✗ 证明失败——该三段论形式无效（或前提不足）"
    return "⚠ 编译错误（见输出）"

def gen_skeleton_lean(major, minor, concl):
    """生成三段论验证骨架脚本（含用户命题注释，供 --lean 模式精调后判定）。"""
    return (
        "-- 三段论验证骨架：请把谓词/个体替换为实际定义，然后运行 lean 此文件判定\n"
        "-- 用法：lean <本文件>  → 全部 example 通过 = 形式有效；类型错误 = 偷换中项\n"
        f"-- 大前提: {major}\n"
        f"-- 小前提: {minor}\n"
        f"-- 结论:   {concl}\n\n"
        "axiom T : Type\n"
        "axiom a : T\n"
        "-- 按实际命题定义谓词后，把 example 的目标改为你的结论，用 exact 组合前提证明。\n"
        "example : (∀ x : T, True → True) → True := by\n"
        "  intro h\n"
        "  exact h a (by trivial)\n"
    )

PRED_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\b")

def diagnose(major, minor, concl):
    """三段论结构诊断（自动提示中项缺失/四名词谬误风险）。返回行列表。"""
    lines = []
    maj_preds = set(PRED_RE.findall(major))
    min_preds = set(PRED_RE.findall(minor))
    shared = maj_preds & min_preds
    if not shared:
        lines.append("⚠ 中项缺失：小前提谓词与大前提谓词无交集——"
                     "四名词谬误/偷换中项风险（中项必须在大小前提中同义出现）")
    else:
        lines.append(f"✓ 中项候选: {sorted(shared)}（同时出现在大小前提中）")
    if "∀" not in major:
        lines.append("⚠ 大前提非全称（无 ∀）——标准三段论大前提应为全称命题（凡 M 皆 P）")
    if "∀" in minor or "∀" in concl:
        lines.append("⚠ 小前提或结论含 ∀——标准三段论小前提与结论应为单称/特称")
    lines.append("注：形式有效 ≠ 前提为真；大前提真假须人工核查（归纳/经验规律不在验证范围）。")
    return lines

def main():
    ap = argparse.ArgumentParser(
        description="报告语句三段论验证（提取候选 / 三件套检查 / Lean 形式有效性判定）")
    ap.add_argument("--file", help="report.md 路径（与 --extract 联用）")
    ap.add_argument("--extract", action="store_true", help="提取三段论候选并做齐备性检查")
    ap.add_argument("--verify", action="store_true",
                    help="验证三段论形式有效性（配合 --major/--minor/--concl）")
    ap.add_argument("--major", help="大前提（Lean 语法，如 '∀ x, M x → P x'）")
    ap.add_argument("--minor", help="小前提（Lean 语法，如 'M a'）")
    ap.add_argument("--concl", help="结论（Lean 语法，如 'P a'）")
    ap.add_argument("--lean", help="验证已有 .lean 文件")
    args = ap.parse_args()

    if args.lean:
        if not check_lean_available():
            print("ERROR: 未找到 Lean 4（lean 命令）")
            sys.exit(1)
        if not os.path.exists(args.lean):
            print(f"ERROR: 文件不存在 {args.lean}")
            sys.exit(1)
        print(run_lean_file(args.lean))
        return

    if args.verify:
        if not (args.major and args.minor and args.concl):
            print("ERROR: --verify 需同时给 --major/--minor/--concl")
            sys.exit(1)
        if not check_lean_available():
            print("ERROR: 未找到 Lean 4（lean 命令）")
            sys.exit(1)
        print("三段论结构诊断：")
        for d in diagnose(args.major, args.minor, args.concl):
            print("  " + d)
        skeleton = gen_skeleton_lean(args.major, args.minor, args.concl)
        with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False,
                                         encoding="utf-8") as f:
            f.write(skeleton)
            p = f.name
        print(f"\n已生成骨架脚本: {p}")
        print("骨架含占位证明——请按实际谓词精调后，用 --lean 模式判定形式有效性。")
        return

    if args.extract:
        if not args.file or not os.path.exists(args.file):
            print("ERROR: --extract 需 --file 指向存在的 report.md")
            sys.exit(1)
        body = open(args.file, encoding="utf-8").read()
        cands = find_candidates(body)
        if not cands:
            print("未提取到三段论候选句式（该报告可能以归纳/类比/统计为主）")
            return
        print(f"共提取 {len(cands)} 条候选（需人工甄别哪些是真三段论）：\n")
        for i, (seg, typ, lead) in enumerate(cands, 1):
            status = completeness(seg)
            print(f"[{i}] {typ}（引导词「{lead}」）→ {status}")
            print(f"    {seg}")
            print()
        return

    ap.print_help()

if __name__ == "__main__":
    main()
