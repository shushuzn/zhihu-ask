"""check_report_structure.py 回归测试：每条规则的正向（必命中）/负向（必不命中）用例。

覆盖：① 小节编号连续（重复/跳号）；② 顶层章节（当前 REQUIRED_TOP 为空，规则为 no-op）；
③ 参考文献存在且至少一条合法条目（链接/编号/无序列表/纯文本标题/空章节必 flag）；
④ 模板占位符；⑤ 测算须融入正文（**测算 N：** 单开一行 / 假设前提-计算口径 单开 bullet 必 flag）。
每条用例独立构造报告文本，互不污染。

运行：python tests/test_report_structure.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_report_structure as rs

PASS = 0
FAIL = 0


def check(text):
    """对一段报告文本跑结构校验，返回 issues 列表。"""
    return rs.check_structure(text.splitlines())


def expect(label, got, must_have):
    global PASS, FAIL
    ok = (len(got) > 0) == must_have
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: issues={len(got)}, expected {'>0' if must_have else '==0'}")
        for g in got[:3]:
            print(f"        {g}")


def has(issues, substr):
    return [i for i in issues if any(substr in str(x) for x in i)]


# ---- 规则 1：小节编号连续 ----
expect("subnum- 无编号小节不误报", check("# 结论\n\n正文。\n\n## 参考文献\n1. 来源"), False)
expect("subnum- 连续编号 1.1→1.2 通过", check("# 结论\n\n正文。\n\n### 1.1 节\n文。\n\n### 1.2 节\n文。\n\n## 参考文献\n1. 来源"), False)
expect("subnum+ 重复 1.1→1.1 命中", has(check("# 结论\n\n### 1.1 节\n文。\n\n### 1.1 节\n文。\n\n## 参考文献\n1. 来源"), "小节编号重复"), True)
expect("subnum+ 跳号 1.1→1.3 命中", has(check("# 结论\n\n### 1.1 节\n文。\n\n### 1.3 节\n文。\n\n## 参考文献\n1. 来源"), "小节编号跳号"), True)
expect("subnum- 跨章跳号不误报（2.1→3.1）", check("# 结论\n\n### 2.1 节\n文。\n\n### 3.1 节\n文。\n\n## 参考文献\n1. 来源"), False)

# ---- 规则 2：顶层章节（当前 REQUIRED_TOP=[]，规则为 no-op）----
expect("top- REQUIRED_TOP 为空时从不报缺顶层", has(check("# 结论\n\n正文。\n\n## 参考文献\n1. 来源"), "缺少顶层章节"), False)

# ---- 规则 3：参考文献存在 + 至少一条合法条目 ----
expect("ref+ 缺参考文献章节命中", has(check("# 结论\n\n正文。"), "缺少参考文献章节"), True)
expect("ref+ 参考文献为空（仅标题无条目）命中", has(check("# 结论\n\n正文。\n\n## 参考文献\n\n"), "参考文献章节为空"), True)
expect("ref- 编号列表条目通过", check("# 结论\n\n正文。\n\n## 参考文献\n1. 中国移动公告（2026）\n2. 工信部运行数据"), False)
expect("ref- 链接条目通过", check("# 结论\n\n正文。\n\n## 参考文献\n[中国移动公告](https://example.com/a)"), False)
expect("ref- 无序列表条目通过", check("# 结论\n\n正文。\n\n## 参考文献\n- 中国移动公告\n- 工信部数据"), False)
expect("ref- 纯文本标题条目通过（删 url 合规）", check("# 结论\n\n正文。\n\n## 参考文献\n工业和信息化部关于规范售卡管理的公告"), False)
expect("ref+ 仅占位符不算合法条目", has(check("# 结论\n\n正文。\n\n## 参考文献\n{{ref_placeholder}}"), "参考文献章节为空"), True)

# ---- 规则 4：模板占位符残留 ----
expect("ph+ 残留 {{...}} 命中", has(check("# 结论\n\n{{title}} 占位。\n\n## 参考文献\n1. 来源"), "模板占位符残留"), True)
expect("ph- 正常文本不误报", check("# 结论\n\n正文无占位。\n\n## 参考文献\n1. 来源"), False)

# ---- 规则 5：测算须融入正文 ----
expect("calc+ **测算 N：** 单开一行命中", has(check("# 结论\n\n正文。\n\n### 测算小节\n**测算 1：** 某计算\n\n## 参考文献\n1. 来源"), "测算未融入正文"), True)
expect("calc+ - **假设前提** bullet 命中", has(check("# 结论\n\n正文。\n\n### 小节\n- **假设前提**：xxx\n\n## 参考文献\n1. 来源"), "测算未融入正文"), True)
expect("calc+ - **计算口径** bullet 命中", has(check("# 结论\n\n正文。\n\n### 小节\n- **计算口径**：xxx\n\n## 参考文献\n1. 来源"), "测算未融入正文"), True)
expect("calc- 测算叙述融入正文不误报", check("# 结论\n\n正文。\n\n### 规模测算\n按公开数据，2025 年行业规模约 3000 亿元（来源已列），同比温和增长。\n\n## 参考文献\n1. 来源"), False)
expect("calc- 行中 **测算** 不误报", check("# 结论\n\n正文提及某测算结果合理。\n\n## 参考文献\n1. 来源"), False)

# ---- 综合：贴近真实成品的最小合规报告 ----
full = (
    "# 结论\n\n"
    "2026 年 8 月起线上流量卡并未全面禁售，实为规范互联网渠道售卡秩序。\n\n"
    "## 参考文献\n"
    "1. 中国移动、中国电信、中国联通《关于规范互联网渠道售卡管理的公告》（2026-07-31）\n"
    "2. 工业和信息化部《2026 年上半年通信业经济运行情况》\n"
)
expect("full- 最小合规报告通过", check(full), False)


print(f"PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
