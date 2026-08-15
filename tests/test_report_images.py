"""report_images.py 回归测试：锚点插入纯函数 + 颜色解析 + 图表冒烟（20 项）。

覆盖：
- hex_to_rgb：色值解析（带 #/不带 #）
- insert_block_into_content（本轮抽取的纯函数）：锚点小节命中插到首段后
  （不紧跟标题行）、加粗标题命中、锚点缺失回退首个 ### 前、AI 概念图未命中
  跳过、无 ### 可回退报 missing
- 图表冒烟（PIL 可用时）：bar_group/bar_single/scatter 三种图生成 PNG 且尺寸正确

锚点插入回归（插错位置/回退错位）会把图片贴到标题下或污染正文结构，
需回归守护。

运行：python tests/test_report_images.py
"""
import os
import sys
import tempfile
import shutil

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import report_images as ri

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- hex_to_rgb ----
expect("hex+ 带 #", ri.hex_to_rgb("#E64A3C"), (230, 74, 60))
expect("hex+ 不带 #", ri.hex_to_rgb("3B6FB5"), (59, 111, 181))
expect("hex+ 绿色", ri.hex_to_rgb("#2E8B57"), (46, 139, 87))
expect("hex+ 全白", ri.hex_to_rgb("FFFFFF"), (255, 255, 255))

# ---- insert_block_into_content：锚点命中 ----
content = "# 标题\n\n### 斩杀线的定义与出处\n\n这是第一段正文。\n\n第二段。\n\n### 别的\n\n内容\n"
block_lines = ["![alt](chart_1.png)", "", "图 1｜斩杀线示意"]
new, status = ri.insert_block_into_content(content, "斩杀线的定义", block_lines)
expect("ins+ 命中状态", status, "inserted")
expect("ins+ 图块插入", "![alt](chart_1.png)" in new, True)
expect("ins+ 图注编号", "图 1｜斩杀线示意" in new, True)
i_img = new.index("![alt](chart_1.png)")
i_first = new.index("这是第一段正文。")
i_second = new.index("第二段。")
expect("ins+ 插在首段后非标题后", i_first < i_img < i_second, True)
i_heading = new.index("### 斩杀线的定义与出处")
expect("ins+ 不紧跟标题行", i_img - i_heading > 10, True)

# 加粗标题命中
content = "# 标题\n\n**斩杀线的定义与出处**\n\n正文段落内容。\n\n### 别的\n"
new, status = ri.insert_block_into_content(content, "斩杀线的定义", block_lines)
expect("ins+ 加粗标题命中", status, "inserted")

# ---- insert_block_into_content：回退/跳过 ----
content = "# 标题\n\n### 首个小节\n\n内容。\n"
new, status = ri.insert_block_into_content(content, "不存在的锚点", block_lines)
expect("ins+ 未命中回退", status, "fallback")
expect("ins+ 回退插到首个小节前", new.index("![alt](chart_1.png)") < new.index("### 首个小节"), True)

content = "# 标题\n\n### 首个小节\n\n内容。\n"
new, status = ri.insert_block_into_content(content, "不存在的锚点", block_lines, ai_only=True)
expect("ins- AI 概念图未命中跳过", status, "missing_ai")
expect("ins- AI 跳过内容不变", new == content, True)

content = "# 标题\n\n纯文本无小节。\n"
new, status = ri.insert_block_into_content(content, "不存在的锚点", block_lines)
expect("ins- 无 ### 可回退", status, "missing")
expect("ins- 无小节内容不变", new == content, True)

# ---- 图表冒烟（PIL 可用时） ----
try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

if _HAS_PIL:
    tmp = testutil.mktestdir()
    try:
        out = os.path.join(tmp, "bg.png")
        ri.draw_bar_group({
            "groups": ["A", "B"],
            "series": [{"label": "S1", "values": [10, 20]},
                       {"label": "S2", "values": [15, 25]}],
            "title": "对比", "unit": "元", "note": "数据来源",
        }, out)
        im = Image.open(out)
        expect("chart+ bar_group 尺寸", im.size, (1440, 840))

        out = os.path.join(tmp, "bs.png")
        ri.draw_bar_single({"labels": ["甲", "乙", "丙"], "values": [5, 3, 8],
                            "title": "排序"}, out)
        im = Image.open(out)
        expect("chart+ bar_single 宽度", im.size[0], 1440)

        out = os.path.join(tmp, "sc.png")
        ri.draw_scatter({
            "points": [{"x": 5, "y": 3, "label": "P1"},
                       {"x": 8, "y": 6, "label": "P2"}],
            "title": "斩杀线", "kill_x": 7,
        }, out)
        im = Image.open(out)
        expect("chart+ scatter 尺寸", im.size, (1440, 960))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
else:
    print("  [跳过] 当前解释器无 PIL，图表冒烟用例未执行")


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
