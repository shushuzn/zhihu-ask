# -*- coding: utf-8 -*-
"""report_to_flomo.py 回归测试：convert_text（markdown->flomo 格式）+ pick_tags（领域标签）。

运行：python tests/test_report_to_flomo.py
仅锁定当前机械转换与最长键优先匹配行为，不触发任何外部 API。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import report_to_flomo as fl

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


def expect_true(label, cond):
    expect(label, bool(cond), True)


# ---------- convert_text：markdown -> flomo ----------
# 1) 标题转加粗
expect("h1->bold", fl.convert_text("# 结论"), "**结论**")
expect("h3->bold", fl.convert_text("### 2.1 测算说明"), "**2.1 测算说明**")

# 2) 引用去前缀
expect("blockquote", fl.convert_text("> 据工信部公告"), "据工信部公告")

# 3) 表格行 -> 列表
expect("table-row", fl.convert_text("| 列A | 列B |"), "- 列A / 列B")

# 3b) 表格内 LaTeX 范数 \\| 不得被误判为列分隔符
expect("table-latex-bar",
       fl.convert_text('| 数值猜测 | $\\|T_{\\mathrm{even}}\\|\\approx 0.6368$ |'),
       '- 数值猜测 / $\\|T_{\\mathrm{even}}\\|\\approx 0.6368$')

# 4) 表头分隔行 -> 跳过（空输出）
expect("table-sep-skip", fl.convert_text("|---|---|"), "")

# 5) 链接 -> 标题（url）
expect("link", fl.convert_text("详见[公告](http://x.com/a)"), "详见公告（http://x.com/a）")

# 6) 行内公网图片 -> alt（url）
expect("img-public-inline",
       fl.convert_text("![图1](https://img.com/a.png)"),
       "图1（https://img.com/a.png）")

# 7) 行内本地图片 -> 仅 alt
expect("img-local-inline",
       fl.convert_text("见 ![图2](chart.png) 所示"),
       "见 图2 所示")

# 8) 整行本地图片 -> 丢弃
expect("img-local-wholeline",
       fl.convert_text("![chart_benchmark](chart_benchmark.png)"),
       "")

# 9) 反引号剥离
expect("backtick", fl.convert_text("代码 `code` 结束"), "代码 code 结束")

# 10) 多行组合：标题 + 正文 + 引用 + 表格 + 链接
multi = "# 标题\n正文一段。\n> 引用一行\n| 甲 | 乙 |\n链接[百度](https://b.com)\n"
got = fl.convert_text(multi)
expect("multi-h1", "**标题**" in got, True)
expect("multi-quote", "引用一行" in got, True)
expect("multi-table", "- 甲 / 乙" in got, True)
expect("multi-link", "百度（https://b.com）" in got, True)
expect("multi-no-sep", "---" not in got, True)

# 11) 内容完整性：不增删文字（去掉格式符号后原文字应保留）
src = "量子计算将改变密码学。2026 年三大运营商营收均超万亿。"
out = fl.convert_text(src)
for token in ["量子计算将改变密码学", "2026 年三大运营商营收均超万亿"]:
    expect(f"integrity::{token[:6]}", token in out, True)


# ---------- pick_tags：最长键优先匹配 ----------
# 12) 子串误匹配防护：人工智能 应优先于 科技
expect("tag-ai-longest", fl.pick_tags("科技/人工智能"), (("AI", "科技社会"), True))
# 13) 经济史 应优先于 宏观
expect("tag-econ-longest", fl.pick_tags("经济史/宏观经济"), (("经济", "历史"), True))
# 14) 精确命中
expect("tag-finance", fl.pick_tags("金融"), (("金融", "投资理财"), True))
expect("tag-math", fl.pick_tags("数学"), (("数学", "基础科学"), True))
# 15) 未命中 -> 兜底 + matched=False
tags, matched = fl.pick_tags("冷门学科xyz")
expect("tag-fallback-matched", matched, False)
expect("tag-fallback-first", tags[0], "冷门学科xyz")
expect("tag-fallback-second", tags[1], "综合")
# 16) 大小写不敏感：AI 小写键命中
expect("tag-case-insensitive", fl.pick_tags("聊聊ai"), (("AI", "科技社会"), True))


if __name__ == "__main__":
    print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
