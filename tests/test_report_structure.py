"""check_report_structure.py 回归测试：每条规则的正向（必命中）/负向（必不命中）用例。

覆盖：① 小节编号连续（重复/跳号）；② 顶层章节（当前 REQUIRED_TOP 为空，规则为 no-op）；
③ 参考文献存在且至少一条合法条目（链接/编号/无序列表/纯文本标题/空章节必 flag）；
④ 模板占位符。
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

# ---- 规则 5（新增）：结论段禁标题 + 仅参考文献为顶层章节 ----
# 5a 顶层章节：仅 ## 参考文献（含英文 References）可为二级标题，其余 ## 违规
#    内容小节须用 ###，原来是 no-op 的 REQUIRED_TOP 缺口现已堵住。
expect("top+ ## 结论 命中（非参考文献顶层）", has(check("# 标题\n\n结论段。\n\n## 结论\n\n正文。\n\n## 参考文献\n1. 来源"), "顶层章节违规"), True)
expect("top+ ## 一、 命中（内容小节应用 ###）", has(check("# 标题\n\n结论段。\n\n## 一、背景\n\n正文。\n\n## 参考文献\n1. 来源"), "顶层章节违规"), True)
expect("top- ## 参考文献 不误报", has(check("# 标题\n\n结论段。\n\n## 参考文献\n1. 来源"), "顶层章节违规"), False)

# 5b 结论段：H1 后首段不得为标题、首行不得写"结论"字样
expect("concl+ ## 结论 紧贴标题命中", has(check("# 标题\n\n## 结论\n\n正文。\n\n## 参考文献\n1. 来源"), "结论段首行不得写"), True)
expect("concl+ ### 结论 首段为标题命中", has(check("# 标题\n\n### 结论\n\n正文。\n\n## 参考文献\n1. 来源"), "结论段首行不得写"), True)
expect("concl+ 首行写'结论：'命中（首行不得写结论字样）", has(check("# 标题\n\n结论：本报告结论如下。\n\n## 参考文献\n1. 来源"), "结论段首行不得写"), True)
expect("concl- 标题后无标题结论段通过", check("# 标题\n\n本文给出最终判断。\n\n### 一、分析\n正文。\n\n## 参考文献\n1. 来源"), False)

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

if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
