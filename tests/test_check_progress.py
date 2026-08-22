"""check_progress.py --require report_channels 双向交叉校验回归测试。

覆盖：① 无结构化登记时回退旧文件启发式（正向/反向）；② 结构化模式下
正向（声明→证据）、反向（证据→声明）、完整性（五通道）、report.md 承接
四类拦截。每条用例独立造临时 slug 目录，互不污染。

运行：python tests/test_check_progress.py
"""
import os
import sys
import json
import shutil
import tempfile

import testutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_progress as cp

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got}, expected {must_be}")


def build(slug, channels_done=None, files=None, report_bytes=0, domain=None):
    """造一个临时 slug 目录，返回 (slug_dir, slug)。"""
    base = testutil.mktestdir(prefix="tprog_")
    slug_dir = os.path.join(base, slug)
    os.makedirs(slug_dir, exist_ok=True)
    prog = {"stage": "phase1_done", "data": {"question": "q"}}
    if domain:
        prog["data"]["domain"] = domain
    if channels_done is not None:
        prog["data"]["channels_done"] = channels_done
    with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)
    for fname, size in (files or {}).items():
        with open(os.path.join(slug_dir, fname), "w", encoding="utf-8") as f:
            f.write("x" * size)
    if report_bytes:
        with open(os.path.join(slug_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write("x" * report_bytes)
    return slug_dir, slug


def cleanup(slug_dir):
    shutil.rmtree(os.path.dirname(slug_dir), ignore_errors=True)


# ---- 文件启发式回退（无 channels_done）----
d, s = build("h1", channels_done=None, files={"gathered_wechat.md": 300}, report_bytes=0)
expect("fallback+ 有素材无report→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

d, s = build("h2", channels_done=None, files={"gathered_wechat.md": 300}, report_bytes=700)
expect("fallback- 有素材有report→通过", cp.check_report_channels(d, s), 0)
cleanup(d)

# ---- 结构化：完整一致 → 通过 ----
d, s = build("ok1", channels_done={
    "E": {"status": "skip", "note": "ima 未连接"},
    "A": {"status": "done", "note": "命中 10"},
    "B": {"status": "done", "note": "官方来源"},
    "C": {"status": "done", "note": "企查查+通达信+智慧芽"},
    "P": {"status": "skip", "note": "预印本不适用"},
}, files={
    "gathered_wechat.md": 300, "gathered_web.md": 300,
    "gathered_c.md": 300,
}, report_bytes=700)
expect("struct- 五通道声明完整一致→通过", cp.check_report_channels(d, s), 0)
cleanup(d)

# ---- 完整性：缺声明通道 P → 阻塞 ----
d, s = build("miss1", channels_done={
    "E": {"status": "skip", "note": "x"},
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "done", "note": "x"},
}, files={
    "gathered_wechat.md": 300, "gathered_web.md": 300, "gathered_c.md": 300,
}, report_bytes=700)
expect("completeness+ 缺通道P声明→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

# ---- 环境级未配置通道：缺 E/C 声明不阻塞（初始化自动 skip，跨研究共享） ----
d, s = build("envskip", channels_done={
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "P": {"status": "done", "note": "x"},
}, files={
    "gathered_wechat.md": 300, "gathered_web.md": 300, "gathered_arxiv.md": 300,
}, report_bytes=700, domain="学术科研")
expect("envskip- 缺 E/C 声明不阻塞（环境级自动 skip）", cp.check_report_channels(d, s), 0)
cleanup(d)

# ---- 正向：A done 但素材缺失 → 阻塞 ----
d, s = build("fwd1", channels_done={
    "E": {"status": "skip", "note": "x"},
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "done", "note": "x"},
}, files={"gathered_web.md": 300, "gathered_c.md": 300, "gathered_arxiv.md": 300},
   report_bytes=700)
expect("forward+ A done但无素材→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

# ---- 反向：存在素材但 channels_done 未登记 → 阻塞 ----
d, s = build("rev1", channels_done={
    "E": {"status": "skip", "note": "x"},
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "done", "note": "x"},
}, files={
    "gathered_wechat.md": 300, "gathered_web.md": 300,
    "gathered_c.md": 300, "gathered_arxiv.md": 300,
}, report_bytes=700)
expect("reverse+ 素材未登记→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

# ---- report.md 承接：声明齐全但 report 过小 → 阻塞 ----
d, s = build("rep1", channels_done={
    "E": {"status": "skip", "note": "x"},
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "done", "note": "x"},
}, files={
    "gathered_wechat.md": 300, "gathered_web.md": 300,
    "gathered_c.md": 300, "gathered_arxiv.md": 300,
}, report_bytes=100)
expect("report+ report过小→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

# ---- P0 领域校验（领域矩阵工具化）----
# 学术科研领域：P 为 P0，skip 且 note 无原因 → 阻塞
d, s = build("p0skip", channels_done={
    "E": {"status": "skip", "note": "未连接"},
    "A": {"status": "skip", "note": "学术无公众号"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "skip", "note": "未配置"}, "P": {"status": "skip", "note": "没查"},
}, files={"gathered_web.md": 300}, report_bytes=700, domain="物理/宇宙学/流体动力学")
expect("p0+ 学术科研P跳过无原因→阻塞", cp.check_report_channels(d, s), 1)
cleanup(d)

# P0 skip 但 note 说明"未连接" → 放行
d, s = build("p0ok", channels_done={
    "E": {"status": "skip", "note": "未连接"},
    "A": {"status": "skip", "note": "学术无公众号"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "skip", "note": "未配置"}, "P": {"status": "skip", "note": "平台未连接"},
}, files={"gathered_web.md": 300}, report_bytes=700, domain="物理/宇宙学/流体动力学")
expect("p0+ 学术科研P跳过有原因→放行", cp.check_report_channels(d, s), 0)
cleanup(d)

# 财经时政领域：P 为 P2（skip 正常），A/C 为 P0
d, s = build("finp2", channels_done={
    "E": {"status": "skip", "note": "未连接"},
    "A": {"status": "done", "note": "x"}, "B": {"status": "done", "note": "x"},
    "C": {"status": "done", "note": "x"}, "P": {"status": "skip", "note": "无预印本生态"},
}, files={"gathered_wechat.md": 300, "gathered_web.md": 300, "gathered_c.md": 300},
   report_bytes=700, domain="财经/电力设备/电网投资")
expect("p0+ 财经时政P2跳过→放行", cp.check_report_channels(d, s), 0)
cleanup(d)

print(f"\n==== check_progress 回归测试：PASS={PASS} FAIL={FAIL} ====")

if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
