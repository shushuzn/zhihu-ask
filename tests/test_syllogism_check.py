"""syllogism_check.py 回归测试：三段论提取/齐备性/结构诊断（22 项）。

覆盖（均为纯函数，不依赖 lean 二进制）：
- find_candidates：大前提/结论/因果链三类候选提取 + 去重 + 空正文
- completeness：三件套齐备性四分支（齐备/缺结论/省略三段论/缺大前提）+ 非三段论
- diagnose：中项共享候选、中项缺失（四名词谬误风险）、大前提非全称、
  小前提/结论含 ∀ 警告、完整有效式无警告
- gen_skeleton_lean：骨架含大/小/结论注释与占位证明

另：本轮移除死代码 verify_triple（无任何调用，第一段 code 赋值被覆盖、
内含 sorry 占位证明——若被误用会产出误导性"形式有效"判定）。

运行：python tests/test_syllogism_check.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import syllogism_check as sc

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- find_candidates：三类候选 ----
body = ("凡是金属制品都导电，这是物理常识。"
        "因为连续下雨数小时所以路面湿滑。"
        "因此出门需带伞。")
cands = sc.find_candidates(body)
types = [t for _, t, _ in cands]
expect("fc+ 三类候选齐全", set(types), {"大前提候选", "结论候选", "因果链候选"})
expect("fc+ 大前提引导词", cands[0][2], "凡")
expect("fc+ 因果链引导词", next(c[2] for c in cands if c[1] == "因果链候选"), "因为")

body = "凡是金属制品都导电。凡是金属制品都导电。"
cands = sc.find_candidates(body)
expect("fc+ 重复句式去重", len(cands), 1)

expect("fc- 空正文", sc.find_candidates(""), [])
expect("fc- 无句式正文", sc.find_candidates("统计显示多数用户满意，平台增速放缓。"), [])

# ---- completeness：三件套齐备性 ----
expect("cp+ 齐备", sc.completeness("凡是金属制品都导电，因此铜制品导电。"),
       "齐备：含大前提与结论引导")
expect("cp+ 缺结论", sc.completeness("凡是金属制品都导电。"),
       "缺结论：仅全称陈述，未见结论引导词")
expect("cp+ 省略三段论", sc.completeness("因为连续下雨所以路面湿滑，因此出门带伞。"),
       "省略三段论(enthymeme)：因果链缺全称大前提，需补全后才能验证")
expect("cp+ 缺大前提", sc.completeness("因此出门需带伞。"),
       "缺大前提：结论句无全称前提支撑")
expect("cp+ 非三段论", sc.completeness("统计显示大多数用户满意。"),
       "非三段论句式（可能为归纳/类比/统计）")

# ---- diagnose：结构诊断 ----
lines = sc.diagnose("∀ x, M x → P x", "M a", "P a")
expect("dg+ 中项候选", any("✓ 中项候选" in l and "M" in l for l in lines), True)
expect("dg+ 完整式无警告",
       not any(("⚠" in l and "中项" in l) or "非全称" in l or "含 ∀" in l for l in lines), True)

lines = sc.diagnose("P x", "Q a", "R a")
expect("dg- 中项缺失", any("中项缺失" in l for l in lines), True)

lines = sc.diagnose("P x", "M a", "M a")
expect("dg- 大前提非全称", any("大前提非全称" in l for l in lines), True)

lines = sc.diagnose("∀ x, M x → P x", "∀ y, M y", "P a")
expect("dg- 小前提含 ∀", any("小前提或结论含 ∀" in l for l in lines), True)

expect("dg+ 恒有前提真伪注记", any("形式有效 ≠ 前提为真" in l for l in sc.diagnose("∀ x, M x → P x", "M a", "P a")), True)

# ---- gen_skeleton_lean：骨架生成 ----
sk = sc.gen_skeleton_lean("∀ x, M x → P x", "M a", "P a")
expect("sk+ 含大前提注释", "-- 大前提: ∀ x, M x → P x" in sk, True)
expect("sk+ 含小前提注释", "-- 小前提: M a" in sk, True)
expect("sk+ 含结论注释", "-- 结论:   P a" in sk, True)
expect("sk+ 含占位证明", "axiom T : Type" in sk, True)

# ---- 死代码移除验证 ----
expect("dead- verify_triple 已移除", not hasattr(sc, "verify_triple"), True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
