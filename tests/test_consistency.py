#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_consistency.py 单元测试：项目模板与脚本的矛盾与废话检查"""

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_consistency as cc

PASS = 0
FAIL = 0
TOTAL = 0
_TMP_DIRS = []


def make_tmp_dir():
    """在项目 .tmp 下创建临时目录（规避系统临时目录只读沙箱）。"""
    tmp_root = os.path.join(ROOT, ".tmp", "test_consistency")
    os.makedirs(tmp_root, exist_ok=True)
    d = tempfile.mkdtemp(dir=tmp_root)
    _TMP_DIRS.append(d)
    return d


def expect(name, cond, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


# ---- 工具引用缺失 ----
def test_tool_refs():
    d = make_tmp_dir()
    # 引用存在的工具 → 通过；引用不存在 → 报；含"未实施"标注 → 豁免
    f1 = os.path.join(d, "a.md")
    open(f1, "w", encoding="utf-8").write("用 tools/arxiv_search.py 检索。\n")
    f2 = os.path.join(d, "b.md")
    open(f2, "w", encoding="utf-8").write("用 tools/nonexistent_xyz.py。\n")
    f3 = os.path.join(d, "c.md")
    open(f3, "w", encoding="utf-8").write("方案 B（未实施）：tools/ima_search.py。\n")

    issues = cc.check_tool_refs([f1, f2, f3])
    expect("ref+ 存在工具通过", not any("arxiv_search" in h[3] for h in issues), issues)
    expect("ref+ 缺失工具拦截", any("nonexistent_xyz" in h[3] for h in issues), issues)
    expect("ref+ 未实施标注豁免", not any("ima_search" in h[3] for h in issues), issues)


# ---- 旧通道表述 ----
def test_obsolete_channels():
    d = make_tmp_dir()
    f = os.path.join(d, "x.md")
    open(f, "w", encoding="utf-8").write(
        "通道 D 已执行。\n七通道完成。\nF/E/A/B/C/D 六通道。\n"
        "F→E→A→B→C→D 执行。\nA–D 通道。\nA/B/C/D 四通道。\nABD 组合。\n"
        "历史说明：通道 D 已归入通道 P。\n"
        "arxiv→gathered_arxiv.md 登记 D，其余登记 P。\n"
        "arxiv D 的 WebFetch 流程。\n")
    issues = cc.check_obsolete_channels([f])
    # 旧表述均应报，历史说明（归入）也拦截（文档只反映当前状态）
    titles = [h[2] for h in issues]
    expect("chan+ 通道D拦截", any("旧通道 D" in t for t in titles), issues)
    expect("chan+ 七通道拦截", any("七通道" in t for t in titles), issues)
    expect("chan+ 旧清单拦截", any("旧通道清单" in t for t in titles), issues)
    expect("chan+ 旧执行顺序拦截", any("旧执行顺序" in t for t in titles), issues)
    expect("chan+ 旧 A–D 范围拦截", any("旧 A–D" in t for t in titles), issues)
    expect("chan+ 旧 A/B/C/D 范围拦截", any("旧通道范围" in t for t in titles), issues)
    expect("chan+ 旧 ABD 拦截", any("旧 ABD" in t for t in titles), issues)
    # 严格化：历史说明（"归入/不再独立"）不再豁免——文档只反映当前状态
    expect("chan+ 归入说明也拦截", any("通道D" in h[3] or "通道 D" in h[3] for h in issues), issues)
    # 变体：登记 D / arxiv D 同样拦截（本次修复前漏检）
    expect("chan+ 登记D拦截", any("旧通道 D 登记" in t for t in titles), issues)
    expect("chan+ arxiv D 拦截", any("旧 arxiv D" in t for t in titles), issues)
    # 负例：登记 docx 不误报（登记 D 需后随非字母）
    f2 = os.path.join(d, "y.md")
    open(f2, "w", encoding="utf-8").write("登记 docx 正常。\narxiv pdf 正常。\n")
    issues2 = cc.check_obsolete_channels([f2])
    expect("chan- 登记 docx 不误报", not any("旧通道 D 登记" in h[2] for h in issues2), issues2)
    expect("chan- arxiv pdf 不误报", not any("旧 arxiv D" in h[2] for h in issues2), issues2)


# ---- 日期注解残留 ----
def test_stale_dates():
    d = make_tmp_dir()
    f = os.path.join(d, "x.py")
    open(f, "w", encoding="utf-8").write(
        "# 2026-08-14 修复：某 bug\n"
        "# 2026-08-15 用户裁定：某规则\n"
        "# 普通注释\n")
    issues = cc.check_stale_dates([f])
    titles = [h[2] for h in issues]
    expect("date+ 修复拦截", any("日期注解残留" in t for t in titles), issues)
    expect("date+ 用户裁定拦截", any("日期注解残留" in t for t in titles), issues)
    # 无日期的普通注释不拦截
    f2 = os.path.join(d, "y.py")
    open(f2, "w", encoding="utf-8").write("# 普通注释\n")
    expect("date- 普通注释通过", cc.check_stale_dates([f2]) == [], cc.check_stale_dates([f2]))


# ---- 模板占位符 ----
def test_placeholders():
    t = os.path.join(ROOT, "templates", "_t_ph_check.md")
    open(t, "w", encoding="utf-8").write(
        "{{知乎问题完整标题}}\n{{关键词 1}}\n{{topic-slug}}\n{{XYZ_NOT_SUPPORTED}}\n")
    try:
        issues = cc.check_placeholder_supported([t])
        bad = [h for h in issues if "XYZ_NOT_SUPPORTED" in h[3]]
        expect("ph+ 未支持占位符拦截", len(bad) == 1, issues)
        expect("ph- 生成器支持通过", not any("知乎问题完整标题" in h[3] for h in issues), issues)
        expect("ph- 填写型通过", not any("关键词 1" in h[3] for h in issues), issues)
    finally:
        os.unlink(t)


# ---- 废话：无信息量修饰 ----
def test_banal():
    d = make_tmp_dir()
    f = os.path.join(d, "x.py")
    open(f, "w", encoding="utf-8").write(
        "# 这个工具非常强大，极其方便。\ndef f():\n    pass\n")
    issues = cc.check_banal([f])
    expect("banal+ 无信息量修饰拦截", len(issues) > 0, issues)
    # 词表定义行豁免
    f2 = os.path.join(d, "y.py")
    open(f2, "w", encoding="utf-8").write(
        'BANAL_RE = re.compile(r"(非常强大|高效便捷|功能完备)")\n')
    issues2 = cc.check_banal([f2])
    expect("banal- 词表定义豁免", not issues2, issues2)


# ---- docstring 参数 ----
def test_argparse_doc():
    import shutil
    t = os.path.join(ROOT, "tools", "_t_doc_check.py")
    open(t, "w", encoding="utf-8").write(
        '"""用法：python t.py --real-arg\n也支持 --ghost-arg 参数。"""\n'
        'import argparse\nap = argparse.ArgumentParser()\n'
        'ap.add_argument("--real-arg")\n')
    try:
        issues = cc.check_argparse_docstring([t])
        expect("doc+ 幽灵参数提示", any("ghost-arg" in h[3] for h in issues), issues)
    finally:
        os.unlink(t)


test_tool_refs()
test_obsolete_channels()
test_stale_dates()
test_placeholders()
test_banal()
test_argparse_doc()

for d in _TMP_DIRS:
    shutil.rmtree(d, ignore_errors=True)

print(f"\nPASS={PASS} FAIL={FAIL}")
if FAIL > 0:
    sys.exit(1)
