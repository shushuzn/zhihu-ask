# -*- coding: utf-8 -*-
"""项目一键维护工具（zhihu-ask 项目专用）

按固定顺序执行：
1. 清理工作区缓存/临时文件（clean_workspace.py）
2. 全量回归测试（tests/run_all.py）
3. 项目模板/脚本一致性检查（check_consistency.py）
4. 展示 git status（不自动提交）

任一环节失败立即退出非零，不继续后续步骤。

用法：
  python tools/maintain.py
  python tools/maintain.py --skip-clean
"""

import argparse
import os
import subprocess
import sys

try:
    from tools.console_encoding import setup as _ce
    _ce()
except Exception:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PY = sys.executable


def run(cmd, label):
    print(f"\n─── {label} ───")
    r = subprocess.run([PY] + cmd, cwd=ROOT)
    if r.returncode != 0:
        print(f"[阻断] {label} 失败（退出码 {r.returncode}）。")
        sys.exit(r.returncode)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description="项目一键维护工具")
    ap.add_argument("--skip-clean", action="store_true", help="跳过工作区清理")
    args = ap.parse_args()

    if not args.skip_clean:
        run([os.path.join(TOOLS, "clean_workspace.py")], "clean_workspace")
    run([os.path.join(ROOT, "tests", "run_all.py")], "tests/run_all")
    run([os.path.join(TOOLS, "check_consistency.py")], "check_consistency")

    print("\n─── git status ───")
    subprocess.run(["git", "status", "--short"], cwd=ROOT)
    print("\n维护完成：清理、回归、一致性全部通过。可手动审查 git status 后提交。")


if __name__ == "__main__":
    main()
