"""net_check.py 回归测试：外网出口检测策略（8 项）。

覆盖（mock urllib，不真实联网）：
- has_egress：非空响应→True、空响应→False、urlopen 异常→False、read 异常→False
- require_egress：有出口→True 无输出；无出口→False 且提示含 purpose 与 WebFetch 建议

has_egress 是 report_to_docx 图片下载与 arxiv 直连的前置闸门，
回归（如恒 False）会让图片静默不下载、外网动作静默跳过，需守护。

运行：python tests/test_net_check.py
"""
import os
import sys
import io
import contextlib
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import net_check as nc

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


class _FakeResp:
    def __init__(self, data, raise_on_read=False):
        self.data = data
        self.raise_on_read = raise_on_read

    def read(self, n):
        if self.raise_on_read:
            raise OSError("read failed")
        return self.data


class _FakeCtx:
    def __init__(self, resp):
        self.resp = resp

    def __enter__(self):
        return self.resp

    def __exit__(self, *a):
        return False


def _patch_urlopen(fake):
    return mock.patch("net_check.urllib.request.urlopen", fake)


# ---- has_egress：非空响应 ----
with _patch_urlopen(lambda *a, **k: _FakeCtx(_FakeResp(b"<feed>data</feed>"))):
    expect("eg+ 非空响应", nc.has_egress(), True)

# 空响应
with _patch_urlopen(lambda *a, **k: _FakeCtx(_FakeResp(b""))):
    expect("eg- 空响应", nc.has_egress(), False)

# urlopen 抛异常
with _patch_urlopen(mock.Mock(side_effect=OSError("no route"))):
    expect("eg- urlopen 异常", nc.has_egress(), False)

# read 抛异常
with _patch_urlopen(lambda *a, **k: _FakeCtx(_FakeResp(b"x", raise_on_read=True))):
    expect("eg- read 异常", nc.has_egress(), False)

# ---- require_egress ----
with mock.patch("net_check.has_egress", return_value=True):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        expect("req+ 有出口返回 True", nc.require_egress("报告图片下载"), True)
    expect("req+ 有出口无提示", buf.getvalue(), "")

with mock.patch("net_check.has_egress", return_value=False):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        expect("req- 无出口返回 False", nc.require_egress("报告图片下载"), False)
    out = buf.getvalue()
    expect("req- 提示含 purpose", "报告图片下载" in out, True)
    expect("req- 提示含 WebFetch 建议", "WebFetch" in out, True)


print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
