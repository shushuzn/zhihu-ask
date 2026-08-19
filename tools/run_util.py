# -*- coding: utf-8 -*-
"""工具路径与子进程执行共享（zhihu-ask 工具链专用）。

把 tools/**/*.py 里重复 30+ 次的

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TOOLS = os.path.join(ROOT, "tools")
    PY = sys.executable

及 run(cmd, label) 执行器收敛到此单处，避免样板漂移
（如 tools/ 层级变化时需批量改 30 处，或 cwd/PY 入口不一致）。

用法：

    from tools.paths import ROOT, TOOLS, PY
    from tools.run_util import run, capture
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PY = sys.executable


def run(cmd, label="", check=True):
    """在项目根目录以 ``PY + cmd`` 方式运行子命令。

    ``check=True`` 时子进程非零退出即阻断（打印提示后 ``sys.exit``）；
    ``check=False`` 时仅返回退出码，调用方自定处理（如出网探测并回退离线）。
    """
    if label:
        print(f"\n─── {label} ───")
    r = subprocess.run([PY] + cmd, cwd=ROOT)
    if check and r.returncode != 0:
        print(f"[阻断] 步骤失败（退出码 {r.returncode}），请修复后重试。")
        sys.exit(r.returncode)
    return r.returncode


def capture(cmd, label=""):
    """在项目根目录以 ``PY + cmd`` 捕获 stdout/stderr（utf-8）。

    返回 ``(returncode, 文本)``。``label`` 非空时打印与 ``run`` 相同的
    步骤标题，便于全库体检/流水线在捕获模式下保持一致的阶段日志。
    """
    if label:
        print(f"\n─── {label} ───")
    r = subprocess.run([PY] + cmd, cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    so = r.stdout if isinstance(r.stdout, str) else ""
    se = r.stderr if isinstance(r.stderr, str) else ""
    out = (so or "") + (se or "")
    if out.strip():
        print(out.rstrip())
    return r.returncode, out
