"""check_all.py 回归测试：全库体检的纯逻辑（24 项）。

覆盖：
- classify_quality_hits：软命中（无来源数字/立场词）不算硬失败，其余命中计硬失败
- extract_conclusion：标题行后、首个 ## 前提取结论段（空结论/无标题边界）
- conclusion_ok：存在性 / ≤300 字 / 不以 bullet 行开头
- find_reports：按 research/ 目录扫描含 report.md 的研究（临时目录打补丁）

行为与重构前完全一致——main() 委托逻辑不变，本测试锁定门禁策略
（软命中豁免清单变动会静默改变质量列判定，需回归守护）。

运行：python tests/test_check_all.py
"""
import os
import sys
import tempfile
import shutil

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_all as ca

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- classify_quality_hits：软命中豁免 ----
out = "[评价词] 2 处: 离谱\n[立场词] 1 处: 我认为\n[无来源数字] 5 处: 2024\n"
expect("qual+ 仅硬命中", ca.classify_quality_hits(out), ["[评价词] 2 处"])

out = "[无来源数字] 5 处: 2024\n[立场词] 1 处: 我认为\n"
expect("qual+ 仅软命中→空", ca.classify_quality_hits(out), [])

out = "[框架词] 1 处: 总结一下\n[感叹号] 3 处: !!\n[无来源数字] 2 处\n"
expect("qual+ 混合仅取硬", ca.classify_quality_hits(out),
       ["[框架词] 1 处", "[感叹号] 3 处"])

expect("qual+ 空输出", ca.classify_quality_hits(""), [])
expect("qual+ 无命中行", ca.classify_quality_hits("[OK] 全部通过\n"), [])
expect("qual+ 软关键词在硬行内仍豁免",
       ca.classify_quality_hits("[立场词与评价词] 1 处\n"), [])

# ---- extract_conclusion ----
body = "# 示例报告标题\n\n这是结论第一行。\n第二行。\n\n## 一、关键事实与数据\n\n正文\n"
expect("conc+ 整段提取", ca.extract_conclusion(body), "这是结论第一行。\n第二行。\n\n")

body = "# 标题\n\n## 一、开始\n\n正文\n"
expect("conc+ 空结论为空串", ca.extract_conclusion(body), "")

body = "## 一、开始\n\n正文\n"
expect("conc- 无标题返回 None", ca.extract_conclusion(body), None)

body = "# 标题\n\n结论段\n\n## 二、分析\n\nX\n\n## 三、结论\n\nY\n"
expect("conc+ 到首个 ## 为止", ca.extract_conclusion(body), "结论段\n\n")

body = "# 标题\n\n结论段\n\n### 小节一\n\n内容\n"
expect("conc+ 到 ### 小节为止（正文为 ### 平铺结构）", ca.extract_conclusion(body), "结论段\n\n")

body = "# 标题\n\n结论段"
expect("conc+ 文末无小节时到文末", ca.extract_conclusion(body), "结论段")

# ---- conclusion_ok ----
expect("ok- None", ca.conclusion_ok(None), False)
expect("ok+ 空串", ca.conclusion_ok(""), True)
expect("ok+ 300 字边界", ca.conclusion_ok("x" * 300), True)
expect("ok- 301 字", ca.conclusion_ok("x" * 301), False)
expect("ok- bullet 短横线开头", ca.conclusion_ok("- 要点"), False)
expect("ok- bullet 星号开头", ca.conclusion_ok("* 要点"), False)
expect("ok- 第二行 bullet", ca.conclusion_ok("正文\n- 子点"), False)
expect("ok+ 常规结论", ca.conclusion_ok("这是不超过 300 字的正常结论段落。"), True)

# ---- find_reports（打补丁 RESEARCH 到临时目录） ----
# 红线：默认不扫描旧报告——find_reports() 无参须返回空，
# 只有显式传 slugs 才读取指定 slug。
tmp = testutil.mktestdir()
try:
    os.makedirs(os.path.join(tmp, "b-slug"))
    os.makedirs(os.path.join(tmp, "a-slug"))
    os.makedirs(os.path.join(tmp, "c-slug"))
    with open(os.path.join(tmp, "a-slug", "report.md"), "w", encoding="utf-8") as f:
        f.write("# a")
    with open(os.path.join(tmp, "b-slug", "report.md"), "w", encoding="utf-8") as f:
        f.write("# b")
    with open(os.path.join(tmp, "c-slug", "other.txt"), "w", encoding="utf-8") as f:
        f.write("x")

    old = ca.RESEARCH
    ca.RESEARCH = tmp
    try:
        # 默认不扫描：无参调用不得读取任何报告（红线）
        expect("find+ 默认不扫描（红线）", ca.find_reports(), [])
        # 显式 slugs 才读取
        reports = ca.find_reports(["a-slug", "b-slug"])
        expect("find+ 显式 slug 才收", [s for s, _ in reports], ["a-slug", "b-slug"])
        expect("find+ 路径拼接正确", all(os.path.isfile(p) for _, p in reports), True)
        # 只收存在的 slug；不存在的 slug 被忽略
        reports = ca.find_reports(["a-slug", "no-such"])
        expect("find+ 缺失 slug 忽略", [s for s, _ in reports], ["a-slug"])
    finally:
        ca.RESEARCH = old

    ca.RESEARCH = os.path.join(tmp, "no-such-dir")
    expect("find- 目录不存在返回空", ca.find_reports(["a-slug"]), [])
    ca.RESEARCH = old
finally:
    shutil.rmtree(tmp, ignore_errors=True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
