# -*- coding: utf-8 -*-
"""
本地 git 提交保护工具（仅本地使用，不推送到公开仓库）

在提交前检查暂存区是否包含不应进入公开仓库的内部文件，防止误提交。
用法：
    python tools/git_protect.py            # 检查暂存区
    python tools/git_protect.py --commit    # 检查通过后自动提交（用 -f 传入消息文件）

内部文件清单（按需增改）：
    plan.md
    research/
    docs/PLAN_v1_ARCHIVE.md
    .codebuddy/
    *.tmp
    tools/init.*.json / tools/keywords.*.json（临时 config）
"""

import sys
import os
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 不应进入公开仓库的路径/模式（本地内部文件）
INTERNAL_PATTERNS = [
    "plan.md",
    "research/",
    "docs/PLAN_v1_ARCHIVE.md",
    ".codebuddy/",
    ".commit_msg.tmp",
    ".desc.tmp.txt",
    "tools/init.test.json",
    "tools/keywords.test.json",
]


def staged_files():
    """返回暂存区文件列表（git diff --cached --name-only）"""
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]


def is_internal(path):
    p = path.replace("\\", "/")
    return any(
        p == pat.rstrip("/") or p.startswith(pat)
        for pat in INTERNAL_PATTERNS
    )


def main():
    auto_commit = "--commit" in sys.argv
    files = staged_files()
    leaks = [f for f in files if is_internal(f)]

    if leaks:
        print("检测到不应提交的内部文件，已阻止：")
        for f in leaks:
            print(f"  - {f}")
        print("\n如需移除这些文件：")
        print("  git reset HEAD -- <file>    # 取消暂存")
        print("  或已确认不再需要则 git rm --cached <file>")
        sys.exit(1)

    if not files:
        print("暂存区为空，无需提交。")
        sys.exit(0)

    print("检查通过：暂存区无内部文件。")
    if auto_commit:
        print("（未自动提交，请手动执行 git commit）")

    sys.exit(0)


if __name__ == "__main__":
    main()
