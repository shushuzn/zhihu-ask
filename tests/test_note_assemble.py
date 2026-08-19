"""note_assemble.py 回归测试：笔记解析（参考文献:格式）+ 索引组装（箭头编号）。

运行：python tests/test_note_assemble.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import note_assemble as na

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def mknote(tag_line, title, body, refs):
    return f"{tag_line}\n\n{title}\n\n{body}\n\n参考文献:\n" + "\n\n".join(refs) + "\n"


def test_parse_note():
    src = os.path.join(ROOT, "tests", "tmp_note_assemble.md")
    with open(src, "w", encoding="utf-8") as f:
        f.write(mknote("#AI #科技 #主题/x", "标题", "正文引用[1]。",
                        ["[1] 甲. 题名[M]. 京: 社, 2020.",
                         "[2] 乙. 题名[EB/OL]. (2024-01-01)[2026-08-18]. https://a.b/c."]))
    note = na.parse_note_file(src)
    expect("tags解析", note["tags"], ["#AI", "#科技", "#主题/x"])
    expect("正文剥离文献区", "正文引用[1]。" in note["content"] and "参考文献" not in note["content"], True)
    expect("sources提取[1]", note["sources"][0].startswith("甲. 题名[M]"), True)
    expect("sources提取[2]", note["sources"][1].startswith("乙. 题名[EB/OL]"), True)
    os.remove(src)


def test_parse_note_old_source_field():
    """旧式「来源:」字段：非规定格式，不再当作参考文献区解析。"""
    src = os.path.join(ROOT, "tests", "tmp_note_assemble2.md")
    with open(src, "w", encoding="utf-8") as f:
        f.write("#AI #科技 #主题/x\n\n标题\n\n正文。\n\n**来源**：网络\n\n参考文献:\n[1] 甲. 题名[M]. 京: 社, 2020.\n")
    note = na.parse_note_file(src)
    expect("来源字段不算文献区，参考文献正常解析", note["sources"], ["甲. 题名[M]. 京: 社, 2020."])
    expect("来源字段不残留正文", "**来源**：网络" not in note["content"], True)
    os.remove(src)


def test_build_from_index():
    notes = {}
    for nid in ("01", "02"):
        notes[nid] = {"type": "note", "content": f"正文{nid}[1]。",
                      "sources": [f"来源{nid}."], "meta": {}}
    index = {"type": "index",
             "content": "#索引\n\n## 组装顺序\n\n02 → 01\n",
             "sources": []}
    sections = na.build_report_from_index(index, notes)
    assembled = na.assemble_report(sections, "test-slug")
    expect("箭头编号识别两个笔记", "正文02[1]。" in assembled and "正文01[1]。" in assembled, True)
    expect("参考文献区合并来源", "来源01." in assembled and "来源02." in assembled, True)
    expect("无参考来源段残留", "**参考来源:**" not in assembled, True)


if __name__ == "__main__":
    test_parse_note()
    test_parse_note_old_source_field()
    test_build_from_index()
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
