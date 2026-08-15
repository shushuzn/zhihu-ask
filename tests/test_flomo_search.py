# -*- coding: utf-8 -*-
"""flomo_search.py 回归测试：token 只从环境变量读取（凭证不入库）。"""
import os
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import flomo_search as fs

PASS = 0
FAIL = 0


def expect(label, got, must_be):
    global PASS, FAIL
    if got == must_be:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, expected {must_be!r}")


# ---- token 环境变量化（此前硬编码在代码并进入公开仓库，须撤销重建） ----
_old_token = os.environ.get("FLOMO_MCP_TOKEN")
os.environ["FLOMO_MCP_TOKEN"] = "fmcp_test_token"
fs = importlib.reload(fs)
expect("token+ 从 env 读取", fs.MCP_TOKEN, "Bearer fmcp_test_token")

os.environ["FLOMO_MCP_TOKEN"] = "Bearer fmcp_bearer"
fs = importlib.reload(fs)
expect("token+ 已含 Bearer 前缀不重复", fs.MCP_TOKEN, "Bearer fmcp_bearer")

os.environ.pop("FLOMO_MCP_TOKEN", None)
fs = importlib.reload(fs)
expect("token- 未配置为空", fs.MCP_TOKEN, "")
try:
    fs.mcp_call("tools/call")
    expect("token- 未配置调用抛错", False, True)
except RuntimeError as e:
    expect("token- 未配置调用抛错", "FLOMO_MCP_TOKEN" in str(e), True)

if _old_token is None:
    os.environ.pop("FLOMO_MCP_TOKEN", None)
else:
    os.environ["FLOMO_MCP_TOKEN"] = _old_token
fs = importlib.reload(fs)

# F 查重为人工判读门禁：查重结论（复用/更新/参考/正常检索，含假阳性甄别）由主代理
# 判读后用 mark_channel 登记，工具不做自动登记（自动登记会把「已执行查重」与
# 「查重结论」混为一谈，假阳性会漏判）。token 相关测试见上方。

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
