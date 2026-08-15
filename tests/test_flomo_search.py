# -*- coding: utf-8 -*-
"""flomo_search.py 回归测试：token 环境变量化（凭证不入库）+ 通道 F 自动登记。"""
import os
import sys
import json
import shutil
import importlib

import testutil

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

# ---- 通道 F 自动登记（查重执行后登记 done，note 含 memo_search 证据） ----
base = testutil.mktestdir(prefix="tf_")
slug = "f-slug"
slug_dir = os.path.join(base, "research", slug)
os.makedirs(slug_dir)
with open(os.path.join(slug_dir, ".progress.json"), "w", encoding="utf-8") as f:
    json.dump({"stage": "phase1_done", "data": {}}, f)
import channel_state as cs
old_root = cs.ROOT
cs.ROOT = base
try:
    ok, msg = fs.auto_register_f(slug, 3)
    expect("F+ 自动登记返回 True", ok, True)
    prog = json.load(open(os.path.join(slug_dir, ".progress.json"), encoding="utf-8"))
    e = prog["data"]["channels_done"]["F"]
    expect("F+ status done", e["status"], "done")
    expect("F+ note 含 memo_search 证据", "memo_search" in e["note"], True)
    expect("F+ note 含命中数", "3 条" in e["note"], True)

    ok2, msg2 = fs.auto_register_f("nosuch", 0)
    expect("F- 无 progress 不登记", ok2, False)
    expect("F- 缺 progress 提示", "未找到 research" in msg2, True)
finally:
    cs.ROOT = old_root
    shutil.rmtree(base, ignore_errors=True)

print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
