# -*- coding: utf-8 -*-
"""search_all.py 回归测试：命令构造（B/A/P 三通道）+ slug 校验。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import search_all as sa

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- slug 校验 ----
expect("slug+ 合法短横线", sa.SLUG_RE.match("grill-me-skill") is not None, True)
expect("slug- 大写拒绝", sa.SLUG_RE.match("Grill-Me") is None, True)
expect("slug- 下划线拒绝", sa.SLUG_RE.match("a_b") is None, True)

# ---- build_commands：三通道命令构造 ----
cfg = {"question": "测试问题", "slug": "t-slug", "domain": "科技 / AI"}
keywords = ["kw1 体验", "kw2 实战"]
cmds = sa.build_commands(cfg, "t-slug", keywords, 365, 4, skip_preprints=False)
labels = [c[0] for c in cmds]
expect("cmd+ 三通道齐全", labels, ["B Web", "A 公众号", "P 预印本"])
b_cmd = cmds[0][1]
expect("cmd+ B 用 --queries-file", "--queries-file" in b_cmd, True)
expect("cmd+ B 并行参数", "--parallel" in b_cmd and "4" in b_cmd, True)
expect("cmd+ B 落盘标准路径", any("gathered_web.md" in c for c in b_cmd) and "--slug" in b_cmd, True)
a_cmd = cmds[1][1]
expect("cmd+ A 用 --keywords 文件", "--keywords" in a_cmd and "--output" in a_cmd, True)
expect("cmd+ A 时间范围", "--days" in a_cmd and "365" in a_cmd, True)
p_cmd = cmds[2][1]
expect("cmd+ P 四平台", "--platform" in p_cmd and "all" in p_cmd, True)
expect("cmd+ P 带 slug", "--slug" in p_cmd and "t-slug" in p_cmd, True)

# ---- --skip-preprints：P 不构造 ----
cmds2 = sa.build_commands(cfg, "t-slug", keywords, 365, 4, skip_preprints=True)
expect("cmd+ skip-preprints 去掉 P", [c[0] for c in cmds2], ["B Web", "A 公众号"])

# ---- 关键词含引号/空格安全传递（关键词写入 queries 文件，不在命令行） ----
import json
cmds3 = sa.build_commands({"question": "q", "slug": "s1"}, "s1", ['"精确短语" 测试', "x"], 30, 2, skip_preprints=True)
qf = cmds3[0][1][cmds3[0][1].index("--queries-file") + 1]
qdata = json.load(open(qf, encoding="utf-8"))
expect("cmd+ 引号关键词写入文件", qdata["queries"], ['"精确短语" 测试', "x"])

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
