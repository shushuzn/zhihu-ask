# -*- coding: utf-8 -*-
"""工作区清理工具（zhihu-ask 项目专用）

删除运行过程中产生的缓存与临时文件：
- .tmp/ 测试临时目录
- __pycache__/ 与 *.pyc Python 缓存
- *.tmp / *.bak / *.log / *~ / Thumbs.db / .DS_Store

只清理生成物，不触碰已跟踪源码、研究产出、配置与文档。

用法：
  python tools/clean_workspace.py            # 实际清理
  python tools/clean_workspace.py --dry-run  # 只列出将删除路径，不删除
"""

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMP_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEMP_FILE_PATTERNS = (
    ".tmp", ".bak", ".log", ".pyc", "~", "Thumbs.db", ".DS_Store"
)


def is_temp_file(name):
    lower = name.lower()
    return any(lower.endswith(p.lower()) or lower.endswith(p) for p in TEMP_FILE_PATTERNS)


def collect(root=ROOT):
    """返回待删除路径列表（文件与目录）。"""
    paths = []
    tmp_root = os.path.join(root, ".tmp")
    if os.path.isdir(tmp_root):
        paths.append(tmp_root)
    for root, dirs, files in os.walk(root):
        # 跳过 .git，避免触碰版本库内部
        dirs[:] = [d for d in dirs if d != ".git"]
        # 已整体加入 .tmp 根目录，不再枚举其内部子路径
        if root == os.path.dirname(tmp_root):
            dirs[:] = [d for d in dirs if d != ".tmp"]
        for d in list(dirs):
            if d in TEMP_DIR_NAMES:
                paths.append(os.path.join(root, d))
                dirs.remove(d)
        for f in files:
            if is_temp_file(f):
                paths.append(os.path.join(root, f))
    return sorted(set(paths))


def main():
    ap = argparse.ArgumentParser(description="工作区清理工具")
    ap.add_argument("--dry-run", action="store_true", help="只列出将删除路径，不实际删除")
    args = ap.parse_args()

    paths = collect()
    if not paths:
        print("工作区已干净，无需清理。")
        return 0

    if args.dry_run:
        print(f"将删除 {len(paths)} 个路径（dry-run）：")
        for p in paths:
            print("  " + os.path.relpath(p, ROOT))
        return 0

    for p in paths:
        if not os.path.lexists(p):
            continue
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                import shutil
                shutil.rmtree(p)
            else:
                os.remove(p)
        except OSError as e:
            print(f"WARN: 删除失败 {os.path.relpath(p, ROOT)}: {e}")
    print(f"已清理 {len(paths)} 个缓存/临时路径。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
