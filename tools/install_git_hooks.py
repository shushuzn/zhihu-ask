
"""
git pre-commit hook 安装工具（zhihu-ask 项目专用）

把提交前检查接入 git：每次 git commit 时自动运行 tools/git_protect.py，
若暂存区包含内部文件（plan.md、research/、.codebuddy/ 等）则阻止提交。

用法：
    python3 tools/install_git_hooks.py       # 安装/更新 pre-commit hook
    python3 tools/install_git_hooks.py --remove   # 移除 hook

注意：hook 位于 .git/hooks/（本地，不入库）。重新 clone 后需重跑本脚本。
"""

import sys
import os
import stat

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(ROOT, ".git", "hooks", "pre-commit")

HOOK_TEMPLATE = """#!/bin/sh
# zhihu-ask pre-commit hook: 自动检查暂存区是否有内部文件
# 由 tools/install_git_hooks.py 生成，勿手动编辑
cd "$(git rev-parse --show-toplevel)" || exit 1
python3 tools/git_protect.py
if [ $? -ne 0 ]; then
    echo "提交被阻止：请处理上方列出的文件后再试。"
    exit 1
fi
exit 0
"""

def main():
    remove = "--remove" in sys.argv
    if not os.path.isdir(os.path.dirname(HOOK_PATH)):
        print("ERROR: 未找到 .git/hooks 目录（当前目录不是 git 仓库？）")
        sys.exit(1)

    if remove:
        if os.path.exists(HOOK_PATH):
            os.remove(HOOK_PATH)
            print("已移除 pre-commit hook。")
        else:
            print("未找到 hook，无需移除。")
        return

    with open(HOOK_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK_TEMPLATE)

    try:
        os.chmod(HOOK_PATH, os.stat(HOOK_PATH).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass
    print(f"pre-commit hook 已安装: {HOOK_PATH}")

if __name__ == "__main__":
    main()
