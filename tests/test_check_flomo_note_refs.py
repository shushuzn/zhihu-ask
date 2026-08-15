"""check_flomo_note_refs.py 回归测试：参考文献检测 + 标题提取 + 匹配键 + 相关性过滤 + 不联网判定（20 项）。

覆盖：has_reference（来源:/## 参考文献/文献类型标识/URL/^[n] 条目）、extract_title（tag 行/转义下划线/加粗清理）、
match_keys（中文/英文/前缀键）、relevant_candidates（标题匹配键过滤候选）、detect 不联网分支（无参考文献→fail）。

运行：python tests/test_check_flomo_note_refs.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_flomo_note_refs as cfr

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---------- has_reference ----------
def test_has_reference():
    expect("含来源:标记", cfr.has_reference("内容\n来源:\n[1] 作者. 题名"), True)
    expect("含来源类型", cfr.has_reference("来源类型: 一手"), True)
    expect("含参考文献标题", cfr.has_reference("## 参考文献\n[1] x"), True)
    expect("含文献类型标识", cfr.has_reference("题名[EB/OL]. (2024)"), True)
    expect("含URL", cfr.has_reference("详见 https://example.com/a"), True)
    expect("含编号条目", cfr.has_reference("笔记内容\n[1] 作者. 题名[M]. 北京, 2020."), True)
    expect("纯文本无参考文献", cfr.has_reference("只有正文没有来源"), False)
    expect("空文本", cfr.has_reference(""), False)


# ---------- extract_title ----------
def test_extract_title():
    tag_note = "#知识基座 #编程语言 #主题/seven\n\n**编程技术\\_低级编程\\_汇编学习动机**\n\n正文内容"
    expect("tag行后取标题并清理转义加粗", cfr.extract_title(tag_note), "编程技术_低级编程_汇编学习动机")
    plain = "## 标题\n正文"
    expect("无tag取首行去井号", cfr.extract_title(plain), "标题")
    expect("空笔记", cfr.extract_title(""), "")
    only_tag = "#a #b #c"
    expect("只有tag无标题", cfr.extract_title(only_tag), "")


# ---------- match_keys ----------
def test_match_keys():
    expect("中文整串+前缀键", cfr.match_keys("汇编语言学习动机"),
           {"汇编语言学习动机", "汇编语言"})
    expect("英文小写+前缀键", cfr.match_keys("CyberScript"),
           {"cyberscript", "cybers"})
    expect("短串无前缀键", cfr.match_keys("脚本语言"), {"脚本语言"})


# ---------- relevant_candidates ----------
def test_relevant_candidates():
    title = "编程语言_脚本语言_Cyber脚本语言"
    cands = [
        {"title": "StreamObserver未响应", "href": "https://ask.csdn.net/1", "body": "java 流式处理"},
        {"title": "Cyber 语言快速上手", "href": "https://x.com/cyber", "body": "Cyber 脚本语言介绍"},
        {"title": "无关文章", "href": "https://y.com/2", "body": "天气"},
    ]
    got = cfr.relevant_candidates(title, cands)
    expect("按匹配键过滤候选", [c["title"] for c in got], ["Cyber 语言快速上手"])
    expect("无标题时全保留", len(cfr.relevant_candidates("", cands)), 3)


# ---------- gbt_validate ----------
def test_gbt_validate():
    good = "## 参考文献\n\n[1] 作者. 题名[EB/OL]. (2024-10)[2026-08-13]. https://a.b/c.\n\n来源类型: 一手"
    ok, issues = cfr.gbt_validate(good)
    expect("合规条目通过", ok, True)
    flomo_escaped = "## 参考文献\n\n[1] 作者. 题名[EB/OL]. (2024-10)[2026-08-13]. https://a.b/c.\n\n来源类型: 一手"
    ok, _ = cfr.gbt_validate(cfr.normalize(flomo_escaped.replace("[", r"\[").replace("]", r"\]")))
    expect("flomo转义格式反转义后合规", ok, True)
    no_type = "## 参考文献\n\n[1] 作者. 题名. 出版社, 2020."
    ok, issues = cfr.gbt_validate(no_type)
    expect("缺文献类型标识判不合规", ok, False)
    expect("缺类型标识提示含编号", any("缺文献类型标识" in i for i in issues), True)
    no_date = "## 参考文献\n\n[1] 作者. 题名[EB/OL]. https://a.b/c."
    ok, _ = cfr.gbt_validate(no_date)
    expect("URL缺引用日期判不合规", ok, False)
    skip_num = "## 参考文献\n\n[1] 甲. 题名[M]. 北京: 出版社, 2020.\n\n[3] 乙. 题名[J]. 刊名, 2021."
    ok, _ = cfr.gbt_validate(skip_num)
    expect("编号不连续判不合规", ok, False)
    only_source = "**来源**：网络"
    ok, issues = cfr.gbt_validate(only_source)
    expect("无编号条目判不合规", ok, False)
    expect("无编号提示无[n]条目", any("无 [n] 编号条目" in i for i in issues), True)


# ---------- detect（不联网） ----------
def test_detect_no_search():
    r = cfr.detect("无参考文献的纯文本内容", do_search=False)
    expect("不联网-无参考文献判fail", r["status"], "fail")
    good = "有来源:\n[1] 作者. 题名[EB/OL]. (2024-10)[2026-08-13]. https://a.b/c"
    r2 = cfr.detect(good, do_search=False)
    expect("不联网-合规参考文献判ok", r2["status"], "ok")
    bad = "有来源:\n[1] 作者. 题名. 无类型标识"
    r3 = cfr.detect(bad, do_search=False)
    expect("参考文献不合国标判fail", r3["status"], "fail")
    expect("不合规理由含国标", "GB/T" in r3["reason"], True)


if __name__ == "__main__":
    test_has_reference()
    test_extract_title()
    test_match_keys()
    test_relevant_candidates()
    test_gbt_validate()
    test_detect_no_search()
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
